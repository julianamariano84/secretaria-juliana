Railway + Z-API integration guide

This document shows steps to deploy the app to Railway and wire Z-API to send webhooks to the deployed app.

Prerequisites
- A Railway account and the Railway CLI (optional).
- A GitHub repo (this repo is already configured).
- A Z-API account with access to set a webhook URL and token.

Steps

1) Push repo to GitHub
- Ensure your changes are committed and pushed to `main` branch.

2) Create a Railway project
- Log in to Railway and click "New Project" → "Deploy from GitHub".
- Choose the repository and branch (`main`).

3) Environment variables
- In Railway, open Project Settings → Variables and add the required env vars:
  - `SECRET_KEY` (Flask secret key)
  - `OPENAI_API_KEY` (if using OpenAI)
  - `OPENAI_MODEL` (optional)
  - `ZAPI_URL` (base URL for Z-API API)
  - `ZAPI_TOKEN` (token for sending messages / authenticating)
  - `TERAPEE_BASE_URL`, `TERAPEE_UI_USER`, `TERAPEE_UI_PASS` (if using Terapee)
  - `DEBUG_ZAPI` (set to `1` to enable debug stub for local testing)

4) Build & Start Command
- Railway usually detects Python app. Make sure `Procfile` exists (this repo includes one):
  - `web: gunicorn -w 4 -b 0.0.0.0:$PORT app:app`
- Leave Build and Start fields empty so Railway uses defaults.

5) Playwright / Browsers
- If your app uses Playwright in production, open the Service → Settings → Build and add a pre-build command to install system deps and run:
  - `python -m pip install -r requirements.txt`
  - `python -m playwright install --with-deps`
- Alternatively, run Playwright steps in a separate Railway worker.

6) Add a webhook in Z-API
- After Railway deploys, copy the project's domain (e.g., `https://<your-project>.up.railway.app`)
- In Z-API dashboard, set the webhook URL to `https://<your-project>.up.railway.app/webhook` (or the path the app expects).
- Configure any authentication headers in Z-API (if needed) to match your app (e.g., `X-SECRET: <your-secret>`).

7) Test
- Use Z-API test webhook sender or curl to POST a sample message to the webhook endpoint and verify logs in Railway.

Scripts
- You can use Railway CLI to create a project and set variables; see Railway docs.

Notes
- For production, prefer storing persistent data in a DB instead of file-backed JSON in `data/`.
- If Playwright is heavy for Railway, consider extracting UI automation to an external worker or scheduled job.

*** End of guide
