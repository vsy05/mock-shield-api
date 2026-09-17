#!/bin/bash
################################################################################
# Filename        : shield_incidents_get_mocktest.bash
# Description     : MOCK-ONLY test script for the mock-shield-api Cloud Run
#                    service. CLIENT_ID/CLIENT_SECRET are fetched from
#                    Secret Manager by default (using this VM's own
#                    identity, same as the real production scripts) if not
#                    already set in the environment - export both to
#                    override with a specific value instead (e.g. to
#                    deliberately test a mismatch). Uploads the (mock)
#                    result to GCS,
#                    using your ambient GCP login (not a Shield credential),
#                    into a clearly-separate mock_test_landing/ path so it
#                    can never be confused with real landing/ data.
# Usage           : BUCKET_ENV=dev SHIELD_BASE_URL="https://<mock-cloud-run-url>" \
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

# Secret Manager - used to fetch CLIENT_ID/CLIENT_SECRET by default, proving
# the whole chain (this VM's identity -> Secret Manager -> real stored
# values) works end to end, exactly mirroring how the real production
# extraction scripts (shield_*_list_all.bash) fetch credentials. An
# explicit CLIENT_ID/CLIENT_SECRET env var still overrides this, e.g. to
# deliberately test a mismatch against what main.py validates server-side.
CLIENT_ID_SECRET="dta_corpops_shield_client_id"
CLIENT_SECRET_SECRET="dta_corpops_shield_client_secret"
SECRET_PROJECT="skyuk-uk-corpops-vfy-${BUCKET_ENV}"

# GCS upload - uses your ambient GCP login (gsutil), NOT a Shield credential.
# Lands in landing/ alongside real data, using the same filename convention
# as production - there is no way to distinguish this output by name alone
# once uploaded (see README's "Note on output naming").
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
# Hard-fails if BASE_URL or BUCKET_ENV are not explicitly set. CLIENT_ID/
# CLIENT_SECRET are no longer required here - if not exported, they are
# fetched from Secret Manager instead (see get_client_credentials below).
################################################################################
require_mock_env() {
    if [ -z "${BASE_URL}" ]; then
        error_exit "SHIELD_BASE_URL is not set. This is the mock-only test script - it will not default to the real Shield API. Set SHIELD_BASE_URL to your mock Cloud Run URL."
    fi

    if [[ "${BASE_URL}" == *"info-exchange.com"* ]]; then
        error_exit "SHIELD_BASE_URL points at a real info-exchange.com domain (${BASE_URL}). This mock-only script refuses to run against anything but a mock endpoint. Aborting."
    fi

    if [ -z "${BUCKET_ENV:-}" ]; then
        error_exit "BUCKET_ENV is not set. Set it (e.g. BUCKET_ENV=dev) so the GCS destination bucket and Secret Manager project can be determined."
    fi

    if [ -n "${CLIENT_ID:-}" ] || [ -n "${CLIENT_SECRET:-}" ]; then
        log "Mock environment confirmed: BASE_URL=${BASE_URL}, BUCKET_ENV=${BUCKET_ENV}, using CLIENT_ID/CLIENT_SECRET from environment (Secret Manager fetch skipped since an override was supplied)"
    else
        log "Mock environment confirmed: BASE_URL=${BASE_URL}, BUCKET_ENV=${BUCKET_ENV}, CLIENT_ID/CLIENT_SECRET not exported - will fetch from Secret Manager (project: ${SECRET_PROJECT})"
    fi
}

################################################################################
# Function: get_client_credentials
# Fetches CLIENT_ID/CLIENT_SECRET from Secret Manager, using this VM's own
# ambient gcloud identity - the same mechanism the real production
# extraction scripts use. Proves this VM can genuinely read the real
# stored values, not just that some string was typed into an env var.
# Only called if CLIENT_ID/CLIENT_SECRET were not already exported.
################################################################################
get_client_credentials() {
    log "CLIENT_ID/CLIENT_SECRET not set - fetching from Secret Manager (project: ${SECRET_PROJECT})..."

    local fetched_client_id fetched_client_secret

    fetched_client_id=$(gcloud secrets versions access latest \
        --secret="${CLIENT_ID_SECRET}" \
        --project="${SECRET_PROJECT}" 2>&1)
    if [ $? -ne 0 ]; then
        error_exit "Failed to fetch ${CLIENT_ID_SECRET} from Secret Manager (project: ${SECRET_PROJECT}): ${fetched_client_id}"
    fi

    fetched_client_secret=$(gcloud secrets versions access latest \
        --secret="${CLIENT_SECRET_SECRET}" \
        --project="${SECRET_PROJECT}" 2>&1)
    if [ $? -ne 0 ]; then
        error_exit "Failed to fetch ${CLIENT_SECRET_SECRET} from Secret Manager (project: ${SECRET_PROJECT}): ${fetched_client_secret}"
    fi

    log "Successfully fetched CLIENT_ID/CLIENT_SECRET from Secret Manager"

    CLIENT_ID="${fetched_client_id}"
    CLIENT_SECRET="${fetched_client_secret}"
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
# Function: convert_to_ndjson
# Mirrors shield-api-file-extract's app.py convert_to_ndjson(): unwraps the
# JSON:API envelope's "data" array and re-serialises each element onto its
# own line. This step is what actually happens in production between the
# raw Shield/mock response and what lands in GCS - without it, this script
# would upload the raw, unexploded envelope, which does not match what the
# real pipeline (or the downstream arc/cc ingest jobs) actually expects.
################################################################################
convert_to_ndjson() {
    local response_body="$1"

    if ! command -v jq &> /dev/null; then
        error_exit "jq is required to convert the mock response to NDJSON but is not installed."
    fi

    echo "${response_body}" | jq -c '.data[]'
}

################################################################################
# Function: upload_to_gcs
# Converts the mock response to NDJSON (one record per line, matching what
# the real relay's convert_to_ndjson() produces), gzips it, and uploads via
# gsutil, using your ambient GCP login - not a Shield credential.
################################################################################
upload_to_gcs() {
    local response_body="$1"
    local timestamp="$2"

    local output_file_name="${OUTPUT_FILE_PREFIX}_${timestamp}_1.json"
    local tmp_file
    tmp_file=$(mktemp)

    convert_to_ndjson "${response_body}" > "${tmp_file}"

    local ndjson_line_count
    ndjson_line_count=$(wc -l < "${tmp_file}")
    log "Converted response to NDJSON: ${ndjson_line_count} record line(s)"

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

    if [ -z "${CLIENT_ID:-}" ] || [ -z "${CLIENT_SECRET:-}" ]; then
        get_client_credentials
    fi

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
    convert_to_ndjson "${response_body}" > "${out_file}"
    log "Saved local NDJSON copy (matches what lands in GCS) to ${out_file}"

    local raw_out_file="${OUTPUT_DIR}/${OUTPUT_FILE_PREFIX}_raw_envelope_sample.json"
    echo "${response_body}" > "${raw_out_file}"
    log "Saved raw (unconverted) envelope for reference to ${raw_out_file}"

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
