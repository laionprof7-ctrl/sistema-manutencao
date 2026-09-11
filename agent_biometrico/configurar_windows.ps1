param(
    [Parameter(Mandatory=$true)]
    [string]$AllowedOrigin,
    [int]$Port = 8765
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python não encontrado no PATH. Instale Python 3.11+ antes de configurar o agente."
    exit 1
}

$bytes = New-Object byte[] 48
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$rng.GetBytes($bytes)
$rng.Dispose()
$secret = [Convert]::ToBase64String($bytes)

[Environment]::SetEnvironmentVariable("SST_BIOMETRIC_AGENT_SECRET", $secret, "User")
[Environment]::SetEnvironmentVariable("SST_BIOMETRIC_ALLOWED_ORIGIN", $AllowedOrigin.TrimEnd('/'), "User")
[Environment]::SetEnvironmentVariable("SST_BIOMETRIC_AGENT_PORT", "$Port", "User")
[Environment]::SetEnvironmentVariable("SST_BIOMETRIC_AGENT_ID", "copa-sst-$env:COMPUTERNAME", "User")

Write-Host ""
Write-Host "Configuração local concluída." -ForegroundColor Green
Write-Host "Origem autorizada: $($AllowedOrigin.TrimEnd('/'))"
Write-Host "Porta local: $Port"
Write-Host ""
Write-Host "IMPORTANTE: copie o segredo abaixo para os Secrets do Streamlit com o nome SST_BIOMETRIC_AGENT_SECRET." -ForegroundColor Yellow
Write-Host $secret -ForegroundColor Cyan
Write-Host ""
Write-Host "Não salve esse segredo no GitHub e não envie por chat." -ForegroundColor Yellow
Write-Host "Feche e abra novamente o PowerShell antes de iniciar o agente."
