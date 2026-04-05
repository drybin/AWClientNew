# Full Windows bundle: PyInstaller for all modules + Inno Setup installer.
# Requires: Python 3.x on PATH (py -3), npm, Inno Setup 6.
# Usage: pwsh -File scripts/package/build-windows-installer.ps1
#    or:  .\scripts\package\build-windows-installer.ps1

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Py = "py"
$PyExe = & $Py -3 -c "import sys; print(sys.executable)"

$InnoDefault = "F:\Programs\InnoSetup6\ISCC.exe"
if ($env:INNO_SETUP_ISCC) {
    $Iscc = $env:INNO_SETUP_ISCC
} elseif (Test-Path $InnoDefault) {
    $Iscc = $InnoDefault
} else {
    $Iscc = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
}
if (-not (Test-Path $Iscc)) {
    Write-Error "Inno Setup compiler not found. Set INNO_SETUP_ISCC or install Inno Setup 6."
}

function Get-AwVersion {
    $pyproject = Join-Path $Root "pyproject.toml"
    if (Test-Path $pyproject) {
        $raw = Get-Content $pyproject -Raw
        if ($raw -match 'version\s*=\s*"([^"]+)"') {
            return "v" + $Matches[1].Trim()
        }
    }
    return "v0.0.0-dev"
}

$versionRaw = Get-AwVersion
$env:AW_VERSION = $versionRaw -replace '^v', ''
Write-Host "AW_VERSION=$($env:AW_VERSION) (raw: $versionRaw)"

Write-Host "== pip: aw-core, aw-client =="
& $Py -3 -m pip install -q -e "$Root\aw-core" -e "$Root\aw-client" pyinstaller

Remove-Item "$Root\dist" -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path "$Root\dist\activitywatch" -Force | Out-Null

# --- aw-qt ---
Write-Host "== aw-qt =="
& $Py -3 -m pip install -q "PyQt6==6.5.3" "PyQt6-Qt6==6.5.3" "PyQt6-sip" click setuptools
& $Py -3 -m pip install -q -e "$Root\aw-qt"
Push-Location "$Root\aw-qt"
& $Py -3 -m PyInstaller aw-qt.spec --clean --noconfirm
Pop-Location
Copy-Item -Path "$Root\aw-qt\dist\aw-qt" -Destination "$Root\dist\activitywatch\aw-qt" -Recurse -Force

# --- aw-server (web UI) ---
Write-Host "== aw-webui + aw-server =="
Push-Location "$Root\aw-server\aw-webui"
if (-not (Test-Path "node_modules")) { npm install }
npm run build
Pop-Location
$static = "$Root\aw-server\aw_server\static"
New-Item -ItemType Directory -Force -Path $static | Out-Null
Remove-Item "$static\*" -Recurse -Force -ErrorAction SilentlyContinue
robocopy "$Root\aw-server\aw-webui\dist" $static /E /NFL /NDL /NJH /NJS | Out-Null

& $Py -3 -m pip install -q -e "$Root\aw-server"
Push-Location "$Root\aw-server"
& $Py -3 -m PyInstaller aw-server.spec --clean --noconfirm
Pop-Location
Copy-Item -Path "$Root\aw-server\dist\aw-server" -Destination "$Root\dist\activitywatch\aw-server" -Recurse -Force

# --- aw-watcher-afk ---
Write-Host "== aw-watcher-afk =="
& $Py -3 -m pip install -q -e "$Root\aw-watcher-afk"
Push-Location "$Root\aw-watcher-afk"
& $Py -3 -m PyInstaller aw-watcher-afk.spec --clean --noconfirm
Pop-Location
Copy-Item -Path "$Root\aw-watcher-afk\dist\aw-watcher-afk" -Destination "$Root\dist\activitywatch\aw-watcher-afk" -Recurse -Force

# --- aw-watcher-window ---
Write-Host "== aw-watcher-window =="
& $Py -3 -m pip install -q -e "$Root\aw-watcher-window"
Push-Location "$Root\aw-watcher-window"
& $Py -3 -m PyInstaller aw-watcher-window.spec --clean --noconfirm
Pop-Location
Copy-Item -Path "$Root\aw-watcher-window\dist\aw-watcher-window" -Destination "$Root\dist\activitywatch\aw-watcher-window" -Recurse -Force

# Flatten aw-qt into activitywatch root (same as Makefile package)
Write-Host "== flatten aw-qt -> dist\activitywatch =="
$tmp = "$Root\dist\aw-qt-tmp"
Move-Item "$Root\dist\activitywatch\aw-qt" $tmp
Move-Item "$tmp\*" "$Root\dist\activitywatch\"
Remove-Item $tmp -Force

# Linux-only junk (no-op if missing)
@("libdrm.so.2", "libharfbuzz.so.0", "libfontconfig.so.1", "libfreetype.so.6") | ForEach-Object {
    Remove-Item "$Root\dist\activitywatch\$_" -Force -ErrorAction SilentlyContinue
}
Remove-Item "$Root\dist\activitywatch\pytz" -Recurse -Force -ErrorAction SilentlyContinue

# --- Inno Setup ---
$iss = Join-Path $Root "scripts\package\activitywatch-setup.iss"
Write-Host "== Inno Setup: $Iscc $iss =="
& $Iscc $iss
if ($LASTEXITCODE -ne 0) { throw "ISCC failed with exit code $LASTEXITCODE" }

$setupName = "activitywatch-$($env:AW_VERSION)-windows-setup.exe"
Copy-Item "$Root\dist\activitywatch-setup.exe" "$Root\dist\$setupName" -Force
Write-Host "Done. Installer: $Root\dist\$setupName"
Write-Host "Also: $Root\dist\activitywatch-setup.exe"
