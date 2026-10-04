$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$python = $null
foreach ($candidate in @('3.13', '3.12', '3.11')) {
    try {
        & py "-$candidate" -c "import sys; print(sys.version)" *> $null
        if ($LASTEXITCODE -eq 0) { $python = "py -$candidate"; break }
    } catch {}
}

if (-not $python) {
    try {
        python -c "import sys; print(sys.version)"
        if ($LASTEXITCODE -eq 0) { $python = 'python' }
    } catch {}
}

if (-not $python) { throw 'Python 3.11-3.13 not found.' }

Write-Host "Using: $python" -ForegroundColor Cyan
Invoke-Expression "$python -m venv .venv"
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e ".[dev]"

if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host 'Created .env. OPENAI_API_KEY is optional when using Local/Auto fallback.' -ForegroundColor Yellow
}

Write-Host ''
Write-Host 'Base installation complete.' -ForegroundColor Green
Write-Host 'Optional Local engine: .\setup-local.ps1'
Write-Host 'Run diagnostics:       .\diagnose.ps1'
Write-Host 'Start app:             .\run.ps1'
