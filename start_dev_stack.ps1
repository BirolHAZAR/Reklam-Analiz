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
    # Separate log files keep startup errors reviewable without visible consoles.
    $process = Start-Process -FilePath "powershell.exe" -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ('"' + $ScriptPath + '"')
    ) -WorkingDirectory $RootDir -WindowStyle Hidden -PassThru `
      -RedirectStandardOutput (Join-Path $LogDir "$Name.out.log") `
      -RedirectStandardError (Join-Path $LogDir "$Name.err.log")
    return $process
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

foreach ($service in @(
    @{ Name = "worker"; Pattern = 'celery.*\bworker\b'; Script = "start_celery_worker.ps1" },
    @{ Name = "beat"; Pattern = 'celery.*\bbeat\b'; Script = "start_celery_beat.ps1" }
)) {
    if ((Find-ProjectProcess $service.Pattern).Count -eq 0) {
        $started = Start-LocalService $service.Name $service.Script
        Write-Output "$($service.Name) baslatildi (PID $($started.Id))."
    } else {
        Write-Output "$($service.Name) zaten calisiyor."
    }
}

Write-Output "ReklamAnaliz hazir: $SiteUrl"
if (-not $NoBrowser) { Start-Process $SiteUrl }
