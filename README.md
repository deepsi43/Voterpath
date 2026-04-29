# VoterPath

VoterPath is an election information assistant for Andhra Pradesh, built with a FastAPI backend and a static frontend.

## Live Demo (Cloud Run URL - Mandatory)

Replace this with your deployed public URL before submission:

- **Cloud Run URL:** `https://REPLACE-WITH-YOUR-CLOUD-RUN-URL`

> Submission note: Your dashboard submission is valid only with a live public Cloud Run URL.

## Project Structure

- `backend.py` - FastAPI server and API routes.
- `index.html` - Frontend served as static content by FastAPI.
- `DEPLOY_CLOUD_RUN.md` - Step-by-step Cloud Run deployment doc.
- `PROMPTING_LOGIC.md` - Prompt design and agent behavior documentation.
- `Dockerfile` / `requirements.txt` / `.dockerignore` - Deployment artifacts.

## Local Run

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn backend:app --reload --host 0.0.0.0 --port 8000
```

Open: `http://localhost:8000`

## Cloud Run Deployment

Use the full guide in `DEPLOY_CLOUD_RUN.md`.

Quick command:

```bash
gcloud run deploy voterpath \
  --source . \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY=YOUR_GEMINI_API_KEY
```

## GitHub Documentation Checklist

- [ ] Public Cloud Run URL added above.
- [ ] `PROMPTING_LOGIC.md` is present and updated.
- [ ] `DEPLOY_CLOUD_RUN.md` steps are accurate for your final deployment.
- [ ] No secrets committed (`.env`, API keys, credentials).
- [ ] Optional: Add screenshots/GIF of app in action.

## LinkedIn Story (Submission Ready Template)

Use this post format:

```text
Built and deployed VoterPath - an AI-powered Andhra Pradesh election assistant.

What it does:
- Real-time politician profile generation
- Election timeline and constituency insights
- Interactive chatbot for voter information

Tech stack:
FastAPI, LangChain, Gemini, DuckDuckGo tools, Cloud Run

Live demo:
[PASTE YOUR CLOUD RUN URL]

#GoogleCloud #CloudRun #GenerativeAI #Hackathon #BuildInPublic

@Google for Developers @Hack2skill
```

## License

Add your preferred license (MIT/Apache-2.0) if required by submission rules.
