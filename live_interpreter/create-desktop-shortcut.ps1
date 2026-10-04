$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$Launcher = Join-Path $PSScriptRoot 'LiveInterpreter.bat'
if (-not (Test-Path $Launcher)) {
    throw "Launcher not found: $Launcher"
}

$Desktop = [Environment]::GetFolderPath('Desktop')
$ShortcutPath = Join-Path $Desktop 'LiveInterpreter.lnk'

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $Launcher
$Shortcut.WorkingDirectory = $PSScriptRoot
$Shortcut.Description = 'Live bidirectional speech translator'
$Shortcut.Save()

Write-Host "Desktop shortcut created:" -ForegroundColor Green
Write-Host "  $ShortcutPath"
Write-Host ''
Write-Host 'Now start LiveInterpreter by double-clicking the desktop shortcut.' -ForegroundColor Cyan
