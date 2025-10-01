<#
    Outlook-AutoReport Health Check Script
    Checks recent report execution and optional local API port binding.
#>
param(
    [string]$ProjectRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
)

Write-Host "[HealthCheck] Starting diagnostics in $ProjectRoot"

$workDir = Join-Path $ProjectRoot "..\work"
$logDir = Join-Path $ProjectRoot "..\logs"
$queuePath = Join-Path $workDir "queue.json"
$reportPath = Join-Path $workDir "daily_report.xlsx"
$summaryPath = Join-Path $workDir "daily_summary.txt"
$portFile = Join-Path $workDir "service_port.txt"

if (Test-Path $portFile) {
    $port = Get-Content $portFile | Select-Object -First 1
    Write-Host "[HealthCheck] Detected service port: $port"
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:$port/health" -Method Get -UseBasicParsing -TimeoutSec 3
        Write-Host "[HealthCheck] Local API status: $($response.StatusCode)"
    } catch {
        Write-Warning "[HealthCheck] Unable to reach local API on port $port. Ensure the service is running."
    }
} else {
    Write-Host "[HealthCheck] No service_port.txt found. Skipping API probe."
}

if (-Not (Test-Path $queuePath)) {
    Write-Warning "[HealthCheck] queue.json not found in work directory. Run inbox_reader.py first."
} else {
    $queueJson = Get-Content $queuePath -Raw | ConvertFrom-Json
    $processedItems = $queueJson | Where-Object { $_.processed_at -ne $null }
    if ($processedItems.Count -gt 0) {
        $lastRun = ($processedItems | Sort-Object processed_at -Descending | Select-Object -First 1).processed_at
        Write-Host "[HealthCheck] Last processed timestamp: $lastRun"
    } else {
        Write-Warning "[HealthCheck] No processed items found in queue.json."
    }
}

if (Test-Path $reportPath) {
    $reportInfo = Get-Item $reportPath
    Write-Host "[HealthCheck] Found daily_report.xlsx (LastWriteTime=$($reportInfo.LastWriteTime))"
} else {
    Write-Warning "[HealthCheck] Missing daily_report.xlsx. Run report_builder.py."
}

if (Test-Path $summaryPath) {
    $summaryInfo = Get-Item $summaryPath
    Write-Host "[HealthCheck] Found daily_summary.txt (LastWriteTime=$($summaryInfo.LastWriteTime))"
} else {
    Write-Warning "[HealthCheck] Missing daily_summary.txt."
}

if (Test-Path $logDir) {
    Write-Host "[HealthCheck] Logs directory present: $logDir"
} else {
    Write-Warning "[HealthCheck] Logs directory not found."
}

Write-Host "[HealthCheck] Diagnostics complete."
