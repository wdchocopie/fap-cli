#Requires -Version 5.1
<#
  register-watch-windows.ps1 - run the attendance watcher as a RESIDENT background task on Windows.
  Starts at logon, HIDDEN (pythonw, no console window), auto-restarts. Default: --absent-only (less noise).
  The watcher self-refreshes the FAP token while running, so it stays alive on its own.

    .\deploy\register-watch-windows.ps1                 # every 15 min, absent-only
    .\deploy\register-watch-windows.ps1 -Interval 10
    .\deploy\register-watch-windows.ps1 -AllNew         # notify EVERY new record (not only Absent/Late)
    .\deploy\register-watch-windows.ps1 -TaskName 'FAP Watch'

  Needs a one-time 'fap login' first. Remove: Unregister-ScheduledTask -TaskName 'FAP Attendance Watch' -Confirm:$false
  (ASCII-only so Windows PowerShell 5.1 parses it regardless of file encoding.)
#>
param(
    [int]$Interval = 15,
    [string]$TaskName = 'FAP Attendance Watch',
    [switch]$AllNew
)
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot

# pythonw.exe next to the active python = no console window
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
$pyw = if ($py) { Join-Path (Split-Path $py) 'pythonw.exe' } else { 'pythonw.exe' }
if (-not (Test-Path $pyw)) { $pyw = 'pythonw.exe' }

$argline = "-m fapc watch-attendance loop $Interval"
if (-not $AllNew) { $argline += ' --absent-only' }

$action  = New-ScheduledTaskAction -Execute $pyw -Argument $argline -WorkingDirectory $RepoRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5) -ExecutionTimeLimit (New-TimeSpan -Seconds 0)
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
    -Description 'FAP attendance watcher (resident, hidden)' -Force | Out-Null

Write-Host "OK - registered resident watcher '$TaskName'."
Write-Host "  Runner    : $pyw $argline"
Write-Host "  WorkingDir: $RepoRoot"
Write-Host "  Start now : Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "  Status    : Get-ScheduledTask -TaskName '$TaskName' | Get-ScheduledTaskInfo"
Write-Host "  Remove    : Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
Write-Host ""
Write-Host "Tip: it pushes to Telegram/Discord; console is hidden (pythonw). Set TELEGRAM_CHAT in .env first."
Write-Host "     Same pattern for the bot: change argline to '-m fapc telegram-bot'."
