# Mock Shield (InfoExchange) API

Mimics the real InfoExchange (EcoOnline Shield) API for testing the
`riskAssessments/identifiedRisk` extraction pipeline in dev, since EcoOnline
does not provide a separate dev/sandbox tenant - only production exists.

A small Flask app, deployed to Cloud Run via Cloud Build, serving canned
JSON:API-shaped responses so the extraction pipeline's logic (auth flow,
request construction, pagination, response parsing) can be tested
repeatably without hitting the real prod API.

## Endpoints

| Method | Path                                     | Purpose                                   |
| ------ | ----------------------------------------- | ------------------------------------------ |
| POST   | `/identity/connect/token`                 | Mock OAuth2 `client_credentials` token issuance (any client_id/secret accepted) |
| GET    | `/api/v0/riskAssessments/identifiedRisk`  | Mock JSON:API data endpoint, supports `page[limit]` / `page[offset]` |
| GET    | `/health`                                 | Health check |

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

## Point the extraction script at the mock

The `infoexchange_riskassessments_identifiedrisk_get.bash` script supports a
`SHIELD_BASE_URL` override, so once this is deployed:

```bash
export SHIELD_BASE_URL="https://<cloud-run-service-url>"
export CLIENT_ID="anything"       # not validated by the mock
export CLIENT_SECRET="anything"   # not validated by the mock
bash infoexchange_riskassessments_identifiedrisk_get.bash
```

Since the Cloud Run URL is on `*.run.app`, it should already be reachable
through your dev environment's proxy without needing a `no_proxy` exception
(unlike `shield.info-exchange.com`, which required one).

Unset `SHIELD_BASE_URL` to point the same script back at the real prod API.

## Next steps

Once this is validated for `identifiedRisk`, the same pattern (add a route
in `main.py`, add sample data) can be extended to cover:
- `riskAssessments/riskAssessment`
- `incidentReporting/incidents`
