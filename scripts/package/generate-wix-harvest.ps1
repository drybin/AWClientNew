# Generate installer/HarvestedFiles.wxs from dist/activitywatch (WiX v4).
# Run after scripts/package/build-windows-installer.ps1 (or equivalent dist layout).
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$sourceRoot = Join-Path $Root "dist\activitywatch"
if (-not (Test-Path $sourceRoot)) {
    Write-Error "Missing $sourceRoot - run build-windows-installer.ps1 first."
}
$sourceRoot = (Resolve-Path $sourceRoot).Path
$wixNs = "http://wixtoolset.org/schemas/v4/wxs"

$dirMap = @{ "" = "INSTALLFOLDER" }
$dirIdx = 0
Get-ChildItem -Path $sourceRoot -Recurse -Directory | Sort-Object FullName | ForEach-Object {
    $rel = $_.FullName.Substring($sourceRoot.Length + 1)
    $dirMap[$rel] = "d$dirIdx"
    $dirIdx++
}

$doc = New-Object System.Xml.XmlDocument
$doc.AppendChild($doc.CreateXmlDeclaration("1.0", "UTF-8", $null)) | Out-Null
$wix = $doc.CreateElement("Wix", $wixNs)
$doc.AppendChild($wix) | Out-Null
$frag = $doc.CreateElement("Fragment", $wixNs)
$wix.AppendChild($frag) | Out-Null

$nodeMap = @{ "" = $null }
$dirRef = $doc.CreateElement("DirectoryRef", $wixNs)
$dirRef.SetAttribute("Id", "INSTALLFOLDER")
$frag.AppendChild($dirRef) | Out-Null

Get-ChildItem -Path $sourceRoot -Recurse -Directory | Sort-Object FullName | ForEach-Object {
    $rel = $_.FullName.Substring($sourceRoot.Length + 1)
    $parent = [IO.Path]::GetDirectoryName($rel)
    if (-not $parent) { $parent = "" }
    $id = $dirMap[$rel]
    $name = $_.Name
    $dirNode = $doc.CreateElement("Directory", $wixNs)
    $dirNode.SetAttribute("Id", $id)
    $dirNode.SetAttribute("Name", $name)
    $parentNode = if ($parent -eq "") { $dirRef } else { $nodeMap[$parent] }
    $parentNode.AppendChild($dirNode) | Out-Null
    $nodeMap[$rel] = $dirNode
}

$cg = $doc.CreateElement("ComponentGroup", $wixNs)
$cg.SetAttribute("Id", "ActivityWatchFiles")
$frag.AppendChild($cg) | Out-Null

$fileIdx = 0
Get-ChildItem -Path $sourceRoot -Recurse -File | ForEach-Object {
    $rel = $_.FullName.Substring($sourceRoot.Length + 1)
    $dirRel = [IO.Path]::GetDirectoryName($rel)
    if (-not $dirRel) { $dirRel = "" }
    $dirId = $dirMap[$dirRel]

    $comp = $doc.CreateElement("Component", $wixNs)
    $comp.SetAttribute("Id", "c$fileIdx")
    $comp.SetAttribute("Directory", $dirId)
    $comp.SetAttribute("Guid", "*")

    $fileEl = $doc.CreateElement("File", $wixNs)
    $fileEl.SetAttribute("Id", "f$fileIdx")
    $fileEl.SetAttribute("Source", $_.FullName)
    $comp.AppendChild($fileEl) | Out-Null
    $cg.AppendChild($comp) | Out-Null
    $fileIdx++
}

$outPath = Join-Path $Root "installer\HarvestedFiles.wxs"
$settings = New-Object System.Xml.XmlWriterSettings
$settings.Indent = $true
$settings.Encoding = [System.Text.Encoding]::UTF8
$writer = [System.Xml.XmlWriter]::Create($outPath, $settings)
$doc.Save($writer)
$writer.Close()
Write-Host "Generated $fileIdx files in $outPath"
