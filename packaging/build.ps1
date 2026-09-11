# Build PERCH for Windows.
#
#   powershell -ExecutionPolicy Bypass -File packaging\build.ps1
#
# Produces, under dist\:
#   PERCH\PERCH.exe                 the app folder (portable: copy it anywhere)
#   PERCH-portable-<version>.zip    that folder, zipped
#   PERCH-Setup-<version>.exe       the installer, if Inno Setup is installed
#
# Written for Windows PowerShell 5.1 as well as PowerShell 7: no && chains.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$version = (python -c "from app import config; print(config.APP_VERSION)").Trim()
Write-Host "Building PERCH $version" -ForegroundColor Cyan

python packaging\make_icon.py
if ($LASTEXITCODE -ne 0) { throw "icon generation failed" }

python -m PyInstaller packaging\perch.spec --noconfirm --clean --distpath dist --workpath build
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$zip = "dist\PERCH-portable-$version.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path dist\PERCH -DestinationPath $zip
Write-Host "Portable build: $zip"

$iscc = (Get-Command iscc.exe -ErrorAction SilentlyContinue)
if ($iscc) { $iscc = $iscc.Source }
else {
    $iscc = @(
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if ($iscc) {
    & $iscc "/DAppVersion=$version" packaging\installer.iss
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }
    Write-Host "Installer: dist\PERCH-Setup-$version.exe" -ForegroundColor Green
}
else {
    Write-Warning "Inno Setup not found, so no installer was built. dist\PERCH is a complete portable build."
}
