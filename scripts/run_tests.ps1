# Run tests helper for this project
# Usage: open PowerShell in repo root and run: .\scripts\run_tests.ps1

$python = $env:PYTHON_PATH
if (-not $python -or $python -eq '') {
    $python = 'C:\Users\mario\AppData\Local\Programs\Python\Python313\python.exe'
}

Write-Host "Using python: $python"

# Install requirements (safe to run repeatedly)
& $python -m pip install -r ..\requirements.txt

# Run pytest and save output
& $python -m pytest -q 2>&1 | Tee-Object ..\scripts\tests_run_output.txt

if ($LASTEXITCODE -ne 0) {
    Write-Host "pytest exited with code $LASTEXITCODE"
    exit $LASTEXITCODE
} else {
    Write-Host "pytest completed successfully"
}
