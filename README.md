# Mock Shield (InfoExchange) API

Mimics the real InfoExchange (EcoOnline Shield) API for testing the
Shield extraction pipeline in dev, since EcoOnline does not provide a
separate dev/sandbox tenant - only production exists.

A small Flask app, deployed to Cloud Run via Cloud Build, serving canned
JSON:API-shaped responses so the extraction pipeline's logic (auth flow,
request construction, pagination, response parsing) can be tested
repeatably without hitting the real prod API.

## Endpoints

| Method | Path                                       | Purpose                                   |
| ------ | ------------------------------------------- | ------------------------------------------ |
| POST   | `/identity/connect/token`                   | Mock OAuth2 `client_credentials` token issuance (any client_id/secret accepted) |
| GET    | `/api/v0/riskAssessments/identifiedRisk`    | Mock JSON:API data endpoint, supports `page[limit]` / `page[offset]` |
| GET    | `/api/v0/incidentReporting/incidents`       | Mock JSON:API data endpoint, supports `page[limit]` / `page[offset]` |
| GET    | `/api/v0/riskAssessments/riskAssessment`    | Mock JSON:API data endpoint, supports `page[limit]` / `page[offset]` |
| GET    | `/health`                                   | Health check |

## Run locally

```bash
pip install -r requirements.txt
python3 main.py
# listens on http://0.0.0.0:8080
```

## Deploy to Cloud Run

```bash
# 1. Build & push the image
gcloud builds submit --config cloudbuild-build.yaml .

# 2. Deploy to Cloud Run
gcloud builds submit --config cloudbuild-deploy.yaml .
```

Confirm/adjust the substitution values in both `cloudbuild-build.yaml` and
`cloudbuild-deploy.yaml` (`_REPO_NAME`, `_REPO_PROJ`, service account) to
match your actual Artifact Registry repo and build/run service accounts
before running.

## Point the extraction scripts at the mock

Each endpoint has its own mock-only test script (no Secret Manager code
path - `CLIENT_ID`/`CLIENT_SECRET` must be supplied as dummy environment
values):

- `shield_riskassessments_identifiedrisk_get_mocktest.bash`
- `shield_incidentreporting_incidents_get_mocktest.bash`
- `shield_riskassessments_riskassessment_get_mocktest.bash`

Once this mock is deployed:

```bash
export SHIELD_BASE_URL="https://<cloud-run-service-url>"
export CLIENT_ID="anything"       # not validated by the mock
export CLIENT_SECRET="anything"   # not validated by the mock
export BUCKET_ENV=dev             # required - drives the GCS destination bucket

bash shield_riskassessments_identifiedrisk_get_mocktest.bash
bash shield_incidentreporting_incidents_get_mocktest.bash
bash shield_riskassessments_riskassessment_get_mocktest.bash
```

Since the Cloud Run URL is on `*.run.app`, it should already be reachable
through your dev environment's proxy without needing a `no_proxy` exception
(unlike `shield.info-exchange.com`, which required one).

Each script refuses to run if `SHIELD_BASE_URL` points at a real
`info-exchange.com` domain, so they can never accidentally hit real Shield
credentials or data.

## Status

All 3 Shield endpoints used by the production pipeline are mocked here:
`riskAssessments/identifiedRisk`, `incidentReporting/incidents`, and
`riskAssessments/riskAssessment`. No further endpoints are currently
planned.
