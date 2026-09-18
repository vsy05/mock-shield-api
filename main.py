"""
Mock InfoExchange (Shield) API for Development/Testing
Mimics the real InfoExchange (EcoOnline Shield) API behavior for testing the
Shield extraction pipeline in dev, since EcoOnline does not provide a
separate dev/sandbox tenant.

Endpoints mocked:
    POST /identity/connect/token
        - OAuth2 client_credentials grant (any client_id/client_secret accepted)
    GET  /api/v0/riskAssessments/identifiedRisk
        - JSON:API-shaped response with sample records
        - Supports page[limit] / page[offset] query params
    GET  /api/v0/incidentReporting/incidents
        - JSON:API-shaped response with sample records
        - Supports page[limit] / page[offset] query params
    GET  /api/v0/riskAssessments/riskAssessment
        - JSON:API-shaped response with sample records
        - Supports page[limit] / page[offset] query params
    GET  /api/v0/incidentReporting/injuredPerson
        - JSON:API-shaped response with sample records
        - Supports page[limit] / page[offset] query params
    GET  /health
        - Health check

Usage (local):
    python3 main.py
    (listens on 0.0.0.0:8080)

Usage (once deployed to Cloud Run):
    SHIELD_BASE_URL=https://<cloud-run-url> CLIENT_ID=anything CLIENT_SECRET=anything BUCKET_ENV=dev \
    bash shield_identifiedrisk_get_mocktest.bash
    (or shield_incidents_get_mocktest.bash /
     shield_riskassessment_get_mocktest.bash /
     shield_injuredperson_get_mocktest.bash for the other 3 endpoints)
"""

from flask import Flask, jsonify, request
from datetime import datetime
import uuid
import gzip
import io
import os

app = Flask(__name__)


# ==============================================================================
# Secret Manager validation for /identity/connect/token
#
# Purpose: prove the mock's own Cloud Run runtime service account can
# actually reach Secret Manager, rather than just accepting any
# client_id/client_secret blindly. The mock now reads the EXPECTED
# client_id/client_secret from Secret Manager itself at request time and
# compares them against whatever was submitted.
#
# To keep existing test scripts (CLIENT_ID=anything CLIENT_SECRET=anything)
# working unchanged, store the literal string "anything" as the value of
# both secrets below - the comparison then still passes, but only because
# Secret Manager was genuinely reached and read, not because validation
# was skipped.
#
# Secret names/project are overridable via env vars so this can point at
# whichever project/secrets you've set up without a code change.
#
# SECRET_MANAGER_PROJECT resolves in this order:
#   1. Explicit SECRET_MANAGER_PROJECT env var, if set (highest priority)
#   2. PROJ_ID env var - already set on every deploy via
#      --set-env-vars=PROJ_ID=${PROJECT_ID} in cloudbuild-deploy.yaml, so
#      this automatically follows whichever project the service is
#      actually running in (dev, test, etc.) with no per-environment
#      config needed
#   3. Hardcoded 'skyuk-uk-corpops-vfy-dev' as a last-resort fallback only
# ==============================================================================

SECRET_MANAGER_PROJECT = os.environ.get('SECRET_MANAGER_PROJECT') or os.environ.get('PROJ_ID', 'skyuk-uk-corpops-vfy-dev')
CLIENT_ID_SECRET_NAME = os.environ.get('CLIENT_ID_SECRET_NAME', 'dta_corpops_shield_client_id')
CLIENT_SECRET_SECRET_NAME = os.environ.get('CLIENT_SECRET_SECRET_NAME', 'dta_corpops_shield_client_secret')


def get_secret_from_manager(secret_id, project=SECRET_MANAGER_PROJECT, version='latest'):
    """
    Reads a secret value from Secret Manager. Raises on any failure
    (permission denied, not found, destroyed version, etc.) rather than
    swallowing errors - the caller needs to distinguish "Secret Manager
    unreachable" from "credentials didn't match" for this to be a useful
    connectivity test.
    """
    from google.cloud import secretmanager
    client = secretmanager.SecretManagerServiceClient()
    secret_path = f"projects/{project}/secrets/{secret_id}/versions/{version}"
    response = client.access_secret_version(request={"name": secret_path})
    return response.payload.data.decode("UTF-8").strip()


def get_standard_headers(content_type='application/vnd.api+json'):
    """
    Generate standard response headers matching real API format.
    content_type is overridable so a test call can deliberately simulate
    a wrong Content-Type header (see the `simulate` param on the data
    endpoints below) to prove the file_type validation check catches it.
    """
    return {
        'Date': datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT'),
        'Content-Type': content_type,
        'Connection': 'keep-alive',
        'Cache-Control': 'no-store',
        'X-Request-Id': uuid.uuid4().hex,
    }


# ==============================================================================
# Validation checks - ported verbatim from shield-api-file-extract's app.py,
# added here ONLY so this mock can be used to demonstrate/test that the same
# 4 checks correctly accept good data and reject each of the 4 failure modes.
#
# This is a TEST AID, not a production requirement: the real check is that
# shield-api-file-extract validates data it downloads FROM Shield (or this
# mock). Here, the checks are re-run against this mock's own output, purely
# so a tester can hit ?simulate=<check_name> and see a 422 with the exact
# same error a broken real Shield response would produce.
#
# Enable/disable with a request param: ?validate=true (see each endpoint).
# Deliberately break one check at a time with: ?simulate=<name>, one of:
#   file_type   - returns the response with a wrong Content-Type header
#   utf8        - injects an invalid UTF-8 byte into the response
#   json        - truncates the JSON body so it no longer parses
#   row_size    - inflates one record's size past the 2MB per-row limit
# ==============================================================================

ENABLED_CHECKS = ['file_type', 'utf8_encoding', 'json_parsing', 'row_size']
EXPECTED_CONTENT_TYPE = 'application/vnd.api+json'
MAX_ROW_SIZE_MB = 2.0  # BigQuery per-row limit; Shield records run ~5-6KB in practice


class ValidationError(Exception):
    """Raised when a validation check fails."""
    pass


def check_file_type(response_headers, expected_content_type):
    content_type = response_headers.get('Content-Type', '')
    mime_type = content_type.split(';')[0].strip()
    if mime_type != expected_content_type:
        raise ValidationError(
            f"Invalid Content-Type header: '{content_type}'. "
            f"Expected '{expected_content_type}'."
        )


def check_utf8_encoding(file_bytes):
    try:
        file_bytes.decode('utf-8', errors='strict')
    except UnicodeDecodeError:
        raise ValidationError("File contains invalid UTF-8 bytes.")


def check_json_parsing(ndjson_bytes):
    import json as _json
    text = ndjson_bytes.decode('utf-8', errors='replace')
    for i, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            _json.loads(line)
        except _json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON syntax on record {i}: {e.msg}")


def check_row_size(ndjson_bytes, max_size_mb):
    text = ndjson_bytes.decode('utf-8', errors='replace')
    for i, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        size_mb = len(line.encode('utf-8')) / (1024 * 1024)
        if size_mb > max_size_mb:
            raise ValidationError(
                f"Record {i} size {size_mb:.2f}MB exceeds row limit of {max_size_mb}MB."
            )


def validate_page(ndjson_bytes, response_headers):
    """Runs all enabled checks in order. Raises ValidationError on first failure."""
    if 'file_type' in ENABLED_CHECKS:
        check_file_type(response_headers, EXPECTED_CONTENT_TYPE)
    if 'utf8_encoding' in ENABLED_CHECKS:
        check_utf8_encoding(ndjson_bytes)
    if 'json_parsing' in ENABLED_CHECKS:
        check_json_parsing(ndjson_bytes)
    if 'row_size' in ENABLED_CHECKS:
        check_row_size(ndjson_bytes, MAX_ROW_SIZE_MB)


