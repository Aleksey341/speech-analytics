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

Write-Host ''
Write-Host 'Pre-downloading ASR and translation models from Hugging Face ...' -ForegroundColor Cyan
$prefetch = @'
from huggingface_hub import snapshot_download
models = [
    "Systran/faster-whisper-small",
    "facebook/nllb-200-distilled-600M",
]
for model in models:
    print(f"Downloading/cache check: {model}")
    snapshot_download(model)
print("Model cache ready")
'@
& $Python -c $prefetch
if ($LASTEXITCODE -ne 0) { throw 'Model pre-download failed.' }

Write-Host ''
Write-Host 'Running local dependency probe ...' -ForegroundColor Cyan
$probe = @'
from live_interpreter.local_engine import probe_local_engine
report = probe_local_engine(("ru", "en"))
print("AVAILABLE=" + str(report.available))
print("DETAIL=" + report.detail)
raise SystemExit(0 if report.available else 1)
'@
& $Python -c $probe
if ($LASTEXITCODE -ne 0) { throw 'Local engine probe failed.' }

Write-Host ''
Write-Host 'Local engine installation complete.' -ForegroundColor Green
Write-Host 'Default settings:'
Write-Host '  ASR:         faster-whisper small, CPU int8'
Write-Host '  Translation: facebook/nllb-200-distilled-600M, CUDA when torch sees it, otherwise CPU'
Write-Host '  TTS RU:      ru_RU-irina-medium'
Write-Host '  TTS EN:      en_US-lessac-medium'
Write-Host ''
Write-Host 'Start: .\run.ps1'
Write-Host 'Choose engine: Auto or Local cascade.'
Write-Host ''
Write-Host 'Optional GPU ASR (only after CUDA/CTranslate2 is known-good):' -ForegroundColor DarkYellow
Write-Host '  set LIVEINTERPRETER_ASR_DEVICE=cuda'
Write-Host '  set LIVEINTERPRETER_ASR_COMPUTE_TYPE=float16'
