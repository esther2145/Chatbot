$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$agentPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$agentFile = Join-Path $projectRoot "voice-agent\agent.py"

if (-not (Test-Path -LiteralPath $agentPython)) {
    throw "Project virtual environment not found at $agentPython"
}

$existingListener = Get-NetTCPConnection `
    -LocalPort 8081 `
    -State Listen `
    -ErrorAction SilentlyContinue |
    Select-Object -First 1

if ($existingListener) {
    $existingProcess = Get-Process `
        -Id $existingListener.OwningProcess `
        -ErrorAction SilentlyContinue
    $processName = if ($existingProcess) {
        $existingProcess.ProcessName
    } else {
        "unknown process"
    }

    Write-Host "Nicky's voice agent is already running."
    Write-Host "Port 8081 is owned by $processName (PID $($existingListener.OwningProcess))."
    Write-Host "You do not need to start another copy."
    exit 0
}

$env:RAG_API_URL = "http://127.0.0.1:8001/api/ask"
Set-Location -LiteralPath $projectRoot

Write-Host "Starting Nicky's LiveKit agent outside Docker..."
Write-Host "Keep this terminal open while using live voice. Press Ctrl+C to stop."
& $agentPython $agentFile start
