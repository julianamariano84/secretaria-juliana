Deploying to Railway

Overview
- This repo is a Flask app. Railway can build and run it using Python.

Preflight
- Ensure a `requirements.txt` exists (this project has one).
- Add needed environment variables in Railway (see `env` below).
- If you use Playwright in production, the Railway environment must have browsers
  installed — consider using the Terapee API instead or move Playwright to
  an external worker with a headful VM.

Railway setup
1. Create a new project on Railway and connect the repo.
2. In the Railway project settings, set the Environment Variables used by the app:
   - FLASK_ENV=production
   - SECRET_KEY=<your-secret>
   - ZAPI_URL, ZAPI_TOKEN (if you use Z-API in production)
   - OPENAI_API_KEY (if you want AI features)
   - TERAPEE_BASE_URL, TERAPEE_UI_USER, TERAPEE_UI_PASS (only if using Playwright)
   - DEBUG_ZAPI=0
3. Set the Build Command: (Railway will detect Python projects automatically) leave blank or use:
   pip install -r requirements.txt
4. Set the Start Command: leave blank (Railway will use the `Procfile` by default)

Notes
- Port: Railway sets $PORT automatically; the `Procfile` uses it.
- Playwright: installing browsers may require extra steps not covered here.
- For dev/test deployments, set `DEBUG_ZAPI=1` and `DEBUG_WEBHOOK=1`.

Troubleshooting
- If the app fails to boot, check Railway build logs for failing pip installs
  and fix any native dependency requirements.
- To avoid Playwright in production builds, remove `playwright` from
  `requirements.txt` and run Playwright-based tasks in a separate worker or locally.
