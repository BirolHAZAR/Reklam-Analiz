param([switch]$NoBrowser)

$ErrorActionPreference = "Stop"
$RootDir = $PSScriptRoot
$ProjectDir = Join-Path $RootDir "instagram_reklam_analiz"
$PythonExe = Join-Path $RootDir ".venvs\instagram_reklam_analiz\Scripts\python.exe"
$LogDir = Join-Path $RootDir "runtime\launcher"
$SiteUrl = "http://localhost:8000/"

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
if (-not (Test-Path -LiteralPath $PythonExe)) { throw "Python venv bulunamadi: $PythonExe" }

function Test-LocalWebsite {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $SiteUrl -TimeoutSec 4
        return ($response.StatusCode -eq 200 -and $response.Content -match "ReklamAnaliz")
    } catch { return $false }
}

function Find-ProjectProcess([string]$Pattern) {
    # Use the complete project Python path to avoid touching other projects.
    $PythonPattern = [regex]::Escape($PythonExe)
    return @(Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
        Where-Object { $_.CommandLine -match $PythonPattern -and $_.CommandLine -match $Pattern })
}

function Start-LocalService([string]$Name, [string]$Script) {
    $ScriptPath = Join-Path $RootDir $Script
    if (-not (Test-Path -LiteralPath $ScriptPath)) { throw "Baslatma dosyasi bulunamadi: $ScriptPath" }
    $ConsoleScript = Join-Path $RootDir "show_dev_service.ps1"
    $process = Start-Process -FilePath "cmd.exe" -ArgumentList @(
        "/c", "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", ('"' + $ConsoleScript + '"'), "-ServiceName", $Name
    ) -WorkingDirectory $RootDir -WindowStyle Normal -PassThru
    return $process
}

function Show-ServiceConsole([string]$Name) {
    $consolePattern = [regex]::Escape((Join-Path $RootDir "show_dev_service.ps1"))
    $existing = @(Get-CimInstance Win32_Process -Filter "Name = 'powershell.exe'" |
        Where-Object { $_.CommandLine -match $consolePattern -and $_.CommandLine -match "-ServiceName\s+$Name\b" })
    if ($existing.Count -eq 0) { $null = Start-LocalService $Name "show_dev_service.ps1" }
}

$env:DEBUG = "True"
$env:DJANGO_ENV = "development"
$previous = Get-Location
try {
    Set-Location -LiteralPath $ProjectDir
    & $PythonExe manage.py check_database
    if ($LASTEXITCODE -ne 0) { throw "Yerel veritabani kontrolu basarisiz." }
} finally { Set-Location -LiteralPath $previous }

$web = $null
if (-not (Test-LocalWebsite)) {
    if ((Find-ProjectProcess 'manage\.py.*runserver').Count -eq 0) {
        $web = Start-LocalService "web" "start_dev_server.ps1"
    }
    $deadline = (Get-Date).AddSeconds(60)
    do {
        if (Test-LocalWebsite) { break }
        if ($null -ne $web -and $web.HasExited) {
            throw "Web sunucusu kapandi. runtime\launcher\web.err.log dosyasini kontrol edin."
        }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
    if (-not (Test-LocalWebsite)) {
        throw "Web sunucusu hazir olmadi. 8000 portunu ve runtime\launcher\web.err.log dosyasini kontrol edin."
    }
}

Show-ServiceConsole "web"

foreach ($service in @(
    @{ Name = "worker"; Pattern = 'celery.*\bworker\b'; Script = "start_celery_worker.ps1" },
    @{ Name = "beat"; Pattern = 'celery.*\bbeat\b'; Script = "start_celery_beat.ps1" }
)) {
    if ((Find-ProjectProcess $service.Pattern).Count -eq 0) {
        $started = Start-LocalService $service.Name $service.Script
        Write-Output "$($service.Name) baslatildi (PID $($started.Id))."
    } else {
        Write-Output "$($service.Name) zaten calisiyor."
        Show-ServiceConsole $service.Name
    }
}

$workerPingLog = Join-Path $LogDir "worker-health.log"
$previous = Get-Location
try {
    Set-Location -LiteralPath $ProjectDir
    $workerHealthy = $false
    $healthDeadline = (Get-Date).AddSeconds(45)
    do {
        # A new worker needs time to import Django. Celery writes a missing
        # reply to stderr; retain it in the log without aborting the launcher.
        $healthErrorPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = "Continue"
            & $PythonExe -m celery -A config inspect ping --timeout=5 *> $workerPingLog
            $workerHealthy = ($LASTEXITCODE -eq 0 -and (Get-Content -LiteralPath $workerPingLog -Raw) -match '\bpong\b')
        } finally { $ErrorActionPreference = $healthErrorPreference }
        if (-not $workerHealthy) { Start-Sleep -Milliseconds 500 }
    } while (-not $workerHealthy -and (Get-Date) -lt $healthDeadline)
} finally { Set-Location -LiteralPath $previous }
$beatProcesses = @(Find-ProjectProcess 'celery.*\bbeat\b')
$beatLog = Join-Path $LogDir "beat.console.log"
if (-not (Test-Path -LiteralPath $beatLog)) { $beatLog = Join-Path $LogDir "beat.err.log" }
$beatRecent = (Test-Path -LiteralPath $beatLog) -and ((Get-Item -LiteralPath $beatLog).LastWriteTime -gt (Get-Date).AddMinutes(-2))
$statusLines = @(
    "Kontrol: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
    "Web: HAZIR - $SiteUrl",
    $(if ($workerHealthy) { "Worker: CALISIYOR - pong yaniti alindi" } else { "Worker: YANIT ALINAMADI - worker.err.log dosyasini kontrol edin" }),
    $(if ($beatProcesses.Count -gt 0 -and $beatRecent) { "Beat: CALISIYOR - surec mevcut, log guncel" } elseif ($beatProcesses.Count -gt 0) { "Beat: SUREC MEVCUT - henuz guncel log dogrulanamadi" } else { "Beat: CALISMIYOR - beat.err.log dosyasini kontrol edin" }),
    "Web, worker ve beat ayri CMD pencerelerinde izlenebilir. Log klasoru: $LogDir"
)
$statusLines | Set-Content -LiteralPath (Join-Path $LogDir "status.txt") -Encoding UTF8
$statusLines | Write-Output
if (-not $NoBrowser) { Start-Process $SiteUrl }
