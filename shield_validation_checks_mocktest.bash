#!/bin/bash
################################################################################
# Filename        : shield_validation_checks_mocktest.bash
# Description     : MOCK-ONLY test script that proves the 4 validation checks
#                    built into mock-shield-api's main.py actually work.
#                    Unlike the other 4 mocktest scripts (which pull a page
#                    and upload it to GCS, exactly mirroring the real
#                    extraction flow), this script calls the SAME data
#                    endpoint 5 times: once normally (expect 200/pass), then
#                    4 times with &simulate=<check> to deliberately break
#                    one check at a time (expect 422/fail each time).
#                    No GCS upload happens here - this script only proves
#                    the checks fire correctly, it does not test the
#                    extract-and-land flow (the other 4 scripts already do).
#                    Contains NO Secret Manager code path, same as the
#                    other 4 mocktest scripts.
# Usage           : SHIELD_BASE_URL="https://<mock-cloud-run-url>" \
#                    bash shield_validation_checks_mocktest.bash
################################################################################

set -o pipefail

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------
BASE_URL="${SHIELD_BASE_URL:-}"
API_VERSION="v0"
APP_NAME="riskAssessments"
TABLE_ID="identifiedRisk"
PAGE_LIMIT=2

LOG_DIR="${SYS_LOG:-.}"
LOG_FILE="${LOG_DIR}/shield_validation_checks_mocktest_$(date -u '+%Y%m%d_%H%M%S').log"

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
# Same safety rail as the other 4 mocktest scripts - refuses to run
# against anything but a mock endpoint.
################################################################################
require_mock_env() {
    if [ -z "${BASE_URL}" ]; then
        error_exit "SHIELD_BASE_URL is not set. Set it to your mock Cloud Run URL."
    fi

    if [[ "${BASE_URL}" == *"info-exchange.com"* ]]; then
        error_exit "SHIELD_BASE_URL points at a real info-exchange.com domain (${BASE_URL}). This mock-only script refuses to run against anything but a mock endpoint. Aborting."
    fi

    log "Mock environment confirmed: BASE_URL=${BASE_URL}"
}

################################################################################
# Function: get_identity_token
# Same Cloud Run invoker auth pattern as the other 4 mocktest scripts.
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
# Function: call_validation_endpoint
# Calls the data endpoint with &validate=true, optionally &simulate=<name>.
# Returns http_code and response_body via global vars (bash-friendly pattern
# matching the other 4 scripts' fetch_page/response handling).
################################################################################
call_validation_endpoint() {
    local identity_token="$1"
    local simulate="$2"

    local url="${BASE_URL}/api/${API_VERSION}/${APP_NAME}/${TABLE_ID}?page[limit]=${PAGE_LIMIT}&page[offset]=0&validate=true"
    if [ -n "${simulate}" ]; then
        url="${url}&simulate=${simulate}"
    fi

    curl -sg -w "\n%{http_code}" \
        -X GET "${url}" \
        -H "Accept: application/vnd.api+json" \
        -H "Authorization: Bearer ${identity_token}"
}

################################################################################
# Function: run_scenario
# Runs one scenario, checks the HTTP status matches what's expected, logs
# pass/fail. Returns 0 on match, 1 on mismatch.
################################################################################
run_scenario() {
    local label="$1"
    local simulate="$2"
    local expected_code="$3"
    local identity_token="$4"

    log "--- Scenario: ${label} (simulate=${simulate:-none}, expecting HTTP ${expected_code}) ---"

    local response http_code response_body
    response=$(call_validation_endpoint "${identity_token}" "${simulate}")
    http_code=$(echo "${response}" | tail -n 1)
    response_body=$(echo "${response}" | sed '$d')

    log "HTTP Status: ${http_code}"
    log "Response: ${response_body}"

    if [ "${http_code}" == "${expected_code}" ]; then
        log "PASS: ${label} returned expected HTTP ${expected_code}"
        return 0
    else
        log "FAIL: ${label} expected HTTP ${expected_code} but got ${http_code}"
        return 1
    fi
}

################################################################################
# Main
################################################################################
main() {
    log "=== MOCK VALIDATION TEST: proving the 4 checks in mock-shield-api work ==="

    require_mock_env

    local identity_token
    identity_token=$(get_identity_token)

    local pass_count=0
    local fail_count=0

    run_scenario "Happy path (no simulate)"        ""          "200" "${identity_token}"
    if [ $? -eq 0 ]; then pass_count=$((pass_count + 1)); else fail_count=$((fail_count + 1)); fi

    run_scenario "Simulated file_type failure"     "file_type" "422" "${identity_token}"
    if [ $? -eq 0 ]; then pass_count=$((pass_count + 1)); else fail_count=$((fail_count + 1)); fi

    run_scenario "Simulated utf8 failure"          "utf8"      "422" "${identity_token}"
    if [ $? -eq 0 ]; then pass_count=$((pass_count + 1)); else fail_count=$((fail_count + 1)); fi

    run_scenario "Simulated json failure"          "json"      "422" "${identity_token}"
    if [ $? -eq 0 ]; then pass_count=$((pass_count + 1)); else fail_count=$((fail_count + 1)); fi

    run_scenario "Simulated row_size failure"      "row_size"  "422" "${identity_token}"
    if [ $? -eq 0 ]; then pass_count=$((pass_count + 1)); else fail_count=$((fail_count + 1)); fi

    log "=== Summary: ${pass_count} passed, ${fail_count} failed out of 5 scenarios ==="

    if [ "${fail_count}" -gt 0 ]; then
        error_exit "One or more validation scenarios did not behave as expected"
    fi

    log "=== All validation checks confirmed working correctly ==="
}

trap 'log "Script interrupted by user"; exit 130' INT TERM

main "$@"
