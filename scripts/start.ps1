$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path -LiteralPath '.\.venv\Scripts\python.exe')) {
    throw 'Crie o ambiente virtual e instale requirements.txt conforme o README.'
}
& '.\.venv\Scripts\python.exe' -m uvicorn app:app --host 127.0.0.1 --port 8000
