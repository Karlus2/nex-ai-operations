# Inicia o painel integrado do Nex e a instância local do n8n.
$ErrorActionPreference = 'Stop'

$pythonPath = Join-Path $PSScriptRoot 'backend/.venv/Scripts/python.exe'
$n8nScript = Join-Path $PSScriptRoot 'n8n/run_n8n.ps1'

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw 'Ambiente Python do Nex não encontrado. Siga a instalação do backend no README.'
}
if (-not (Test-Path -LiteralPath $n8nScript -PathType Leaf)) {
    throw 'Script de inicialização do n8n não encontrado.'
}
if (-not (Get-Command npx.cmd -ErrorAction SilentlyContinue)) {
    throw 'npx não encontrado. Instale o Node.js e reabra o PowerShell.'
}

$powerShell = (Get-Command powershell.exe).Source
$logDir = Join-Path $PSScriptRoot ('n8n-data/launcher/' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

$services = @(
    @{ Name = 'nex'; Command = "& '.\backend\.venv\Scripts\python.exe' -m backend.app.main"; Url = 'http://localhost:8000' },
    @{ Name = 'n8n'; Command = '$env:npm_config_yes = "true"; & ".\n8n\run_n8n.ps1"'; Url = 'http://localhost:5678' }
)

foreach ($service in $services) {
    $encoded = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($service.Command))
    $process = Start-Process -FilePath $powerShell -WorkingDirectory $PSScriptRoot `
        -ArgumentList @('-NoLogo', '-NoProfile', '-EncodedCommand', $encoded) `
        -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $logDir "$($service.Name).out.log") `
        -RedirectStandardError (Join-Path $logDir "$($service.Name).err.log")
    Write-Host "$($service.Name) iniciado em segundo plano (PID $($process.Id)). Abra $($service.Url) quando estiver pronto."
}

Write-Host "Logs em $logDir"
