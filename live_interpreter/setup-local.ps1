$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$Python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) {
    throw 'Base environment .venv not found. Run .\setup.ps1 first.'
}

$Models = Join-Path $PSScriptRoot 'models'
$PiperDir = Join-Path $Models 'piper'
New-Item -ItemType Directory -Force -Path $PiperDir | Out-Null

Write-Host 'LiveInterpreter local engine installer' -ForegroundColor Cyan
Write-Host 'Pipeline: faster-whisper -> NLLB-200 distilled 600M -> Piper'
Write-Host 'This may download several gigabytes of packages/models.' -ForegroundColor Yellow
Write-Host ''

Write-Host 'Installing optional local dependencies ...' -ForegroundColor Cyan
& $Python -m pip install --upgrade -e '.[local,dev]'
if ($LASTEXITCODE -ne 0) { throw 'Local dependency installation failed.' }

Write-Host ''
Write-Host 'Downloading Piper voices (Russian + English) ...' -ForegroundColor Cyan
& $Python -m piper.download_voices --data-dir $PiperDir ru_RU-irina-medium en_US-lessac-medium
if ($LASTEXITCODE -ne 0) { throw 'Piper voice download failed.' }

# Windows PowerShell can mangle nested quotes when a multi-line Python program is
# passed through `python -c`. Write the helper scripts to temporary .py files
# instead, then execute them normally.
$TempDir = Join-Path $env:TEMP 'live-interpreter-setup'
New-Item -ItemType Directory -Force -Path $TempDir | Out-Null
$PrefetchFile = Join-Path $TempDir 'prefetch_models.py'
$ProbeFile = Join-Path $TempDir 'probe_local.py'

try {
    Write-Host ''
    Write-Host 'Pre-downloading ASR and translation models from Hugging Face ...' -ForegroundColor Cyan
    @'
from huggingface_hub import snapshot_download

models = [
    "Systran/faster-whisper-small",
    "facebook/nllb-200-distilled-600M",
]

for model in models:
    print(f"Downloading/cache check: {model}", flush=True)
    snapshot_download(model)

print("Model cache ready", flush=True)
'@ | Set-Content -Path $PrefetchFile -Encoding UTF8

    & $Python $PrefetchFile
    if ($LASTEXITCODE -ne 0) { throw 'Model pre-download failed.' }

    Write-Host ''
    Write-Host 'Running local dependency probe ...' -ForegroundColor Cyan
    @'
from live_interpreter.local_engine import probe_local_engine

report = probe_local_engine(("ru", "en"))
print("AVAILABLE=" + str(report.available), flush=True)
print("DETAIL=" + report.detail, flush=True)
raise SystemExit(0 if report.available else 1)
'@ | Set-Content -Path $ProbeFile -Encoding UTF8

    & $Python $ProbeFile
    if ($LASTEXITCODE -ne 0) { throw 'Local engine probe failed.' }
}
finally {
    Remove-Item $PrefetchFile -Force -ErrorAction SilentlyContinue
    Remove-Item $ProbeFile -Force -ErrorAction SilentlyContinue
}

Write-Host ''
Write-Host 'Local engine installation complete.' -ForegroundColor Green
Write-Host 'Default settings:'
Write-Host '  ASR:         faster-whisper small, CPU int8'
Write-Host '  Translation: facebook/nllb-200-distilled-600M, CUDA when torch sees it, otherwise CPU'
Write-Host '  TTS RU:      ru_RU-irina-medium'
Write-Host '  TTS EN:      en_US-lessac-medium'
Write-Host ''
Write-Host 'Run diagnostics from CMD:'
Write-Host '  powershell -ExecutionPolicy Bypass -File .\diagnose.ps1'
Write-Host 'Start: .\LiveInterpreter.bat'
Write-Host 'Choose engine: Auto or Local cascade.'
Write-Host ''
Write-Host 'Optional GPU ASR (only after CUDA/CTranslate2 is known-good):' -ForegroundColor DarkYellow
Write-Host '  set LIVEINTERPRETER_ASR_DEVICE=cuda'
Write-Host '  set LIVEINTERPRETER_ASR_COMPUTE_TYPE=float16'
