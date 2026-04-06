param(
    [string]$Token = "",
    [string]$UserAppData = ""
)

$ErrorActionPreference = "Continue"

$logDir = "C:\ProgramData\OTGuruAgent\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = "$logDir\install.log"

function Write-Log {
    param([string]$Message)
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$ts] $Message" | Add-Content -Path $logFile
}

Write-Log "Installer started"

# Read config_template.json
$configPath = Join-Path $PSScriptRoot "config_template.json"
$config = Get-Content $configPath -Raw | ConvertFrom-Json
Write-Log "Config loaded: installer_id=$($config.installer_id)"

# Collect PC parameters
Write-Log "Collecting PC parameters"
$hostname       = $env:COMPUTERNAME
$currentUser    = $env:USERNAME
$winVer         = (Get-WmiObject Win32_OperatingSystem).Caption
$cpu            = (Get-WmiObject Win32_Processor | Select-Object -First 1).Name
$ramGB          = [math]::Round((Get-WmiObject Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 2)
$netCfg         = Get-WmiObject Win32_NetworkAdapterConfiguration | Where-Object { $_.IPEnabled } | Select-Object -First 1
$macAddress     = if ($netCfg) { $netCfg.MACAddress } else { "" }
$ipAddress      = if ($netCfg) { $netCfg.IPAddress[0] } else { "" }
$installDatetime = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$machineGuid    = (Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Cryptography" -ErrorAction SilentlyContinue).MachineGuid
$diskDrive      = Get-WmiObject Win32_DiskDrive | Select-Object -First 1
$diskSerial     = if ($diskDrive -and $diskDrive.SerialNumber) { $diskDrive.SerialNumber.Trim() } else { "" }
$baseBoard      = Get-WmiObject Win32_BaseBoard | Select-Object -First 1
$mbSerial       = if ($baseBoard -and $baseBoard.SerialNumber) { $baseBoard.SerialNumber.Trim() } else { "" }

# Generate HWID
$raw    = "$mbSerial$diskSerial$macAddress"
$bytes  = [System.Text.Encoding]::UTF8.GetBytes($raw)
$hash   = [System.Security.Cryptography.SHA256]::Create().ComputeHash($bytes)
$hwid   = [System.BitConverter]::ToString($hash).Replace("-", "").ToLower()
Write-Log "HWID generated: $hwid"

# Write pc_params.json
$pcParams = [ordered]@{
    hostname           = $hostname
    current_user       = $currentUser
    windows_version    = $winVer
    cpu_model          = $cpu
    ram                = $ramGB
    mac_address        = $macAddress
    ip_address         = $ipAddress
    install_datetime   = $installDatetime
    machine_guid       = $machineGuid
    disk_serial        = $diskSerial
    motherboard_serial = $mbSerial
}
$pcParams | ConvertTo-Json | Set-Content (Join-Path $PSScriptRoot "pc_params.json")
Write-Log "PC parameters saved"

# Write hwid.txt
$hwid | Set-Content (Join-Path $PSScriptRoot "hwid.txt")

# Resolve token: ProgramData token_pending (immediate CA) → installer folder → -Token param → clipboard
# Note: deferred CA runs as SYSTEM; clipboard read in post-install often fails — CA writes pending file as user.
$tokenValue = ""
$pendingProgramData = Join-Path $env:ProgramData "OTGuruAgent\token_pending.txt"
$pendingInstallDir = Join-Path $PSScriptRoot "token_pending.txt"
foreach ($pendingFile in @($pendingProgramData, $pendingInstallDir)) {
    if ($tokenValue -ne "") { break }
    if (Test-Path $pendingFile) {
        $tokenValue = (Get-Content $pendingFile -Raw -ErrorAction SilentlyContinue).Trim()
        Remove-Item $pendingFile -Force -ErrorAction SilentlyContinue
        if ($tokenValue -ne "") { Write-Log "Token read from token_pending.txt ($pendingFile)" }
    }
}
if ($tokenValue -eq "" -and $Token -ne "") {
    $tokenValue = $Token
    Write-Log "Token received via parameter"
}
if ($tokenValue -eq "") {
    try {
        Add-Type -AssemblyName System.Windows.Forms
        $clip = [System.Windows.Forms.Clipboard]::GetText()
        # Align with UI: short tokens are allowed; SYSTEM clipboard read is a last resort only.
        if ($clip -match '^[A-Za-z0-9_\-]{6,}$') {
            $tokenValue = $clip
            Write-Log "Token found in clipboard"
        }
    } catch {
        Write-Log "Clipboard check failed: $_"
    }
}

if ($tokenValue -ne "") {
    $targetBase = ""
    if ($UserAppData -ne "") {
        $targetBase = $UserAppData
        Write-Log "Using MSI user AppData path: $targetBase"
    } elseif ($env:APPDATA -ne "") {
        $targetBase = $env:APPDATA
        Write-Log "Using process APPDATA path: $targetBase"
    }

    if ($targetBase -ne "") {
        $targetDir = Join-Path $targetBase "activitywatch\activitywatch\aw-server"
        New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
        $targetPath = Join-Path $targetDir "preload.txt"
        $tokenValue | Set-Content -Path $targetPath
        Write-Log "Token saved to $targetPath"
    } else {
        $tokenValue | Set-Content (Join-Path $PSScriptRoot "preload.txt")
        Write-Log "APPDATA not resolved, token saved to installer directory preload.txt"
    }
} else {
    Write-Log "No token provided, preload.txt not created"
}

# Send installation report
Write-Log "Sending installation report"
$installResult = 0
try {
    $logContent = Get-Content $logFile -Raw -ErrorAction SilentlyContinue
    $report = @{
        company_id     = $config.company_id
        installer_id   = $config.installer_id
        hostname       = $hostname
        username       = $currentUser
        hwid           = $hwid
        install_result = $installResult
        install_time   = $installDatetime
        agent_version  = "1.0.0"
        log            = $logContent
    }
    $uri = "$($config.server_url)/installer/report"
    Invoke-RestMethod -Uri $uri -Method POST -Body ($report | ConvertTo-Json -Depth 3) -ContentType "application/json" -TimeoutSec 30
    Write-Log "Report sent successfully"
} catch {
    Write-Log "Failed to send report (NETWORK_ERROR): $_"
}

Write-Log "Installation completed"
