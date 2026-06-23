#Requires -Version 5.1
<#
  run-fap.ps1 - one scheduled fap-cli pass.
  Order: fap refresh -> fap calendar-sync -> fap notify today.

  Auto-locates the repo root (parent of deploy\), cds in, logs to output\deploy.log, and
  STOPS if 'refresh' fails (expired token) so it never syncs/notifies with a stale token.

  Schedule it: deploy\register-task-windows.ps1   (or schtasks - see deploy\README.md)
  (ASCII-only on purpose so Windows PowerShell 5.1 parses it regardless of file encoding.)
#>
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
$env:PYTHONUTF8 = '1'
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
New-Item -ItemType Directory -Force -Path (Join-Path $RepoRoot 'output') | Out-Null
$Log = Join-Path $RepoRoot 'output\deploy.log'

# Runner: prefer 'fap', fall back to 'python -m fapc'
if (Get-Command fap -ErrorAction SilentlyContinue) { $Exe = 'fap'; $Pre = @() }
else { $Exe = 'python'; $Pre = @('-m', 'fapc') }

function Invoke-Step {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$StepArgs)
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    "[$stamp] $Exe $(($Pre + $StepArgs) -join ' ')" | Tee-Object -FilePath $Log -Append
    & $Exe @Pre @StepArgs 2>&1 | Tee-Object -FilePath $Log -Append
    return $LASTEXITCODE
}

$rc = Invoke-Step refresh
if ($rc -ne 0) {
    "refresh failed (rc=$rc) - refresh_token expired? Run 'fap login' again." |
        Tee-Object -FilePath $Log -Append
    exit $rc
}
Invoke-Step calendar-sync | Out-Null
Invoke-Step notify today  | Out-Null