def convert_to_ndjson(records):
    """Same conversion shield-api-file-extract does: one record per line."""
    import json as _json
    lines = [_json.dumps(record, ensure_ascii=False) for record in records]
    return ("\n".join(lines) + "\n").encode("utf-8") if lines else b""


def run_self_validation(records, simulate, base_content_type):
    """
    Runs the 4 checks against this mock's own about-to-be-returned data,
    optionally sabotaging it first per `simulate`, so a tester can prove
    each check independently catches its corresponding failure mode.

    Returns (is_valid, error_message_or_None, headers_to_use).
    """
    import copy
    records = copy.deepcopy(records)
    headers = get_standard_headers(base_content_type)

    if simulate == 'file_type':
        headers = get_standard_headers('text/html')  # wrong content-type

    ndjson_bytes = convert_to_ndjson(records)

    if simulate == 'utf8':
        # Inject an invalid UTF-8 byte sequence directly into the bytes
        ndjson_bytes = ndjson_bytes[:10] + b'\xff\xfe' + ndjson_bytes[10:]

    if simulate == 'json':
        # Truncate mid-object so JSON parsing breaks
        ndjson_bytes = ndjson_bytes[:len(ndjson_bytes) // 2]

    if simulate == 'row_size':
        # Inflate the first record's size past the 2MB limit
        if records:
            records[0].setdefault('attributes', {})['_test_oversized_blob'] = 'A' * (3 * 1024 * 1024)
        ndjson_bytes = convert_to_ndjson(records)

    try:
        validate_page(ndjson_bytes, headers)
        return True, None, headers
    except ValidationError as e:
        return False, str(e), headers


# ------------------------------------------------------------------
# Sample data - rebuilt from the REAL field structure of a
# riskAssessments/identifiedRisk record (confirmed against an actual
# prod sample), with entirely fictional values. Field names are
# preserved exactly, including known quirks (e.g. the field named
# "riskRatingafterControlMeasuresactionsSafet" - not a typo here,
# this matches the real API's actual field name so parsing logic
# is tested faithfully).
# ------------------------------------------------------------------
IDENTIFIED_RISK_DATA = [
    {
        "id": "70001",
        "type": "identifiedRisk",
        "attributes": {
            "identifiedRiskRefNo": 88801,
            "riskName": "Trip hazard, minor injury from loose flooring",
            "risksToHealth": None,
            "risksToSafety": None,
            "riskRatingBeforeControlMeasuresActions": {
                "text": "Medium",
                "colour": "#FFFF00"
            },
            "technicalControlMeasures": None,
            "organisationalControlMeasures": None,
            "proceduralControlMeasures": None,
            "status": {
                "text": "Complete",
                "colour": "#00FF00"
            },
            "lastUpdatedOn": "2026-05-14T10:12:00",
            "lastUpdatedBy": "Test User One",
            "riskRatingAfterControlMeasuresActions": {
                "text": "Low",
                "colour": "#00FF00"
            },
            "riskDescription": "Sample fictional description: uneven flooring in a test venue corridor requiring signage and inspection.",
            "riskRatingBeforeControlMeasuresactionsSafety": {
                "text": "",
                "colour": None
            },
            "riskRatingafterControlMeasuresactionsSafet": {
                "text": "",
                "colour": None
            },
            "risksToHealthAfter": None,
            "risksToSafetyAfterControlMeasures": None,
            "personalProtectiveEquipment": None,
            "hazardCategoryuserDefinedHazard": "Slips and Trips",
            "tickToConfirmAllFieldsCompleted": True,
            "conditionalLogicFormattedText": None,
            "suggestedControlMeasures": "Sample fictional control measures text: inspect flooring regularly, place warning signage, report any damage to site management immediately."
        },
        "relationships": {
            "riskAssessmentRefNo": {
                "data": {"type": "riskAssessment", "id": "77001", "meta": {"displayValue": 9999}},
                "links": {"related": "/api/v0/riskAssessments/riskAssessment/77001"}
            },
            "hazardDocument": {"data": None},
            "likelihood": {
                "data": {"type": "luLikelihood", "id": "2", "meta": {"displayValue": "2 - Unlikely"}},
                "links": {"related": "/api/v0/riskAssessments/luLikelihood/2"}
            },
            "likelihoodAfterControl": {
                "data": {"type": "luLikelihood", "id": "1", "meta": {"displayValue": "1 - Remote"}},
                "links": {"related": "/api/v0/riskAssessments/luLikelihood/1"}
            },
            "severity": {
                "data": {"type": "luRiskSeverity", "id": "2", "meta": {"displayValue": "2 - Minor"}},
                "links": {"related": "/api/v0/riskAssessments/luRiskSeverity/2"}
            },
            "severityAfterControl": {
                "data": {"type": "luRiskSeverity", "id": "1", "meta": {"displayValue": "1 - Negligible"}},
                "links": {"related": "/api/v0/riskAssessments/luRiskSeverity/1"}
            },
            "likelihoodSafety": {"data": None},
            "severitySafety": {"data": None},
            "likelihoodAfterControlSafety": {"data": None},
            "severityAfterControlSafety": {"data": None},
            "sys_calculations": {
                "links": {"related": "/api/v0/riskAssessments/identifiedRisk/70001/sys_calculations"}
            }
        },
        "links": {"self": "/api/v0/riskAssessments/identifiedRisk/70001"}
    },
    {
        "id": "70002",
        "type": "identifiedRisk",
        "attributes": {
            "identifiedRiskRefNo": 88802,
            "riskName": "Manual handling, back strain from lifting test equipment",
            "risksToHealth": None,
            "risksToSafety": None,
            "riskRatingBeforeControlMeasuresActions": {
                "text": "Medium High",
                "colour": "#FFA322"
            },
            "technicalControlMeasures": None,
            "organisationalControlMeasures": None,
            "proceduralControlMeasures": None,
            "status": {
                "text": "In Progress",
                "colour": "#FFA500"
            },
            "lastUpdatedOn": "2026-06-02T09:30:00",
            "lastUpdatedBy": "Test User Two",
            "riskRatingAfterControlMeasuresActions": {
                "text": "Medium",
                "colour": "#FFFF00"
            },
            "riskDescription": "Sample fictional description: crew occasionally required to lift equipment cases exceeding recommended weight without assistance.",
            "riskRatingBeforeControlMeasuresactionsSafety": {
                "text": "",
                "colour": None
            },
            "riskRatingafterControlMeasuresactionsSafet": {
                "text": "",
                "colour": None
            },
            "risksToHealthAfter": None,
            "risksToSafetyAfterControlMeasures": None,
            "personalProtectiveEquipment": None,
            "hazardCategoryuserDefinedHazard": "Manual Handling",
            "tickToConfirmAllFieldsCompleted": True,
            "conditionalLogicFormattedText": None,
            "suggestedControlMeasures": "Sample fictional control measures text: use two-person lifting for cases over 20kg, provide manual handling training, use trolleys where available."
        },
        "relationships": {
            "riskAssessmentRefNo": {
                "data": {"type": "riskAssessment", "id": "77002", "meta": {"displayValue": 9998}},
                "links": {"related": "/api/v0/riskAssessments/riskAssessment/77002"}
            },
            "hazardDocument": {"data": None},
            "likelihood": {
                "data": {"type": "luLikelihood", "id": "3", "meta": {"displayValue": "3 - Possible"}},
                "links": {"related": "/api/v0/riskAssessments/luLikelihood/3"}
            },
            "likelihoodAfterControl": {
                "data": {"type": "luLikelihood", "id": "2", "meta": {"displayValue": "2 - Unlikely"}},
                "links": {"related": "/api/v0/riskAssessments/luLikelihood/2"}
            },
            "severity": {
                "data": {"type": "luRiskSeverity", "id": "3", "meta": {"displayValue": "3 - Moderate"}},
                "links": {"related": "/api/v0/riskAssessments/luRiskSeverity/3"}
            },
            "severityAfterControl": {
                "data": {"type": "luRiskSeverity", "id": "2", "meta": {"displayValue": "2 - Minor"}},
                "links": {"related": "/api/v0/riskAssessments/luRiskSeverity/2"}
            },
            "likelihoodSafety": {"data": None},
            "severitySafety": {"data": None},
            "likelihoodAfterControlSafety": {"data": None},
            "severityAfterControlSafety": {"data": None},
            "sys_calculations": {
                "links": {"related": "/api/v0/riskAssessments/identifiedRisk/70002/sys_calculations"}
            }
        },
        "links": {"self": "/api/v0/riskAssessments/identifiedRisk/70002"}
    },
]

IDENTIFIED_RISK_TOTAL_COUNT = 20621  # mimics real prod totalCount seen during testing


# ------------------------------------------------------------------
# Sample data - rebuilt from the REAL field structure of an
# incidentReporting/incidents record (confirmed against an actual
# prod sample), with entirely fictional values. All names, emails,
# addresses, and reference numbers below are fictional. Field names
# are preserved exactly, including the many relationship fields with
# null data (these mirror real optional/unused fields on the record).
# ------------------------------------------------------------------
INCIDENTS_DATA = [
    {
        "id": "50001",
        "type": "incidents",
        "attributes": {
            "dateAndTimeIncidentReported": "2026-02-10T09:15:00",
            "otherReportingPersonType": None,
            "nameOfPersonCompletingThisForm": "Sample Tester One",
            "emailAddress": "sample.tester.one@example-corp.test",
            "phoneNumber": None,
            "dateAndTimeOfIncident": "2026-02-10T08:00:00",
            "otherIncidentLocation": None,
            "exactLocation": "1 Test Avenue, Sampleton, TS1 1AA",
            "incidentDescriptionPleaseDescribeInDetail": "Sample fictional incident: a test employee reported a minor equipment issue during a routine site visit.",
            "otherImmediateCause": None,
            "tickIfYouWishToRemainAnonymous": None,
            "firstDayOfLostTime": None,
            "lastDayOfLostTime": None,
            "otherPurposeOfTravelVehicleUsed": None,
            "registrationNumberOfVehicleInvolved": None,
            "yourVehicleDamageDetails": None,
            "registrationNumberOfThirdPartyVehicle": None,
            "thirdPartyVehicleDamageDetails": None,
            "otherTypeOfDamage": None,
            "howLongDidItTakeForTheBuilding": None,
            "generalFeedbackOnPepPlans": None,
            "generalCommentsOnEvacuation": None,
            "incidentStatus": {"text": "Closed", "colour": "#00FF00"},
            "lastUpdatedOn": "2026-02-14T11:20:00",
            "lastUpdatedBy": "Sample Reviewer One",
            "incidentRefNoPrefix": "TST - 001",
            "severityOfIncident": {"text": "P3", "colour": "#FFFF00"},
            "calculatedDaysOff": None,
            "whereAppropriatePleaseEnterFurtherDetails": "T0001",
            "departmentNotListed": None,
            "otherRetailType": None,
            "conditionalLogic": None,
            "germanWorkRelatedIllHealthConditionalLogic": None,
            "conditionalLogicSupportingDocuments": None,
            "conditionalLogicInjuredPerson": None,
            "reportedByGric": None,
            "reportedByHomeServiceHelpdesk": None
        },
        "relationships": {
            "pleaseSelectWhichDescriptionOfTheIncident": {"data": None},
            "pleaseSelectTheMostAppropriateDescription": {"data": None},
            "reportingPersonType": {
                "data": {"type": "luReportingPersonType", "id": "1", "meta": {"displayValue": "Employee"}},
                "links": {"related": "/api/v0/incidentReporting/luReportingPersonType/1"}
            },
            "incidentLocation": {
                "data": {"type": "luIncidentLocation", "id": "1", "meta": {"displayValue": "Field Service"}},
                "links": {"related": "/api/v0/incidentReporting/luIncidentLocation/1"}
            },
            "incidentSubLocation": {
                "data": {"type": "luIncidentSubLocation", "id": "3", "meta": {"displayValue": "Domestic Property"}},
                "links": {"related": "/api/v0/incidentReporting/luIncidentSubLocation/3"}
            },
            "locationType": {
                "data": {"type": "luLocationDetail", "id": "3", "meta": {"displayValue": "Inside the property"}},
                "links": {"related": "/api/v0/incidentReporting/luLocationDetail/3"}
            },
            "immediateCause": {
                "data": {"type": "luImmediateCause", "id": "9", "meta": {"displayValue": "Property Damage - Customer Property"}},
                "links": {"related": "/api/v0/incidentReporting/luImmediateCause/9"}
            },
            "didTheIncidentOccurWhilstCommutingToOrFrom": {"data": None},
            "didTheEmergencyServicesAttendThisIncident": {
                "data": {"type": "luYesNo", "id": "2", "meta": {"displayValue": "No"}},
                "links": {"related": "/api/v0/incidentReporting/luYesNo/2"}
            },
            "employeeNameOfIllHealthPerson": {"data": None},
            "pleaseSelectTheNatureOfTheWorkRelatedIll": {"data": None},
            "hasTheConditionBeenDiagnosedByADrOr": {"data": None},
            "pleaseSelectTheTypeOfIncident": {"data": None},
            "wasAnAmbulanceCalled": {"data": None},
            "wasThisPersonPlacedOnRestrictedOrLight": {"data": None},
            "whatWasThePurposeOfYourTravelVehicleBeing": {"data": None},
            "wereThereAnyInjuredPersonsIps": {"data": None},
            "ipsTakenByAmbulance": {"data": None},
            "wasYourVehicleDamaged": {"data": None},
            "wasAThirdPartyVehicleInvolved": {"data": None},
            "wasTheThirdPartyVehicleDamaged": {"data": None},
            "typeOfDamage": {
                "data": {"type": "luTypeOfDamage", "id": "2", "meta": {"displayValue": "Services Damage (water, electricity, gas)"}},
                "links": {"related": "/api/v0/incidentReporting/luTypeOfDamage/2"}
            },
            "didTheBuildingEvacuate": {"data": None},
            "wereThereAnyPersonsWithPepPlansInTheBuild": {"data": None},
            "incidentType": {
                "data": {"type": "luIncidentTypeAndDescription", "id": "47", "meta": {"displayValue": "Damage to property arising from work activities"}},
                "links": {"related": "/api/v0/incidentReporting/luIncidentTypeAndDescription/47"}
            },
            "whatWasThePotentialSeverityOfTheIssue": {"data": None},
            "thisALostTimeInjury": {"data": None},
            "retailType": {"data": None},
            "italyIncidentCategory": {"data": None},
            "inailRejected": {"data": None},
            "nonCriticalHitType": {"data": None},
            "luImmediateCause": {"links": {"related": "/api/v0/incidentReporting/incidents/50001/luImmediateCause"}},
            "luWeatherConditions": {"links": {"related": "/api/v0/incidentReporting/incidents/50001/luWeatherConditions"}},
            "luEmergencyServices": {"links": {"related": "/api/v0/incidentReporting/incidents/50001/luEmergencyServices"}},
            "employees": {"links": {"related": "/api/v0/incidentReporting/incidents/50001/employees"}},
            "sys_calculations": {"links": {"related": "/api/v0/incidentReporting/incidents/50001/sys_calculations"}}
        },
        "links": {"self": "/api/v0/incidentReporting/incidents/50001"}
    },
    {
        "id": "50002",
        "type": "incidents",
        "attributes": {
            "dateAndTimeIncidentReported": "2026-03-05T14:22:00",
            "otherReportingPersonType": None,
            "nameOfPersonCompletingThisForm": "Sample Tester Two",
            "emailAddress": "sample.tester.two@example-corp.test",
            "phoneNumber": None,
            "dateAndTimeOfIncident": "2026-03-05T11:00:00",
            "otherIncidentLocation": None,
            "exactLocation": "2 Test Boulevard, Sampleton, TS2 2BB",
            "incidentDescriptionPleaseDescribeInDetail": "Sample fictional incident: a test field engineer temporarily left equipment unattended near a walkway before promptly relocating it to a safe position after being reminded of procedure.",
            "otherImmediateCause": None,
            "tickIfYouWishToRemainAnonymous": None,
            "firstDayOfLostTime": None,
            "lastDayOfLostTime": None,
            "otherPurposeOfTravelVehicleUsed": None,
            "registrationNumberOfVehicleInvolved": None,
            "yourVehicleDamageDetails": None,
            "registrationNumberOfThirdPartyVehicle": None,
            "thirdPartyVehicleDamageDetails": None,
            "otherTypeOfDamage": None,
            "howLongDidItTakeForTheBuilding": None,
            "generalFeedbackOnPepPlans": None,
            "generalCommentsOnEvacuation": None,
            "incidentStatus": {"text": "Closed", "colour": "#00FF00"},
            "lastUpdatedOn": "2026-03-09T10:05:00",
            "lastUpdatedBy": "Sample Reviewer Two",
            "incidentRefNoPrefix": "TST - 002",
            "severityOfIncident": {"text": "P3", "colour": "#FFFF00"},
            "calculatedDaysOff": None,
            "whereAppropriatePleaseEnterFurtherDetails": "T0002",
            "departmentNotListed": None,
            "otherRetailType": None,
            "conditionalLogic": None,
            "germanWorkRelatedIllHealthConditionalLogic": None,
            "conditionalLogicSupportingDocuments": None,
            "conditionalLogicInjuredPerson": None,
            "reportedByGric": None,
            "reportedByHomeServiceHelpdesk": None
        },
        "relationships": {
            "pleaseSelectWhichDescriptionOfTheIncident": {"data": None},
            "pleaseSelectTheMostAppropriateDescription": {"data": None},
            "reportingPersonType": {
                "data": {"type": "luReportingPersonType", "id": "1", "meta": {"displayValue": "Employee"}},
                "links": {"related": "/api/v0/incidentReporting/luReportingPersonType/1"}
            },
            "incidentLocation": {
                "data": {"type": "luIncidentLocation", "id": "1", "meta": {"displayValue": "Field Service"}},
                "links": {"related": "/api/v0/incidentReporting/luIncidentLocation/1"}
            },
            "incidentSubLocation": {
                "data": {"type": "luIncidentSubLocation", "id": "3", "meta": {"displayValue": "Domestic Property"}},
                "links": {"related": "/api/v0/incidentReporting/luIncidentSubLocation/3"}
            },
            "locationType": {
                "data": {"type": "luLocationDetail", "id": "4", "meta": {"displayValue": "Outside the property"}},
                "links": {"related": "/api/v0/incidentReporting/luLocationDetail/4"}
            },
            "immediateCause": {"data": None},
            "didTheIncidentOccurWhilstCommutingToOrFrom": {"data": None},
            "didTheEmergencyServicesAttendThisIncident": {
                "data": {"type": "luYesNo", "id": "2", "meta": {"displayValue": "No"}},
                "links": {"related": "/api/v0/incidentReporting/luYesNo/2"}
            },
            "employeeNameOfIllHealthPerson": {"data": None},
            "pleaseSelectTheNatureOfTheWorkRelatedIll": {"data": None},
            "hasTheConditionBeenDiagnosedByADrOr": {"data": None},
            "pleaseSelectTheTypeOfIncident": {"data": None},
            "wasAnAmbulanceCalled": {"data": None},
            "wasThisPersonPlacedOnRestrictedOrLight": {"data": None},
            "whatWasThePurposeOfYourTravelVehicleBeing": {"data": None},
            "wereThereAnyInjuredPersonsIps": {"data": None},
            "ipsTakenByAmbulance": {"data": None},
            "wasYourVehicleDamaged": {"data": None},
            "wasAThirdPartyVehicleInvolved": {"data": None},
            "wasTheThirdPartyVehicleDamaged": {"data": None},
            "typeOfDamage": {"data": None},
            "didTheBuildingEvacuate": {"data": None},
            "wereThereAnyPersonsWithPepPlansInTheBuild": {"data": None},
            "incidentType": {
                "data": {"type": "luIncidentTypeAndDescription", "id": "48", "meta": {"displayValue": "An event that did not cause harm but had the potential to cause injury or ill health"}},
                "links": {"related": "/api/v0/incidentReporting/luIncidentTypeAndDescription/48"}
            },
            "whatWasThePotentialSeverityOfTheIssue": {
                "data": {"type": "luNearMissSeverity", "id": "3", "meta": {"displayValue": "An incident which did not, but which could have caused harm/damage to an individual or property"}},
                "links": {"related": "/api/v0/incidentReporting/luNearMissSeverity/3"}
            },
            "thisALostTimeInjury": {"data": None},
            "retailType": {"data": None},
            "italyIncidentCategory": {"data": None},
            "inailRejected": {"data": None},
            "nonCriticalHitType": {"data": None},
            "luImmediateCause": {"links": {"related": "/api/v0/incidentReporting/incidents/50002/luImmediateCause"}},
            "luWeatherConditions": {"links": {"related": "/api/v0/incidentReporting/incidents/50002/luWeatherConditions"}},
            "luEmergencyServices": {"links": {"related": "/api/v0/incidentReporting/incidents/50002/luEmergencyServices"}},
            "employees": {"links": {"related": "/api/v0/incidentReporting/incidents/50002/employees"}},
            "sys_calculations": {"links": {"related": "/api/v0/incidentReporting/incidents/50002/sys_calculations"}}
        },
        "links": {"self": "/api/v0/incidentReporting/incidents/50002"}
    },
]

INCIDENTS_TOTAL_COUNT = 6321  # fictional total, deliberately different from real prod count


# ------------------------------------------------------------------
# Sample data - rebuilt from the REAL field structure of a
# riskAssessments/riskAssessment record (confirmed against an actual
# prod sample), with entirely fictional values. All company/brand
# references, employee names, and assessment content below are
# fictional. Field names preserved exactly.
# ------------------------------------------------------------------
RISK_ASSESSMENT_DATA = [
    {
        "id": "80001",
        "type": "riskAssessment",
        "attributes": {
            "riskAssessmentRefNo": 9101,
            "dateCreated": "2026-01-10T00:00:00",
            "otherRiskAssessmentCategory": None,
            "assessmentTitle": "Sample Fictional Assessment - Field Operations Category A, Test Period 2026",
            "assessmentOutlineDescriptionOfActivitiesUnder": "Sample fictional description: this assessment covers a generic set of field operations activities for testing purposes, including standard travel, on-site work, and routine coordination between test teams. No real operational content is contained here - all details are placeholder text for pipeline validation.",
            "assessmentStartDate": "2026-01-10T00:00:00",
            "approximateAssessmentEndDate": None,
            "planForTrip": None,
            "commsPlan": None,
            "accommodation": None,
            "emergencyPlan": None,
            "otherPeopleAtRisk": None,
            "onSiteLocation": None,
            "offSiteProvideDetail": "Sample fictional deployments with a generic test rating.",
            "status": {"text": "Archived", "colour": "#808080"},
            "lastUpdatedOn": "2026-01-20T09:00:00",
            "lastUpdatedBy": "Sample Assessor One",
            "travellerMlreConditionalLogic": None,
            "additionalInformation": False,
            "assessmentOutlinedescriptionOfActivitiesCont": None,
            "peopleAtRiskDetails": None,
            "supportingEvidenceMlreConditionalLogic": None,
            "tickWhenReadyForApproval": False,
            "acknowledgmentRequired": None,
            "numberOfAcknowledgementsRemaining": 0,
            "tickToCloseDownAssessment": None,
            "teamHaveDepartedFromTheCountryOfDeployment": None,
            "trackingClosedDown": None,
            "ppeReturnedAndCheckedInOnCheqroom": None,
            "nokRemovedFromTheDatabase": None,
            "comms": None,
            "equipment": None,
            "training": None,
            "other": None,
            "teamFeedback": None,
            "secondaryHighRiskAssessmentApproval": None
        },
        "relationships": {
            "riskAssessmentCategory": {
                "data": {"type": "luRiskAssessmentCategory", "id": "3", "meta": {"displayValue": "Category A"}},
                "links": {"related": "/api/v0/riskAssessments/luRiskAssessmentCategory/3"}
            },
            "uploadAttachment": {"data": None},
            "isThisAnAdHocOrOnGoingRiskAssessment": {
                "data": {"type": "luAdHocOnGoing", "id": "2", "meta": {"displayValue": "Long Term"}},
                "links": {"related": "/api/v0/riskAssessments/luAdHocOnGoing/2"}
            },
            "emergencyPlanAttachment": {"data": None},
            "updates": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80001/sys_discussionForumPosts/updates"}},
            "feedback": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80001/sys_discussionForumPosts/feedback"}},
            "uploadAttachment2": {"data": None},
            "uploadAttachment3": {"data": None},
            "primaryAssessor": {
                "data": {"type": "employees", "id": "99001", "meta": {"displayValue": "Sample Assessor One"}},
                "links": {"related": "/api/v0/riskAssessments/employees/99001"}
            },
            "jobProfile": {"data": None},
            "nextReviewmonths": {
                "data": {"type": "luFrequencyOfReview", "id": "12", "meta": {"displayValue": 12}},
                "links": {"related": "/api/v0/riskAssessments/luFrequencyOfReview/12"}
            },
            "market": {
                "data": {"type": "luMarket", "id": "1", "meta": {"displayValue": "Test Region"}},
                "links": {"related": "/api/v0/riskAssessments/luMarket/1"}
            },
            "marketAreaResponsible": {
                "data": {"type": "luMarket", "id": "1", "meta": {"displayValue": "Test Region"}},
                "links": {"related": "/api/v0/riskAssessments/luMarket/1"}
            },
            "luPeopleAtRisk": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80001/luPeopleAtRisk"}},
            "mtmGenericAssessment": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80001/mtmGenericAssessment"}},
            "employees": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80001/employees"}},
            "luFreelancers": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80001/luFreelancers"}},
            "luDirectorate": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80001/luDirectorate"}},
            "luLocationOfRisks": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80001/luLocationOfRisks"}},
            "luOnSiteBuilding": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80001/luOnSiteBuilding"}},
            "luHighRiskType": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80001/luHighRiskType"}},
            "luLocationsRa": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80001/luLocationsRa"}},
            "luLessonsIdentified": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80001/luLessonsIdentified"}},
            "sys_calculations": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80001/sys_calculations"}}
        },
        "links": {"self": "/api/v0/riskAssessments/riskAssessment/80001"}
    },
    {
        "id": "80002",
        "type": "riskAssessment",
        "attributes": {
            "riskAssessmentRefNo": 9102,
            "dateCreated": "2026-01-18T00:00:00",
            "otherRiskAssessmentCategory": None,
            "assessmentTitle": "Sample Fictional Assessment - Standard Operations Generic Assessment",
            "assessmentOutlineDescriptionOfActivitiesUnder": "Sample fictional description: this generic assessment covers standard, low-risk test activities. DISTRIBUTION: for use by fictional test teams only. USE: for standard, low-risk sample assignments. EXCEPTIONS: outside these definitions a bespoke assessment must be considered. All content here is placeholder text for pipeline validation purposes only.",
            "assessmentStartDate": "2026-01-18T00:00:00",
            "approximateAssessmentEndDate": None,
            "planForTrip": None,
            "commsPlan": None,
            "accommodation": None,
            "emergencyPlan": None,
            "otherPeopleAtRisk": None,
            "onSiteLocation": None,
            "offSiteProvideDetail": "Sample fictional coverage across generic test locations.",
            "status": {"text": "Archived", "colour": "#808080"},
            "lastUpdatedOn": "2026-02-01T10:00:00",
            "lastUpdatedBy": "Sample Assessor Two",
            "travellerMlreConditionalLogic": None,
            "additionalInformation": False,
            "assessmentOutlinedescriptionOfActivitiesCont": None,
            "peopleAtRiskDetails": None,
            "supportingEvidenceMlreConditionalLogic": None,
            "tickWhenReadyForApproval": True,
            "acknowledgmentRequired": False,
            "numberOfAcknowledgementsRemaining": 0,
            "tickToCloseDownAssessment": None,
            "teamHaveDepartedFromTheCountryOfDeployment": None,
            "trackingClosedDown": None,
            "ppeReturnedAndCheckedInOnCheqroom": None,
            "nokRemovedFromTheDatabase": None,
            "comms": None,
            "equipment": None,
            "training": None,
            "other": None,
            "teamFeedback": None,
            "secondaryHighRiskAssessmentApproval": None
        },
        "relationships": {
            "riskAssessmentCategory": {
                "data": {"type": "luRiskAssessmentCategory", "id": "1", "meta": {"displayValue": "Category B"}},
                "links": {"related": "/api/v0/riskAssessments/luRiskAssessmentCategory/1"}
            },
            "uploadAttachment": {"data": None},
            "isThisAnAdHocOrOnGoingRiskAssessment": {
                "data": {"type": "luAdHocOnGoing", "id": "2", "meta": {"displayValue": "Long Term"}},
                "links": {"related": "/api/v0/riskAssessments/luAdHocOnGoing/2"}
            },
            "emergencyPlanAttachment": {"data": None},
            "updates": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80002/sys_discussionForumPosts/updates"}},
            "feedback": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80002/sys_discussionForumPosts/feedback"}},
            "uploadAttachment2": {"data": None},
            "uploadAttachment3": {"data": None},
            "primaryAssessor": {
                "data": {"type": "employees", "id": "99002", "meta": {"displayValue": "Sample Assessor Two"}},
                "links": {"related": "/api/v0/riskAssessments/employees/99002"}
            },
            "jobProfile": {"data": None},
            "nextReviewmonths": {
                "data": {"type": "luFrequencyOfReview", "id": "12", "meta": {"displayValue": 12}},
                "links": {"related": "/api/v0/riskAssessments/luFrequencyOfReview/12"}
            },
            "market": {
                "data": {"type": "luMarket", "id": "1", "meta": {"displayValue": "Test Region"}},
                "links": {"related": "/api/v0/riskAssessments/luMarket/1"}
            },
            "marketAreaResponsible": {
                "data": {"type": "luMarket", "id": "1", "meta": {"displayValue": "Test Region"}},
                "links": {"related": "/api/v0/riskAssessments/luMarket/1"}
            },
            "luPeopleAtRisk": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80002/luPeopleAtRisk"}},
            "mtmGenericAssessment": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80002/mtmGenericAssessment"}},
            "employees": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80002/employees"}},
            "luFreelancers": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80002/luFreelancers"}},
            "luDirectorate": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80002/luDirectorate"}},
            "luLocationOfRisks": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80002/luLocationOfRisks"}},
            "luOnSiteBuilding": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80002/luOnSiteBuilding"}},
            "luHighRiskType": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80002/luHighRiskType"}},
            "luLocationsRa": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80002/luLocationsRa"}},
            "luLessonsIdentified": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80002/luLessonsIdentified"}},
            "sys_calculations": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80002/sys_calculations"}}
        },
        "links": {"self": "/api/v0/riskAssessments/riskAssessment/80002"}
    },
]

RISK_ASSESSMENT_TOTAL_COUNT = 1777  # fictional total, deliberately different from real prod count


# ------------------------------------------------------------------
# Sample data - rebuilt from the REAL field structure of an
# incidentReporting/injuredPerson record (confirmed against an actual
# prod sample), with entirely fictional values. All names, emails, and
# reference numbers below are fictional. Field names preserved exactly,
# including the array-valued relationships (bodyMap, luInjuriesSustained)
# which carry their own meta.totalCount - a pattern not present on the
# other 3 endpoints.
# ------------------------------------------------------------------
INJURED_PERSON_DATA = [
    {
        "id": "90001",
        "type": "injuredPerson",
        "attributes": {
            "injuredPersonRefNo": 5501,
            "dateCreated": "2026-01-06T00:00:00",
            "injuredPersonName": "Sample Injured Person One",
            "injuredPersonEmailAddress": "sample.injured.one@example-corp.test",
            "injuredPersonJobTitle": None,
            "injuredPersonPhoneNumber": None,
            "employerContactDetails": None,
            "shiftStartTime": "2000-01-01T08:00:00",
            "treatmentDetails": None,
            "whatWasTheNameOfTheHospital": None,
            "firstDayOfLostTime": "2026-01-05T00:00:00",
            "lastDayOfLostTime": "2026-01-07T00:00:00",
            "lastUpdatedOn": "2026-01-06T16:33:08",
            "lastUpdatedBy": "Sample Reviewer One",
            "employerName": None,
            "calculatedDaysOff": 2
        },
        "relationships": {
            "typeOfPerson": {
                "data": {"type": "luTypeOfPerson", "id": "1", "meta": {"displayValue": "Employee"}},
                "links": {"related": "/api/v0/incidentReporting/luTypeOfPerson/1"}
            },
            "employeeName": {
                "data": {"type": "employees", "id": "88801", "meta": {"displayValue": "Sample Injured Person One"}},
                "links": {"related": "/api/v0/incidentReporting/employees/88801"}
            },
            "gender": {
                "data": {"type": "luGender", "id": "1", "meta": {"displayValue": "Male"}},
                "links": {"related": "/api/v0/incidentReporting/luGender/1"}
            },
            "whatTreatmentWasProvided": {
                "data": {"type": "luTreatmentProvided", "id": "1", "meta": {"displayValue": "No Treatment"}},
                "links": {"related": "/api/v0/incidentReporting/luTreatmentProvided/1"}
            },
            "wasThisPersonPlacedOnRestrictedOrLight": {"data": None},
            "thisALostTimeInjury": {
                "data": {"type": "luYesNoUnknown", "id": "1", "meta": {"displayValue": "Yes"}},
                "links": {"related": "/api/v0/incidentReporting/luYesNoUnknown/1"}
            },
            "bodyMap": {
                "data": [{"type": "sys_imageHotSpots", "id": "60001"}],
                "links": {"related": "/api/v0/incidentReporting/injuredPerson/90001/sys_imageHotSpots/bodyMap"},
                "meta": {"totalCount": 1}
            },
            "doesThisIncidentNeedReportingToTheHse": {
                "data": {"type": "luYesNoUnknown", "id": "2", "meta": {"displayValue": "No"}},
                "links": {"related": "/api/v0/incidentReporting/luYesNoUnknown/2"}
            },
            "luInjuriesSustained": {
                "data": [{"type": "luInjuriesSustained", "id": "1", "meta": {"displayValue": "Strain/Sprain - Back"}}],
                "links": {"related": "/api/v0/incidentReporting/injuredPerson/90001/luInjuriesSustained"},
                "meta": {"totalCount": 1}
            },
            "sys_calculations": {
                "links": {"related": "/api/v0/incidentReporting/injuredPerson/90001/sys_calculations"}
            }
        },
        "links": {"self": "/api/v0/incidentReporting/injuredPerson/90001"}
    },
    {
        "id": "90002",
        "type": "injuredPerson",
        "attributes": {
            "injuredPersonRefNo": 5502,
            "dateCreated": "2026-02-11T00:00:00",
            "injuredPersonName": "Sample Injured Person Two",
            "injuredPersonEmailAddress": "sample.injured.two@example-corp.test",
            "injuredPersonJobTitle": None,
            "injuredPersonPhoneNumber": None,
            "employerContactDetails": None,
            "shiftStartTime": "2000-01-01T09:00:00",
            "treatmentDetails": "Sample fictional treatment note: minor first aid applied on site.",
            "whatWasTheNameOfTheHospital": None,
            "firstDayOfLostTime": None,
            "lastDayOfLostTime": None,
            "lastUpdatedOn": "2026-02-12T10:15:00",
            "lastUpdatedBy": "Sample Reviewer Two",
            "employerName": None,
            "calculatedDaysOff": 0
        },
        "relationships": {
            "typeOfPerson": {
                "data": {"type": "luTypeOfPerson", "id": "2", "meta": {"displayValue": "Contractor"}},
                "links": {"related": "/api/v0/incidentReporting/luTypeOfPerson/2"}
            },
            "employeeName": {"data": None},
            "gender": {
                "data": {"type": "luGender", "id": "2", "meta": {"displayValue": "Female"}},
                "links": {"related": "/api/v0/incidentReporting/luGender/2"}
            },
            "whatTreatmentWasProvided": {
                "data": {"type": "luTreatmentProvided", "id": "2", "meta": {"displayValue": "First Aid"}},
                "links": {"related": "/api/v0/incidentReporting/luTreatmentProvided/2"}
            },
            "wasThisPersonPlacedOnRestrictedOrLight": {"data": None},
            "thisALostTimeInjury": {
                "data": {"type": "luYesNoUnknown", "id": "2", "meta": {"displayValue": "No"}},
                "links": {"related": "/api/v0/incidentReporting/luYesNoUnknown/2"}
            },
            "bodyMap": {
                "data": [],
                "links": {"related": "/api/v0/incidentReporting/injuredPerson/90002/sys_imageHotSpots/bodyMap"},
                "meta": {"totalCount": 0}
            },
            "doesThisIncidentNeedReportingToTheHse": {
                "data": {"type": "luYesNoUnknown", "id": "2", "meta": {"displayValue": "No"}},
                "links": {"related": "/api/v0/incidentReporting/luYesNoUnknown/2"}
            },
            "luInjuriesSustained": {
                "data": [{"type": "luInjuriesSustained", "id": "2", "meta": {"displayValue": "Minor Cut/Abrasion"}}],
                "links": {"related": "/api/v0/incidentReporting/injuredPerson/90002/luInjuriesSustained"},
                "meta": {"totalCount": 1}
            },
            "sys_calculations": {
                "links": {"related": "/api/v0/incidentReporting/injuredPerson/90002/sys_calculations"}
            }
        },
        "links": {"self": "/api/v0/incidentReporting/injuredPerson/90002"}
    },
]

INJURED_PERSON_TOTAL_COUNT = 2441  # fictional total, deliberately different from any real prod count


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "service": "mock-shield-api"}), 200, get_standard_headers()


