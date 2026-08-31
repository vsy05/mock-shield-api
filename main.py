"""
Mock InfoExchange (Shield) API for Development/Testing
Mimics the real InfoExchange (EcoOnline Shield) API behavior for testing the
riskAssessments/identifiedRisk extraction pipeline in dev, since EcoOnline
does not provide a separate dev/sandbox tenant.

Endpoints mocked:
    POST /identity/connect/token
        - OAuth2 client_credentials grant (any client_id/client_secret accepted)
    GET  /api/v0/riskAssessments/identifiedRisk
        - JSON:API-shaped response with sample records
        - Supports page[limit] / page[offset] query params

Usage (local):
    python3 main.py
    (listens on 0.0.0.0:8080)

Usage (once deployed to Cloud Run):
    SHIELD_BASE_URL=https://<cloud-run-url> bash infoexchange_riskassessments_identifiedrisk_get.bash
"""

from flask import Flask, jsonify, request
from datetime import datetime
import uuid

app = Flask(__name__)


def get_standard_headers():
    """Generate standard response headers matching real API format."""
    return {
        'Date': datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT'),
        'Content-Type': 'application/vnd.api+json',
        'Connection': 'keep-alive',
        'Cache-Control': 'no-store',
        'X-Request-Id': uuid.uuid4().hex,
    }


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

TOTAL_COUNT = 20621  # mimics real prod totalCount seen during testing


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "service": "mock-shield-api"}), 200, get_standard_headers()


@app.route('/identity/connect/token', methods=['POST'])
def get_token():
    """
    Mock OAuth2 client_credentials token endpoint.
    Accepts any client_id/client_secret - this mock does not validate
    credentials, it only tests the pipeline's request/response handling.
    """
    grant_type = request.form.get('grant_type')
    if grant_type != 'client_credentials':
        return jsonify({"error": "unsupported_grant_type"}), 400, get_standard_headers()

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

    next_offset = offset + limit
    last_offset = TOTAL_COUNT - limit

    response_body = {
        "data": records,
        "meta": {"totalCount": TOTAL_COUNT},
        "links": {
            "next": f"/api/v0/riskAssessments/identifiedRisk?page%5Blimit%5D={limit}&page%5Boffset%5D={next_offset}",
            "last": f"/api/v0/riskAssessments/identifiedRisk?page%5Blimit%5D={limit}&page%5Boffset%5D={last_offset}",
        },
    }

    return jsonify(response_body), 200, get_standard_headers()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
