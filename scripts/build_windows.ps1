param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

if ($Clean) {
    Remove-Item -LiteralPath "$ProjectRoot\build" -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath "$ProjectRoot\dist" -Recurse -Force -ErrorAction SilentlyContinue
}

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onefile `
    --name CaptionTranslator `
    --collect-all faster_whisper `
    --collect-all ctranslate2 `
    --collect-all sounddevice `
    --add-data "realtime_subtitle\config.json;realtime_subtitle" `
    realtime_subtitle\main.py

Write-Host "Built: $ProjectRoot\dist\CaptionTranslator.exe"
