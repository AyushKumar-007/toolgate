# Bootstrap toolgate (Ollama + project server).
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "== toolgate lab setup ==" -ForegroundColor Cyan

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
  Write-Host "Ollama not found. Install from https://ollama.com then re-run." -ForegroundColor Red
  exit 1
}

Write-Host "Checking Ollama API..."
try {
  Invoke-RestMethod "http://127.0.0.1:11434/api/tags" | Out-Null
} catch {
  Write-Host "Starting 'ollama serve' in background..."
  Start-Process ollama -ArgumentList "serve" -WindowStyle Minimized
  Start-Sleep -Seconds 3
}

$model = "qwen2.5:3b-instruct"
Write-Host "Ensuring model $model ..."
ollama pull $model

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
  Write-Host "Creating venv and installing package..."
  py -3.12 -m venv .venv
  .\.venv\Scripts\python.exe -m pip install -U pip
  .\.venv\Scripts\python.exe -m pip install -e ".[dev,serve]"
}

Write-Host "Lab ready. Start UI with:" -ForegroundColor Green
Write-Host '  .\.venv\Scripts\python.exe -m uvicorn toolgate.api.app:create_app --factory --host 127.0.0.1 --port 8000'