@app.route('/identity/connect/token', methods=['POST'])
def get_token():
    """
    Mock OAuth2 client_credentials token endpoint.

    Unlike a pure "accept anything" mock, this now reads the EXPECTED
    client_id/client_secret from Secret Manager itself (server-side, using
    this Cloud Run service's own runtime service account) and compares
    them against whatever was submitted. This proves Secret Manager
    connectivity genuinely works, not just that credentials were supplied.

    Three distinct failure modes are surfaced separately so a tester can
    tell them apart:
      - 500 secret_manager_unreachable: the mock's service account could
        not read the secret at all (permission denied, destroyed version,
        secret doesn't exist, etc.) - this is the actual connectivity
        problem to fix.
      - 401 invalid_client: Secret Manager was reached fine, but the
        submitted client_id/client_secret didn't match the stored values.
      - 200 success: both credentials matched what Secret Manager returned.
    """
    grant_type = request.form.get('grant_type')
    if grant_type != 'client_credentials':
        return jsonify({"error": "unsupported_grant_type"}), 400, get_standard_headers()

    submitted_client_id = request.form.get('client_id', '')
    submitted_client_secret = request.form.get('client_secret', '')

    try:
        expected_client_id = get_secret_from_manager(CLIENT_ID_SECRET_NAME)
        expected_client_secret = get_secret_from_manager(CLIENT_SECRET_SECRET_NAME)
    except Exception as ex:
        return jsonify({
            "error": "secret_manager_unreachable",
            "error_description": (
                f"Could not read expected credentials from Secret Manager "
                f"(project={SECRET_MANAGER_PROJECT}, secrets="
                f"{CLIENT_ID_SECRET_NAME}/{CLIENT_SECRET_SECRET_NAME}): "
                f"{type(ex).__name__}: {ex}"
            ),
        }), 500, get_standard_headers()

    if submitted_client_id != expected_client_id or submitted_client_secret != expected_client_secret:
        return jsonify({
            "error": "invalid_client",
            "error_description": (
                "Secret Manager was reached successfully, but the submitted "
                "client_id/client_secret did not match the values stored there."
            ),
        }), 401, get_standard_headers()

    return jsonify({
        "access_token": "MOCK-ACCESS-TOKEN-FOR-TESTING",
        "expires_in": 86400,
        "token_type": "Bearer",
    }), 200, get_standard_headers()


