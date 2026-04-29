# Deploy VoterPath on Google Cloud Run

This guide deploys the FastAPI app in `backend.py` (serving `index.html`) to Google Cloud Run.

## 1) Prerequisites

- A Google Cloud project with billing enabled.
- `gcloud` CLI installed and authenticated.
- Cloud Run and Artifact Registry APIs enabled.
- Your Gemini API key ready (do not hardcode in code).

## 2) Files included for deployment

This repo now includes:

- `Dockerfile`
- `requirements.txt`
- `.dockerignore`

Cloud Run will use these to build and run the container.

## 3) Set your project and region

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud config set run/region asia-south1
```

You can change region if needed (for example `us-central1`).

## 4) Enable required APIs

```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
```

## 5) Deploy to Cloud Run (source-based build)

From this project root:

```bash
gcloud run deploy voterpath \
  --source . \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY=YOUR_GEMINI_API_KEY
```

Notes:
- Service name is `voterpath` (change if you want).
- `--allow-unauthenticated` makes the app public.
- `GEMINI_API_KEY` is required by `backend.py`.

## 6) Verify deployment

After deploy, Cloud Run prints a service URL. Open it in browser.

You can also verify with:

```bash
gcloud run services describe voterpath --region asia-south1 --format='value(status.url)'
```

Health/API quick checks:

```bash
curl https://YOUR_CLOUD_RUN_URL/api/ministers
curl https://YOUR_CLOUD_RUN_URL/api/election-dates
```

## 7) Update an existing deployment

Run the same deploy command again after code changes:

```bash
gcloud run deploy voterpath --source . --platform managed --allow-unauthenticated
```

If env vars change, include `--set-env-vars` again.

## 8) View logs

```bash
gcloud run services logs read voterpath --region asia-south1 --limit 100
```

## 9) Optional: safer secret handling (recommended)

Instead of passing key directly in command, store in Secret Manager:

```bash
echo -n "YOUR_GEMINI_API_KEY" | gcloud secrets create GEMINI_API_KEY --data-file=-
gcloud run deploy voterpath \
  --source . \
  --allow-unauthenticated \
  --set-secrets GEMINI_API_KEY=GEMINI_API_KEY:latest
```

This is better for production security.
