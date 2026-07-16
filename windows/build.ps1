$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot 'venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Project virtual environment not found: $Python"
}

Push-Location $ProjectRoot
try {
    & $Python -m pip install -r requirements-windows.txt
    & $Python windows\create_icon.py
    & $Python -m PyInstaller --noconfirm --clean windows\ClipForge.spec
    Write-Host "`nClipForge Windows application created:"
    Write-Host (Join-Path $ProjectRoot 'dist\ClipForge.exe') -ForegroundColor Green
}
finally {
    Pop-Location
}