@app.route('/api/v0/riskAssessments/identifiedRisk', methods=['GET'])
def get_identified_risk():
    """
    Mock endpoint mimicking InfoExchange (Shield) JSON:API dynamic endpoint
    for the riskAssessments/identifiedRisk table.

    Query parameters supported:
        page[limit]  - max records to return (default 3, capped at sample size)
        page[offset] - offset into the sample set (wraps if beyond sample size)
    """
    # Basic bearer token presence check (does not validate the token value)
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({
            "errors": [{"detail": "Missing or invalid Authorization header"}]
        }), 401, get_standard_headers()

    try:
        limit = int(request.args.get('page[limit]', 3))
    except (TypeError, ValueError):
        limit = 3

    try:
        offset = int(request.args.get('page[offset]', 0))
    except (TypeError, ValueError):
        offset = 0

    # Serve from the small fixed sample set, cycling if offset exceeds it -
    # good enough for pipeline logic testing without needing 20k+ fake rows.
    start = offset % len(IDENTIFIED_RISK_DATA)
    records = (IDENTIFIED_RISK_DATA * 2)[start:start + limit]

    # Optional: run the 4 validation checks against this response before
    # returning it, so a tester can prove they work without a separate
    # relay. ?validate=true runs the checks; ?simulate=<name> deliberately
    # breaks one check (file_type, utf8, json, row_size) to prove it's
    # actually being enforced, not just always passing.
    if request.args.get('validate', '').lower() == 'true':
        simulate = request.args.get('simulate')
        is_valid, error_message, _ = run_self_validation(records, simulate, EXPECTED_CONTENT_TYPE)
        if not is_valid:
            return jsonify({
                "validation_result": "FAILED",
                "error": error_message,
                "simulated_failure": simulate,
            }), 422, get_standard_headers()

    next_offset = offset + limit
    last_offset = IDENTIFIED_RISK_TOTAL_COUNT - limit

    response_body = {
        "data": records,
        "meta": {"totalCount": IDENTIFIED_RISK_TOTAL_COUNT},
        "links": {
            "next": f"/api/v0/riskAssessments/identifiedRisk?page%5Blimit%5D={limit}&page%5Boffset%5D={next_offset}",
            "last": f"/api/v0/riskAssessments/identifiedRisk?page%5Blimit%5D={limit}&page%5Boffset%5D={last_offset}",
        },
    }

    return jsonify(response_body), 200, get_standard_headers()


