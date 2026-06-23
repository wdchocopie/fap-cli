#Requires -Version 5.1
<#
  register-task-windows.ps1 - register a Windows Scheduled Task that runs run-fap.ps1 daily.
  Default 07:00, task name "FAP Daily". No admin needed (current-user task).

    .\deploy\register-task-windows.ps1
    .\deploy\register-task-windows.ps1 -Time 18:30
    .\deploy\register-task-windows.ps1 -TaskName "FAP Evening" -Time 19:00

  (ASCII-only on purpose so Windows PowerShell 5.1 parses it regardless of file encoding.)
#>
param(
    [string]$Time = '07:00',
    [string]$TaskName = 'FAP Daily'
)
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
$ErrorActionPreference = 'Stop'

$Script = Join-Path $PSScriptRoot 'run-fap.ps1'
if (-not (Test-Path $Script)) { throw "Not found: $Script" }

$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument ('-NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $Script)
$trigger = New-ScheduledTaskTrigger -Daily -At $Time
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Description 'fap-cli daily (refresh + calendar-sync + notify)' -Force | Out-Null

Write-Host "OK - registered '$TaskName' to run daily at $Time."
Write-Host "  Run now : Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "  Status  : Get-ScheduledTask -TaskName '$TaskName' | Get-ScheduledTaskInfo"
Write-Host "  Log     : output\deploy.log"
Write-Host "  Remove  : Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
