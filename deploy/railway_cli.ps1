<#
Railway CLI helper (PowerShell)

Prerequisites:
- Install Railway CLI: https://railway.app/docs/cli
- Be logged in: `railway login`
- Git remote configured and pushed to GitHub

Usage:
.
  .\deploy\railway_cli.ps1 -ProjectName "my-secretaria" -EnvFile ".env"

This script will:
- create or link a Railway project
- set environment variables from a local `.env` file (if provided)

#>

param(
    [string]$ProjectName = "",
    [string]$EnvFile = ".env"
)

function Assert-RailwayCli {
    if (-not (Get-Command railway -ErrorAction SilentlyContinue)) {
        Write-Error "Railway CLI not found. Install from https://railway.app/docs/cli and run 'railway login'"
        exit 1
    }
}

Assert-RailwayCli

if ([string]::IsNullOrWhiteSpace($ProjectName)) {
    Write-Host "No project name provided. You will be prompted to select/create a project interactively." -ForegroundColor Yellow
}

# Optional: create a new project
if ($ProjectName -ne "") {
    Write-Host "Creating Railway project '$ProjectName' (if it exists, Railway will select it)." -ForegroundColor Cyan
    railway init $ProjectName
} else {
    Write-Host "Running 'railway link' to associate local repo with a project (interactive)." -ForegroundColor Cyan
    railway link
}

if (Test-Path $EnvFile) {
    Write-Host "Setting environment variables from $EnvFile" -ForegroundColor Green
    Get-Content $EnvFile | Where-Object { $_ -match "^\s*[^#].*=.*" } | ForEach-Object {
        $pair = $_ -split "=",2
        $key = $pair[0].Trim()
        $val = $pair[1].Trim()
        if ($key) {
            Write-Host "railway variables set $key=***" -ForegroundColor DarkGray
            railway variables set $key $val
        }
    }
} else {
    Write-Host "Env file '$EnvFile' not found. Skipping variable import." -ForegroundColor Yellow
}

Write-Host "Deployment helper finished. Use 'railway up' to deploy or visit Railway console." -ForegroundColor Green
