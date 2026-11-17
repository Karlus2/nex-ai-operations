# Script auxiliar para inicialização do n8n local com variáveis de ambiente do Nex
$env:NEX_API_URL = if ($env:NEX_API_URL) { $env:NEX_API_URL } else { "http://127.0.0.1:8000" }
if (-not $env:INTERNAL_API_KEY -and (Test-Path ".env")) {
    $env:INTERNAL_API_KEY = (Get-Content .env | Where-Object { $_ -match "^INTERNAL_API_KEY=(.*)" } | ForEach-Object { $matches[1] })
}
$env:N8N_PORT = "5678"
$env:WEBHOOK_URL = "http://localhost:5678/"
$env:N8N_DIAGNOSTICS_ENABLED = "false"
$env:N8N_VERSION_CANDIDATE_CHECK = "false"
$env:N8N_BLOCK_ENV_ACCESS_IN_NODE = "false"

Write-Host "[Nex n8n Runner] Iniciando n8n conectado a $env:NEX_API_URL..."
npx n8n start
