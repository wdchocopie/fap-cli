#Requires -Version 5.1
<#
  run-notify.ps1 <view> - refresh token then push one 'view' to chat (Telegram/Discord).
  view: today | tomorrow | weekly | banrisk | attendance | grades | status   (default: today)
  Use with Task Scheduler to send a notification at a chosen time.
  (ASCII-only on purpose so Windows PowerShell 5.1 parses it regardless of file encoding.)
#>
param([string]$View = 'today')
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
$env:PYTHONUTF8 = '1'
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
New-Item -ItemType Directory -Force -Path (Join-Path $RepoRoot 'output') | Out-Null
$Log = Join-Path $RepoRoot 'output\deploy.log'

if (Get-Command fap -ErrorAction SilentlyContinue) { $Exe = 'fap'; $Pre = @() }
else { $Exe = 'python'; $Pre = @('-m', 'fapc') }

"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] refresh + notify $View" | Tee-Object -FilePath $Log -Append
& $Exe @Pre refresh 2>&1 | Tee-Object -FilePath $Log -Append
if ($LASTEXITCODE -eq 0) {
    & $Exe @Pre notify $View 2>&1 | Tee-Object -FilePath $Log -Append
}
else {
    "refresh failed - skip notify (run 'fap login' again?)." | Tee-Object -FilePath $Log -Append
}
