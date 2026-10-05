[CmdletBinding()]
param(
    [switch]$SkipModelDownload
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$VoiceVenv = Join-Path $PSScriptRoot '.voice-venv'
$VoicePython = Join-Path $VoiceVenv 'Scripts\python.exe'

if (-not (Test-Path $VoicePython)) {
    $python = $null
    foreach ($candidate in @('3.11', '3.13', '3.12', '3.10')) {
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
    if (-not $python) { throw 'Python 3.10-3.13 not found.' }

    Write-Host "Creating isolated voice environment with: $python" -ForegroundColor Cyan
    Invoke-Expression "$python -m venv `"$VoiceVenv`""
}

if (-not (Test-Path $VoicePython)) {
    throw "Voice virtual environment was not created: $VoicePython"
}

Write-Host 'Updating pip ...' -ForegroundColor Cyan
& $VoicePython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'pip upgrade failed.' }

$HasNvidia = $null -ne (Get-Command nvidia-smi -ErrorAction SilentlyContinue)
if ($HasNvidia) {
    Write-Host 'NVIDIA detected. Installing PyTorch 2.6 CUDA 12.4 wheels ...' -ForegroundColor Cyan
    & $VoicePython -m pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124
} else {
    Write-Host 'NVIDIA not detected. Installing PyTorch 2.6 CPU wheels ...' -ForegroundColor Cyan
    & $VoicePython -m pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cpu
}
if ($LASTEXITCODE -ne 0) { throw 'PyTorch installation failed.' }

Write-Host 'Installing Chatterbox Multilingual voice cloning ...' -ForegroundColor Cyan
& $VoicePython -m pip install 'chatterbox-tts==0.1.7'
if ($LASTEXITCODE -ne 0) { throw 'Chatterbox installation failed.' }

Write-Host ''
Write-Host 'Checking Chatterbox and Torch ...' -ForegroundColor Cyan
$check = @'
import torch
from chatterbox.mtl_tts import ChatterboxMultilingualTTS
print("CHATTERBOX_IMPORT=OK")
print("TORCH=" + torch.__version__)
print("CUDA_AVAILABLE=" + str(torch.cuda.is_available()))
if torch.cuda.is_available():
    print("CUDA_DEVICE=" + torch.cuda.get_device_name(0))
'@
& $VoicePython -c $check
if ($LASTEXITCODE -ne 0) { throw 'Chatterbox import failed.' }

if (-not $SkipModelDownload) {
    Write-Host ''
    Write-Host 'Downloading/caching Chatterbox Multilingual model. This can be several GB ...' -ForegroundColor Yellow
    $prefetch = @'
import torch
from chatterbox.mtl_tts import ChatterboxMultilingualTTS
device = "cuda" if torch.cuda.is_available() else "cpu"
print("VOICE_DEVICE=" + device)
model = ChatterboxMultilingualTTS.from_pretrained(device=device)
print("CHATTERBOX_MODEL=READY")
'@
    & $VoicePython -c $prefetch
    if ($LASTEXITCODE -ne 0) {
        throw 'Chatterbox model download/load failed. Re-run with -SkipModelDownload to keep only the installed runtime.'
    }
}

Write-Host ''
Write-Host 'Voice Clone installation complete.' -ForegroundColor Green
Write-Host "Environment: $VoiceVenv"
Write-Host 'Next:'
Write-Host '  1. Start LiveInterpreter.'
Write-Host '  2. Select your microphone in "Вы -> Собеседник".'
Write-Host '  3. Click "Записать мой голос (15 с)".'
Write-Host '  4. Set voice to "Мой голос".'
Write-Host ''
Write-Host 'The voice sample stays locally in live_interpreter\voice_profiles and is ignored by Git.' -ForegroundColor DarkYellow
