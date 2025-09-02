param(
    [string]$Message = "chore: sync workspace (auto push)",
    [string]$Remote = 'origin',
    [string]$Branch = 'main'
)

Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force
Write-Host "Staging all changes..."
git add -A

# Only commit if there are staged changes
$diff = git diff --cached --name-only
if ($diff) {
    Write-Host "Committing with message: $Message"
    git commit -m $Message
} else {
    Write-Host "No changes to commit."
}

Write-Host "Pushing to $Remote/$Branch..."
try {
    git push $Remote $Branch
    Write-Host "Push finished."
} catch {
    Write-Host "Push failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