@app.route('/api/v0/incidentReporting/incidents', methods=['GET'])
def get_incidents():
    """
    Mock endpoint mimicking InfoExchange (Shield) JSON:API dynamic endpoint
    for the incidentReporting/incidents table.

    Query parameters supported:
        page[limit]  - max records to return (default 3, capped at sample size)
        page[offset] - offset into the sample set (wraps if beyond sample size)
    """
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({
            "errors": [{"detail": "Missing or invalid Authorization header"}]
        }), 401, get_standard_headers()

    try:
        limit = int(request.args.get('page[limit]', 3))
    except (TypeError, ValueError):
        limit = 3

    try:
        offset = int(request.args.get('page[offset]', 0))
    except (TypeError, ValueError):
        offset = 0

    start = offset % len(INCIDENTS_DATA)
    records = (INCIDENTS_DATA * 2)[start:start + limit]

    if request.args.get('validate', '').lower() == 'true':
        simulate = request.args.get('simulate')
        is_valid, error_message, _ = run_self_validation(records, simulate, EXPECTED_CONTENT_TYPE)
        if not is_valid:
            return jsonify({
                "validation_result": "FAILED",
                "error": error_message,
                "simulated_failure": simulate,
            }), 422, get_standard_headers()

    next_offset = offset + limit
    last_offset = INCIDENTS_TOTAL_COUNT - limit

    response_body = {
        "data": records,
        "meta": {"totalCount": INCIDENTS_TOTAL_COUNT},
        "links": {
            "next": f"/api/v0/incidentReporting/incidents?page%5Blimit%5D={limit}&page%5Boffset%5D={next_offset}",
            "last": f"/api/v0/incidentReporting/incidents?page%5Blimit%5D={limit}&page%5Boffset%5D={last_offset}",
        },
    }

    return jsonify(response_body), 200, get_standard_headers()


