Quick steps to deploy with Railway CLI and configure Z-API webhook

1) Install Railway CLI and log in
- https://railway.app/docs/cli
- `railway login`

2) Link or create a project
- Create and link interactively: `railway link` or create and set the name: `railway init my-secretaria`

3) Import env vars from your local `.env` (script provided)
- Run PowerShell helper to set variables from `.env`:
  - `pwsh ./deploy/railway_cli.ps1 -ProjectName "my-secretaria" -EnvFile ".env"`

4) Deploy
- `railway up` (or use the Railway console)

5) Configure Z-API webhook
- After deploy, copy the service URL from Railway (e.g. `https://<proj>.up.railway.app`)
- In Z-API dashboard, set webhook URL to `https://<proj>.up.railway.app/webhook`
- If your app expects a header like `X-SECRET`, set it in Z-API webhook headers to your `SECRET_KEY`.

6) Test webhook
- Use Z-API test webhook sender or `curl` to POST sample payload.

Notes
- The script uses `railway variables set` which requires CLI auth.
- For macOS/Linux use the same script via PowerShell Core (`pwsh`).
