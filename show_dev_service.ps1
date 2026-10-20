param([Parameter(Mandatory=$true)][ValidateSet("web", "worker", "beat")][string]$ServiceName)

$ErrorActionPreference = "Stop"
$RootDir = $PSScriptRoot
$PythonExe = Join-Path $RootDir ".venvs\instagram_reklam_analiz\Scripts\python.exe"
$LogDir = Join-Path $RootDir "runtime\launcher"
$Host.UI.RawUI.WindowTitle = "ReklamAnaliz - $ServiceName"
$services = @{
    web = @{ Pattern = 'manage\.py.*runserver'; Script = "start_dev_server.ps1" }
    worker = @{ Pattern = 'celery.*\bworker\b'; Script = "start_celery_worker.ps1" }
    beat = @{ Pattern = 'celery.*\bbeat\b'; Script = "start_celery_beat.ps1" }
}
$service = $services[$ServiceName]
# One console per service, including simultaneous launcher clicks.
$mutex = New-Object System.Threading.Mutex($false, "Local\ReklamAnaliz-$ServiceName")
$acquired = $mutex.WaitOne(0)
if (-not $acquired) { $mutex.Dispose(); exit 0 }
try {
    $running = @(Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
        Where-Object { $_.CommandLine -match [regex]::Escape($PythonExe) -and $_.CommandLine -match $service.Pattern })
    if ($running.Count -gt 0) {
        Write-Host "$ServiceName zaten calisiyor. Canli log gosteriliyor."
        $logPath = Join-Path $LogDir "$ServiceName.console.log"
        if (-not (Test-Path -LiteralPath $logPath)) { $logPath = Join-Path $LogDir "$ServiceName.err.log" }
        Get-Content -LiteralPath $logPath -Tail 50 -Wait
    } else {
        New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
        $logPath = Join-Path $LogDir "$ServiceName.console.log"
        $scriptPath = Join-Path $RootDir $service.Script
        # A separate PowerShell process preserves the service scripts' exit
        # behavior while displaying and recording both output streams.
        $ErrorActionPreference = "Continue"
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $scriptPath 2>&1 |
            Tee-Object -FilePath $logPath
        Write-Host "$ServiceName durdu. Yukaridaki ciktiyi kontrol edin."
        Read-Host "Pencereyi kapatmak icin Enter"
    }
} finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
