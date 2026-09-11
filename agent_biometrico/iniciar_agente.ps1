$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
Set-Location $repoRoot

$secret = [Environment]::GetEnvironmentVariable("SST_BIOMETRIC_AGENT_SECRET", "User")
$origin = [Environment]::GetEnvironmentVariable("SST_BIOMETRIC_ALLOWED_ORIGIN", "User")

if ([string]::IsNullOrWhiteSpace($secret)) {
    Write-Error "SST_BIOMETRIC_AGENT_SECRET não configurado. Execute configurar_windows.ps1 primeiro."
    exit 1
}

if ([string]::IsNullOrWhiteSpace($origin)) {
    Write-Error "SST_BIOMETRIC_ALLOWED_ORIGIN não configurado. Execute configurar_windows.ps1 primeiro."
    exit 1
}

Write-Host "Iniciando Copa SST Biometric Agent..." -ForegroundColor Green
python .\agent_biometrico\agent.py
