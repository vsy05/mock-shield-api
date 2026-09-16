#!/bin/bash
################################################################################
# Manual curl commands to test each of the 4 validation checks individually,
# plus the happy path. Confirmed working against the deployed mock-shield-api
# on 2026-09-16 - actual results from each command are noted below each one.
#
# IMPORTANT - two things that caused failures during testing, now fixed here:
#   1. MUST use "-g" (globoff) with curl - the [limit]/[offset] square
#      brackets in the URL are otherwise misread as curl's own range
#      syntax and the request fails silently under -s.
#   2. A real Google identity token IS required, despite
#      --allow-unauthenticated being set in cloudbuild-deploy.yaml. This
#      org's IAM policy blocks granting allUsers access, so that flag's
#      IAM binding silently doesn't take effect. Confirmed directly:
#      calling without a token returns HTTP 401 from Google's own front
#      end, before the request ever reaches main.py.
################################################################################

# ------------------------------------------------------------------
# Setup - run once, reused by all 5 commands below
# ------------------------------------------------------------------
export SHIELD_BASE_URL="https://mock-shield-api-246656841134.europe-west1.run.app"
TOKEN=$(gcloud auth print-identity-token --audiences="${SHIELD_BASE_URL}")


# ------------------------------------------------------------------
# 1. Happy path - no simulate param
# Confirmed result: HTTP 200, full data payload returned (2 records,
# meta.totalCount 20621) - all 4 checks pass on clean data.
# ------------------------------------------------------------------
curl -sg -w "\nHTTP Status: %{http_code}\n" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Accept: application/vnd.api+json" \
  "${SHIELD_BASE_URL}/api/v0/riskAssessments/identifiedRisk?page[limit]=2&page[offset]=0&validate=true"


# ------------------------------------------------------------------
# 2. file_type check - deliberately wrong Content-Type
# Confirmed result: HTTP 422
#   {"error":"Invalid Content-Type header: 'text/html'. Expected
#   'application/vnd.api+json'.","simulated_failure":"file_type",
#   "validation_result":"FAILED"}
# ------------------------------------------------------------------
curl -sg -w "\nHTTP Status: %{http_code}\n" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Accept: application/vnd.api+json" \
  "${SHIELD_BASE_URL}/api/v0/riskAssessments/identifiedRisk?page[limit]=2&page[offset]=0&validate=true&simulate=file_type"


# ------------------------------------------------------------------
# 3. utf8_encoding check - deliberately invalid UTF-8 bytes
# Confirmed result: HTTP 422
#   {"error":"File contains invalid UTF-8 bytes.","simulated_failure":
#   "utf8","validation_result":"FAILED"}
# ------------------------------------------------------------------
curl -sg -w "\nHTTP Status: %{http_code}\n" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Accept: application/vnd.api+json" \
  "${SHIELD_BASE_URL}/api/v0/riskAssessments/identifiedRisk?page[limit]=2&page[offset]=0&validate=true&simulate=utf8"


# ------------------------------------------------------------------
# 4. json_parsing check - deliberately truncated/broken JSON
# Confirmed result: HTTP 422
#   {"error":"Invalid JSON syntax on record 2: Unterminated string
#   starting at","simulated_failure":"json","validation_result":"FAILED"}
# ------------------------------------------------------------------
curl -sg -w "\nHTTP Status: %{http_code}\n" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Accept: application/vnd.api+json" \
  "${SHIELD_BASE_URL}/api/v0/riskAssessments/identifiedRisk?page[limit]=2&page[offset]=0&validate=true&simulate=json"


# ------------------------------------------------------------------
# 5. row_size check - deliberately oversized record (3MB > 2MB limit)
# Confirmed result: HTTP 422
#   {"error":"Record 1 size 3.00MB exceeds row limit of 2.0MB.",
#   "simulated_failure":"row_size","validation_result":"FAILED"}
# ------------------------------------------------------------------
curl -sg -w "\nHTTP Status: %{http_code}\n" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Accept: application/vnd.api+json" \
  "${SHIELD_BASE_URL}/api/v0/riskAssessments/identifiedRisk?page[limit]=2&page[offset]=0&validate=true&simulate=row_size"


# ------------------------------------------------------------------
# Summary of confirmed results (2026-09-16, corpops-vfy-dev):
#   1. Happy path       -> 200  (PASS)
#   2. file_type        -> 422  (PASS)
#   3. utf8_encoding     -> 422  (PASS)
#   4. json_parsing       -> 422  (PASS)
#   5. row_size           -> 422  (PASS)
# All 4 checks confirmed working correctly, manually, one call at a time.
# ------------------------------------------------------------------

# ------------------------------------------------------------------
# Optional: repeat any of the above against the other 3 endpoints by
# swapping the path, e.g.:
#   /api/v0/incidentReporting/incidents
#   /api/v0/riskAssessments/riskAssessment
#   /api/v0/incidentReporting/injuredPerson
# ------------------------------------------------------------------
