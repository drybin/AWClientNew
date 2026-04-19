# Downloads official WixUI Russian strings for WiX v4 (matches WixToolset.UI.wixext major version).
param(
    [string]$WixTag = "v4.0.6",
    [string]$OutFile = "$PSScriptRoot/WixUI_ru-ru.wxl"
)

$ErrorActionPreference = "Stop"
$uri = "https://raw.githubusercontent.com/wixtoolset/wix/$WixTag/src/ext/UI/wixlib/WixUI_ru-ru.wxl"
Write-Host "Downloading $uri"
Invoke-WebRequest -Uri $uri -OutFile $OutFile -UseBasicParsing

$bytes = [IO.File]::ReadAllBytes($OutFile)
if ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFF -and $bytes[1] -eq 0xFE) {
    $text = [Text.Encoding]::Unicode.GetString($bytes, 2, $bytes.Length - 2)
    [IO.File]::WriteAllText($OutFile, $text, [Text.UTF8Encoding]::new($false))
    Write-Host "Converted UTF-16 LE to UTF-8"
}

$content = Get-Content -Path $OutFile -Raw -Encoding UTF8
if ($content -notmatch "WixLocalization") {
    throw "Invalid WixUI_ru-ru.wxl (no WixLocalization root)"
}
Write-Host "OK: $OutFile ($($content.Length) chars)"