@app.route('/api/v0/riskAssessments/riskAssessment', methods=['GET'])
def get_risk_assessment():
    """
    Mock endpoint mimicking InfoExchange (Shield) JSON:API dynamic endpoint
    for the riskAssessments/riskAssessment table.

    Query parameters supported:
        page[limit]  - max records to return (default 3, capped at sample size)
        page[offset] - offset into the sample set (wraps if beyond sample size)
    """
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({
            "errors": [{"detail": "Missing or invalid Authorization header"}]
        }), 401, get_standard_headers()

    try:
        limit = int(request.args.get('page[limit]', 3))
    except (TypeError, ValueError):
        limit = 3

    try:
        offset = int(request.args.get('page[offset]', 0))
    except (TypeError, ValueError):
        offset = 0

    start = offset % len(RISK_ASSESSMENT_DATA)
    records = (RISK_ASSESSMENT_DATA * 2)[start:start + limit]

    if request.args.get('validate', '').lower() == 'true':
        simulate = request.args.get('simulate')
        is_valid, error_message, _ = run_self_validation(records, simulate, EXPECTED_CONTENT_TYPE)
        if not is_valid:
            return jsonify({
                "validation_result": "FAILED",
                "error": error_message,
                "simulated_failure": simulate,
            }), 422, get_standard_headers()

    next_offset = offset + limit
    last_offset = RISK_ASSESSMENT_TOTAL_COUNT - limit

    response_body = {
        "data": records,
        "meta": {"totalCount": RISK_ASSESSMENT_TOTAL_COUNT},
        "links": {
            "next": f"/api/v0/riskAssessments/riskAssessment?page%5Blimit%5D={limit}&page%5Boffset%5D={next_offset}",
            "last": f"/api/v0/riskAssessments/riskAssessment?page%5Blimit%5D={limit}&page%5Boffset%5D={last_offset}",
        },
    }

    return jsonify(response_body), 200, get_standard_headers()


