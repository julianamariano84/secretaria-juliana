Railway deployment notes (minimal)

1) Create a new project on Railway and connect your GitHub repo or push via the Railway CLI.

2) Set environment variables in the Railway project settings (do NOT store secrets in the repo):
   - SECRET_KEY
   - PORT (Railway provides one; you can leave blank or use default 5000)
   - ZAPI_URL (include /send-text exact path)
   - ZAP_TOKEN (instance token)
   - CLIENT_TOKEN (client token — if required by your Z-API instance)
   - OPENAI_API_KEY (if using AI features)

3) Build settings
   - Railway will use the Procfile. Ensure Python build is selected.
   - requirements.txt is present and lists required packages.

4) Health check
   - After deployment, visit /health to confirm the app responds with {"status":"ok"}.

5) Testing outbound
   - Use /api/send to trigger send_text via the web UI or curl and verify Z-API outgoing messages.

Notes
   - Keep production tokens in Railway environment variables only.
   - If you need to install Playwright browsers, add build steps or remove Playwright from production requirements.
