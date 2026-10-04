param(
    [string]$Image = "verifyiq:latest",
    [string]$Container = "verifyiq",
    [string]$Port = "8000:8000"
)

$ErrorActionPreference = "Stop"

$DatasetDir = Join-Path (Get-Location) "dataset"
$OutputDir = Join-Path (Get-Location) "output"

Write-Host "==> Building Docker image..."

docker build -f docker/Dockerfile -t $Image .

Write-Host "==> Stopping and removing existing container (if any)..."
docker rm -f $Container 2>$null

New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

Write-Host "==> Starting container..."
docker run -d `
    --name $Container `
    -p $Port `
    -v "${DatasetDir}:/app/dataset:ro" `
    -v "${OutputDir}:/app/output" `
    -e "GEMINI_API_KEY=$env:GEMINI_API_KEY" `
    -e "OPENROUTER_API_KEY=$env:OPENROUTER_API_KEY" `
    -e "LOG_LEVEL=$env:LOG_LEVEL" `
    -e "VERIFYIQ_MODE=$(if ($env:VERIFYIQ_MODE) { $env:VERIFYIQ_MODE } else { 'production' })" `
    --entrypoint uvicorn `
    $Image api.main:app --host 0.0.0.0 --port 8000

Write-Host "==> Waiting for health check..."
$healthy = $false
for ($i = 1; $i -le 12; $i++) {
    Start-Sleep -Seconds 5
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -TimeoutSec 5 -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            Write-Host "Container is healthy!"
            $healthy = $true
            break
        }
    } catch {
        # ignore connection errors while starting
    }
    Write-Host "  Attempt $i/12..."
}

if (-not $healthy) {
    Write-Warning "Health check did not pass within 60s. Container may still be starting."
    Write-Host "Check logs: docker logs $Container"
}

Register-EngineEvent -SourceIdentifier PowerShell.Exiting -SupportEvent -Action {
    Write-Host "==> Shutting down container..."
    docker stop $Container 2>$null
    docker rm $Container 2>$null
    Write-Host "Container stopped and removed."
} | Out-Null
