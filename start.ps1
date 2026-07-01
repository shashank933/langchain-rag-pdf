$root = $PSScriptRoot

Write-Host "============================================" -ForegroundColor Black -BackgroundColor Yellow
Write-Host "  Starting PDF RAG with DeepSeek" -ForegroundColor Black -BackgroundColor Yellow
Write-Host "============================================" -ForegroundColor Black -BackgroundColor Yellow
Write-Host ""

# Activate virtual environment path
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$venvActivate = Join-Path $root ".venv\Scripts\Activate.ps1"

if (Test-Path $venvPython) {
    Write-Host "Backend (FastAPI)  -> http://localhost:8000" -ForegroundColor Green
    Write-Host "Frontend (Vite)    -> http://localhost:3000" -ForegroundColor Green
    Write-Host "API Docs           -> http://localhost:8000/docs" -ForegroundColor Cyan
    Write-Host ""

    $backendCmd = ". '$venvActivate'; uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"
    $frontendCmd = "Set-Location '$root\frontend'; npm run dev"

    Write-Host "Opening two terminal windows..." -ForegroundColor Yellow

    Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd

    Write-Host ""
    Write-Host "Both services started. Close each window to stop." -ForegroundColor Gray
} else {
    Write-Host "ERROR: .venv not found. Trying Docker..." -ForegroundColor Red
    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if ($docker) {
        Write-Host "Running with Docker Compose..." -ForegroundColor Yellow
        docker-compose up --build
    } else {
        Write-Host "ERROR: Neither Python venv nor Docker found." -ForegroundColor Red
        Write-Host "Run:  pip install -r requirements.txt" -ForegroundColor Gray
        Write-Host "Then: uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload" -ForegroundColor Gray
    }
}