@app.route('/api/v0/incidentReporting/injuredPerson', methods=['GET'])
def get_injured_person():
    """
    Mock endpoint mimicking InfoExchange (Shield) JSON:API dynamic endpoint
    for the incidentReporting/injuredPerson table.

    Query parameters supported:
        page[limit]  - max records to return (default 3, capped at sample size)
        page[offset] - offset into the sample set (wraps if beyond sample size)
    """
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({
            "errors": [{"detail": "Missing or invalid Authorization header"}]
        }), 401, get_standard_headers()

    try:
        limit = int(request.args.get('page[limit]', 3))
    except (TypeError, ValueError):
        limit = 3

    try:
        offset = int(request.args.get('page[offset]', 0))
    except (TypeError, ValueError):
        offset = 0

    start = offset % len(INJURED_PERSON_DATA)
    records = (INJURED_PERSON_DATA * 2)[start:start + limit]

    if request.args.get('validate', '').lower() == 'true':
        simulate = request.args.get('simulate')
        is_valid, error_message, _ = run_self_validation(records, simulate, EXPECTED_CONTENT_TYPE)
        if not is_valid:
            return jsonify({
                "validation_result": "FAILED",
                "error": error_message,
                "simulated_failure": simulate,
            }), 422, get_standard_headers()

    next_offset = offset + limit
    last_offset = INJURED_PERSON_TOTAL_COUNT - limit

    response_body = {
        "data": records,
        "meta": {"totalCount": INJURED_PERSON_TOTAL_COUNT},
        "links": {
            "next": f"/api/v0/incidentReporting/injuredPerson?page%5Blimit%5D={limit}&page%5Boffset%5D={next_offset}",
            "last": f"/api/v0/incidentReporting/injuredPerson?page%5Blimit%5D={limit}&page%5Boffset%5D={last_offset}",
        },
    }

    return jsonify(response_body), 200, get_standard_headers()


