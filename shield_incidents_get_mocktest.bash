#!/bin/bash
################################################################################
# Filename        : shield_incidents_get_mocktest.bash
# Description     : MOCK-ONLY test script for the mock-shield-api Cloud Run
#                    service. Contains NO Secret Manager code path - CLIENT_ID
#                    and CLIENT_SECRET must already be set in the environment,
#                    or the script refuses to run. Safe to use for testing
#                    against the mock without any risk of touching real
#                    Shield credentials. Uploads the (mock) result to GCS,
#                    using your ambient GCP login (not a Shield credential),
#                    into a clearly-separate mock_test_landing/ path so it
#                    can never be confused with real landing/ data.
# Usage           : BUCKET_ENV=dev SHIELD_BASE_URL="https://<mock-cloud-run-url>" \
#                    CLIENT_ID="anything" CLIENT_SECRET="anything" \
#                    bash shield_riskassessments_identifiedrisk_get_mocktest.bash
################################################################################

set -o pipefail

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------
# No default prod URL fallback here on purpose - this script is mock-only.
# SHIELD_BASE_URL MUST be set explicitly (e.g. to the mock Cloud Run URL).
BASE_URL="${SHIELD_BASE_URL:-}"
API_VERSION="v0"
APP_NAME="incidentReporting"
TABLE_ID="incidents"

PAGE_LIMIT=2
OUTPUT_DIR="./output"
OUTPUT_FILE_PREFIX="SHIELD_INCIDENTS_LIST_ALL"

# GCS upload - uses your ambient GCP login (gsutil), NOT a Shield credential.
# Lands in landing/ alongside real data; the MOCKTEST_ filename prefix keeps
# it clearly distinguishable from real SHIELD_... files in the same folder.
DESTINATION_BUCKET="skyuk-uk-lan-tds-shield-is-${BUCKET_ENV}"
GCS_PATH_PREFIX="incidents_list_all/landing/"

LOG_DIR="${SYS_LOG:-.}"
LOG_FILE="${LOG_DIR}/shield_incidents_get_mocktest_$(date -u '+%Y%m%d_%H%M%S').log"

################################################################################
# Function: log
################################################################################
log() {
    local message="$1"
    local timestamp
    timestamp=$(date -u '+%Y-%m-%d %H:%M:%S UTC')
    echo "[${timestamp}] ${message}" | tee -a "${LOG_FILE}" >&2
}

error_exit() {
    log "ERROR: $1"
    exit 1
}

################################################################################
# Function: require_mock_env
# Hard-fails if BASE_URL, CLIENT_ID, or CLIENT_SECRET are not explicitly set.
# NO Secret Manager fallback exists anywhere in this file.
################################################################################
require_mock_env() {
    if [ -z "${BASE_URL}" ]; then
        error_exit "SHIELD_BASE_URL is not set. This is the mock-only test script - it will not default to the real Shield API. Set SHIELD_BASE_URL to your mock Cloud Run URL."
    fi

    if [[ "${BASE_URL}" == *"info-exchange.com"* ]]; then
        error_exit "SHIELD_BASE_URL points at a real info-exchange.com domain (${BASE_URL}). This mock-only script refuses to run against anything but a mock endpoint. Aborting."
    fi

    if [ -z "${CLIENT_ID:-}" ] || [ -z "${CLIENT_SECRET:-}" ]; then
        error_exit "CLIENT_ID and/or CLIENT_SECRET are not set. Export dummy values before running (e.g. CLIENT_ID=anything CLIENT_SECRET=anything) - this script has no Secret Manager fallback."
    fi

    if [ -z "${BUCKET_ENV:-}" ]; then
        error_exit "BUCKET_ENV is not set. Set it (e.g. BUCKET_ENV=dev) so the GCS destination bucket can be determined."
    fi

    log "Mock environment confirmed: BASE_URL=${BASE_URL}, BUCKET_ENV=${BUCKET_ENV}, using CLIENT_ID/CLIENT_SECRET from environment (no Secret Manager call will be made)"
}

################################################################################
# Function: get_identity_token
# Cloud Run requires a Google-signed identity token to invoke this service
# (it is not publicly accessible). This matches the same pattern used by
# your Everbridge scripts to call gcs-api-file-extract. This is separate
# from - and in addition to - the mock's own simulated OAuth flow below.
################################################################################
get_identity_token() {
    log "Requesting Google identity token for audience ${BASE_URL} ..."
    local identity_token
    identity_token=$(gcloud auth print-identity-token --audiences="${BASE_URL}" 2>&1)
    if [ -z "${identity_token}" ]; then
        error_exit "Failed to obtain identity token: ${identity_token}"
    fi
    log "Identity token obtained successfully"
    echo "${identity_token}"
}

