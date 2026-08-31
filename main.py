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
# Sample data - mimics the JSON:API shape described in the EcoOnline
# "Info Exchange API Functionality" guide for a riskAssessments /
# identifiedRisk table record.
# ------------------------------------------------------------------
IDENTIFIED_RISK_DATA = [
    {
        "id": "1001",
        "type": "identifiedRisk",
        "attributes": {
            "riskTitle": "Slip hazard - warehouse floor",
            "riskCategory": "Health & Safety",
            "status": {"name": "Open", "colour": "#ff0000"},
            "likelihood": 3,
            "impact": 4,
            "riskScore": 12,
            "dateIdentified": "2026-06-01T09:00:00",
            "dateReviewed": "2026-07-15T09:00:00",
            "location": {"latitude": 51.5074, "longitude": -0.1278},
            "description": "Wet floor near loading bay causing slip hazard during rain.",
        },
        "links": {
            "self": "/api/v0/riskAssessments/identifiedRisk/1001"
        },
    },
    {
        "id": "1002",
        "type": "identifiedRisk",
        "attributes": {
            "riskTitle": "Unsecured cabling - office floor 3",
            "riskCategory": "Health & Safety",
            "status": {"name": "In Progress", "colour": "#ffa500"},
            "likelihood": 2,
            "impact": 2,
            "riskScore": 4,
            "dateIdentified": "2026-05-20T14:30:00",
            "dateReviewed": None,
            "location": {"latitude": None, "longitude": None},
            "description": "Loose cabling across walkway poses trip hazard.",
        },
        "links": {
            "self": "/api/v0/riskAssessments/identifiedRisk/1002"
        },
    },
    {
        "id": "1003",
        "type": "identifiedRisk",
        "attributes": {
            "riskTitle": "Fire exit obstruction - store room B",
            "riskCategory": "Fire Safety",
            "status": {"name": "Closed", "colour": "#00ff00"},
            "likelihood": 1,
            "impact": 5,
            "riskScore": 5,
            "dateIdentified": "2026-03-11T08:00:00",
            "dateReviewed": "2026-04-01T08:00:00",
            "location": {"latitude": 51.5155, "longitude": -0.1426},
            "description": "Boxes stacked in front of fire exit, now cleared.",
        },
        "links": {
            "self": "/api/v0/riskAssessments/identifiedRisk/1003"
        },
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

    response_body = {
        "data": records,
        "meta": {"totalCount": TOTAL_COUNT},
        "lastPageUri": f"/api/v0/riskAssessments/identifiedRisk?page[offset]={TOTAL_COUNT - limit}",
    }

    return jsonify(response_body), 200, get_standard_headers()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
