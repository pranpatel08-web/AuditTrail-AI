param(
    [string]$Url = "http://127.0.0.1:8077/api/v1/health",
    [int]$Minutes = 240
)

$log = Join-Path $PSScriptRoot "..\.zwork\health-watch.log"
$log = [System.IO.Path]::GetFullPath($log)
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
if (-not (Test-Path $log)) { New-Item -ItemType File -Path $log | Out-Null }

$deadline = (Get-Date).AddMinutes($Minutes)
$last = ""
while ((Get-Date) -lt $deadline) {
    try {
        $health = Invoke-RestMethod $Url -TimeoutSec 10
        $line = "{0} backend={1} reason={2}" -f (Get-Date -Format o), $health.storage.backend, $health.storage.supabase_reason
    }
    catch {
        $line = "{0} unreachable" -f (Get-Date -Format o)
    }
    if ($line -ne $last) {
        Add-Content -Path $log -Value $line
        $last = $line
    }
    Start-Sleep -Seconds 10
}