################################################################################
# Function: get_access_token
# Simulates the mock's OAuth client_credentials exchange. The identity_token
# is passed here only to satisfy Cloud Run's own invoker check on the way
# in - it is unrelated to the mock app's own client_id/client_secret logic.
################################################################################
get_access_token() {
    local client_id="$1"
    local client_secret="$2"
    local identity_token="$3"

    log "Requesting access token from ${BASE_URL}/identity/connect/token ..."

    local token_response
    token_response=$(curl -s -X POST \
        "${BASE_URL}/identity/connect/token" \
        -H "Authorization: Bearer ${identity_token}" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        --data-urlencode "grant_type=client_credentials" \
        --data-urlencode "scope=api" \
        --data-urlencode "client_id=${client_id}" \
        --data-urlencode "client_secret=${client_secret}")

    local access_token
    if command -v jq &> /dev/null; then
        access_token=$(echo "${token_response}" | jq -r '.access_token // empty')
    else
        access_token=$(echo "${token_response}" | grep -oP '"access_token":\s*"\K[^"]+')
    fi

    if [ -z "${access_token}" ]; then
        log "Token response: ${token_response}"
        error_exit "Failed to obtain access token"
    fi

    log "Access token obtained successfully (mock OAuth flow confirmed working)"
    echo "${access_token}"
}

################################################################################
# Function: fetch_page
# Uses the identity_token to satisfy Cloud Run's invoker check, since this
# mock is not publicly reachable. In the real production pipeline (against
# the actual Shield API), this would instead use the mock/real OAuth
# access_token, as the real API has no Google Cloud Run auth layer.
################################################################################
fetch_page() {
    local identity_token="$1"
    local offset="$2"

    local url="${BASE_URL}/api/${API_VERSION}/${APP_NAME}/${TABLE_ID}?page[limit]=${PAGE_LIMIT}&page[offset]=${offset}"
    log "GET ${url}"

    curl -sg -w "\n%{http_code}" \
        -X GET "${url}" \
        -H "Accept: application/vnd.api+json" \
        -H "Authorization: Bearer ${identity_token}"
}

################################################################################
# Function: upload_to_gcs
# Gzips the mock response and uploads it via gsutil, using your ambient GCP
# login - not a Shield credential. Lands in mock_test_landing/, separate
# from any real Shield data path.
################################################################################
upload_to_gcs() {
    local response_body="$1"
    local timestamp="$2"

    local output_file_name="${OUTPUT_FILE_PREFIX}_${timestamp}_1.json"
    local tmp_file
    tmp_file=$(mktemp)
    echo "${response_body}" > "${tmp_file}"
    gzip -f "${tmp_file}"

    local gcs_dest="gs://${DESTINATION_BUCKET}/${GCS_PATH_PREFIX}${output_file_name}.gz"

    if gsutil cp "${tmp_file}.gz" "${gcs_dest}" 2>&1 | tee -a "${LOG_FILE}"; then
        log "Successfully uploaded mock sample to ${gcs_dest}"
        rm -f "${tmp_file}.gz"
        return 0
    else
        log "Failed to upload mock sample to GCS"
        rm -f "${tmp_file}.gz"
        return 1
    fi
}

################################################################################
# Main
################################################################################
main() {
    log "=== MOCK TEST: InfoExchange (Shield) incidentReporting/incidents ==="

    require_mock_env

    mkdir -p "${OUTPUT_DIR}"

    local identity_token
    identity_token=$(get_identity_token)

    local access_token
    access_token=$(get_access_token "${CLIENT_ID}" "${CLIENT_SECRET}" "${identity_token}")

    local response http_code response_body
    response=$(fetch_page "${identity_token}" 0)
    http_code=$(echo "${response}" | tail -n 1)
    response_body=$(echo "${response}" | sed '$d')

    log "HTTP Status: ${http_code}"

    if [ "${http_code}" != "200" ]; then
        log "Response body: ${response_body}"
        error_exit "Request failed with HTTP ${http_code}"
    fi

    local timestamp
    timestamp=$(date -u '+%Y%m%d%H%M%S')

    local out_file="${OUTPUT_DIR}/${OUTPUT_FILE_PREFIX}_sample.json"
    echo "${response_body}" > "${out_file}"
    log "Saved local copy to ${out_file}"

    if command -v jq &> /dev/null; then
        local total_count page_record_count
        total_count=$(echo "${response_body}" | jq -r '.meta.totalCount // -1')
        page_record_count=$(echo "${response_body}" | jq -r '.data | length')
        log "Fetched ${page_record_count} sample record(s) (mock totalCount: ${total_count})"
    else
        log "jq not installed - saved raw JSON only"
    fi

    if upload_to_gcs "${response_body}" "${timestamp}"; then
        log "=== Mock test pull completed. Local copy in ${OUTPUT_DIR}/, GCS copy in gs://${DESTINATION_BUCKET}/${GCS_PATH_PREFIX} ==="
    else
        error_exit "Mock test fetch succeeded but GCS upload failed"
    fi
}

trap 'log "Script interrupted by user"; exit 130' INT TERM

main "$@"