# ==============================================================================
# Test-data landing helper
#
# Purpose: this mock has no real Cloud Run relay in front of it in dev (there
# is no Shield sandbox tenant and no deployed shield-api-file-extract in this
# environment), so nothing would normally perform the
# fetch -> convert_to_ndjson -> gzip -> upload-to-GCS steps that happen in
# prod. This section does exactly those same steps, using this mock's own
# sample data as the source instead of a real Shield API call, and lands the
# result at the same GCS path/filename convention the real pipeline uses -
# so a Control-M job pointed at this bucket sees the same shape of file it
# would see in production, and the downstream ingest/cc jobs can be run
# against it unmodified.
#
# This intentionally does NOT touch the mock's HTTP endpoints above (they
# keep returning the raw JSON:API envelope, as the real Shield API does) -
# this is a separate, additional code path used only to seed GCS for testing.
# ==============================================================================

FEED_CONFIG = {
    "identifiedrisk": {
        "data_fn": lambda: IDENTIFIED_RISK_DATA,
        "gcs_folder": "identifiedrisk_list_all",
        "filename_prefix": "SHIELD_IDENTIFIEDRISK_LIST_ALL",
    },
    "incidents": {
        "data_fn": lambda: INCIDENTS_DATA,
        "gcs_folder": "incidents_list_all",
        "filename_prefix": "SHIELD_INCIDENTS_LIST_ALL",
    },
    "riskassessment": {
        "data_fn": lambda: RISK_ASSESSMENT_DATA,
        "gcs_folder": "riskassessment_list_all",
        "filename_prefix": "SHIELD_RISKASSESSMENT_LIST_ALL",
    },
    "injuredperson": {
        "data_fn": lambda: INJURED_PERSON_DATA,
        "gcs_folder": "injuredperson_list_all",
        "filename_prefix": "SHIELD_INJUREDPERSON_LIST_ALL",
    },
}


def _gzip_bytes(data_bytes):
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode="wb") as gz:
        gz.write(data_bytes)
    return out.getvalue()


def _upload_bytes_to_gcs(bucket_name, blob_path, data_bytes):
    """Uploads raw bytes to GCS. Requires google-cloud-storage and ADC/creds
    available in the environment this is run from (e.g. gcloud auth
    application-default login, or a service account on the box)."""
    from google.cloud import storage
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    blob.upload_from_string(data_bytes)
    return f"gs://{bucket_name}/{blob_path}"


def land_test_file(feed_key, bucket_env, page_num=1, timestamp=None):
    """
    Generates one landing-ready gzipped NDJSON file for the given feed from
    this mock's own sample data, and uploads it to
    gs://skyuk-uk-lan-tds-shield-is-<bucket_env>/<feed>/landing/<filename>.json.gz
    exactly as the real pipeline would name and shape it.
    """
    if feed_key not in FEED_CONFIG:
        raise ValueError(f"Unknown feed_key '{feed_key}'. Valid: {list(FEED_CONFIG.keys())}")

    cfg = FEED_CONFIG[feed_key]
    records = cfg["data_fn"]()

    # Same conversion the real relay (app.py) performs: one record per line, unwrapped
    ndjson_bytes = convert_to_ndjson(records)
    gzipped = _gzip_bytes(ndjson_bytes)

    ts = timestamp or datetime.utcnow().strftime('%Y%m%d%H%M%S')
    filename = f"{cfg['filename_prefix']}_{ts}_{page_num}.json.gz"
    bucket_name = f"skyuk-uk-lan-tds-shield-is-{bucket_env}"
    blob_path = f"{cfg['gcs_folder']}/landing/{filename}"

    gcs_uri = _upload_bytes_to_gcs(bucket_name, blob_path, gzipped)
    return {
        "feed": feed_key,
        "records_landed": len(records),
        "gcs_uri": gcs_uri,
    }


@app.route('/mock_land_test_file', methods=['POST'])
def mock_land_test_file():
    """
    Test-only endpoint: lands one gzipped NDJSON file to GCS for a given
    feed, using this mock's own sample data, in the exact shape/path/naming
    convention the real pipeline uses.

    Body: {"feed": "identifiedrisk", "bucket_env": "dev"}
    feed one of: identifiedrisk | incidents | riskassessment | injuredperson
    """
    data = request.get_json(silent=True) or {}
    feed_key = data.get("feed")
    bucket_env = data.get("bucket_env", os.environ.get("BUCKET_ENV", "dev"))

    if not feed_key:
        return jsonify({"error": "Missing required field: feed"}), 400

    try:
        result = land_test_file(feed_key, bucket_env)
        return jsonify({"status": "success", **result}), 200
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


if __name__ == '__main__':
    import sys
    # CLI mode: land test files directly without running the Flask server.
    # Usage: python3 main.py --land-test-data [feed] [bucket_env]
    #   python3 main.py --land-test-data identifiedrisk dev
    #   python3 main.py --land-test-data all dev
    if len(sys.argv) > 1 and sys.argv[1] == '--land-test-data':
        feed_arg = sys.argv[2] if len(sys.argv) > 2 else 'all'
        env_arg = sys.argv[3] if len(sys.argv) > 3 else os.environ.get('BUCKET_ENV', 'dev')
        feeds_to_land = list(FEED_CONFIG.keys()) if feed_arg == 'all' else [feed_arg]
        for fk in feeds_to_land:
            result = land_test_file(fk, env_arg)
            print(f"{result['feed']}: landed {result['records_landed']} records -> {result['gcs_uri']}")
    else:
        app.run(host='0.0.0.0', port=8080, debug=True)
