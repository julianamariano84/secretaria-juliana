<#
railway_full.ps1

Helper to automate Railway project link/init, import variables from .env,
deploy and optionally follow logs. Run this locally (PowerShell / pwsh).

Usage examples:
  # interactive link and import env, then deploy and follow logs
  pwsh ./deploy/railway_full.ps1 -EnvFile ".env" -AutoDeploy -FollowLogs

  # create a named project, import env but don't deploy automatically
  pwsh ./deploy/railway_full.ps1 -ProjectName "my-secretaria" -EnvFile ".env"

Notes:
 - Requires Railway CLI installed and logged in (`railway login`).
 - This script runs interactive commands where necessary and won't bypass auth.
 - Review the commands the script will run before executing in production.
#>

param(
    [string]$ProjectName = "",
    [string]$EnvFile = ".env",
    [switch]$AutoDeploy,
    [switch]$FollowLogs
)

function Assert-RailwayCli {
    if (-not (Get-Command railway -ErrorAction SilentlyContinue)) {
        Write-Error "Railway CLI not found. Install from https://railway.app/docs/cli and run 'railway login'"
        exit 1
    }
}

function Import-EnvFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        Write-Host "Env file '$Path' not found, skipping import." -ForegroundColor Yellow
        return
    }
    Write-Host "Importing variables from $Path" -ForegroundColor Cyan
    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith('#')) {
            $pair = $line -split '=',2
            if ($pair.Count -ge 2) {
                $k = $pair[0].Trim()
                $v = $pair[1].Trim()
                if ($k) {
                    Write-Host "railway variables set $k=***" -ForegroundColor DarkGray
                    railway variables set $k $v
                }
            }
        }
    }
}

Assert-RailwayCli

if ($ProjectName) {
    Write-Host "Initializing or selecting project: $ProjectName" -ForegroundColor Green
    # railway init is interactive if project exists; it will select existing if name matches
    railway init $ProjectName
} else {
    Write-Host "Linking repository to an existing Railway project (interactive)..." -ForegroundColor Green
    railway link
}

if (Test-Path $EnvFile) {
    Import-EnvFile -Path $EnvFile
} else {
    Write-Host "Env file '$EnvFile' not found, skipping variable import." -ForegroundColor Yellow
}

if ($AutoDeploy) {
    Write-Host "Starting deploy (this may open interactive prompts)..." -ForegroundColor Cyan
    # Attempt to deploy; this will use the currently linked project
    railway up --build
}

if ($FollowLogs) {
    Write-Host "Following logs (Ctrl+C to stop)" -ForegroundColor Cyan
    railway logs -f
}

Write-Host "railway_full.ps1 finished." -ForegroundColor Green
