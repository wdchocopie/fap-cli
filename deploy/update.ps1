# update.ps1 — CẬP NHẬT fap-cli trên Windows: git pull + cài lại (nếu deps đổi) + restart Scheduled Task.
#   .\deploy\update.ps1              # cập nhật 1 lần
#   .\deploy\update.ps1 -Schedule    # đăng ký task tự cập nhật hằng tuần (CN 03:00)
#   .\deploy\update.ps1 -Unschedule  # gỡ task tự cập nhật
# Xử lý: không-git, có thay đổi cục bộ, diverged/mất mạng, deps đổi, đã mới nhất.
param([switch]$Schedule, [switch]$Unschedule)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot          # gốc repo (cha của deploy/)
Set-Location $repo

if ($Unschedule) {
  try { Unregister-ScheduledTask -TaskName "FAP Update" -Confirm:$false } catch {}
  Write-Host "✅ Đã gỡ task 'FAP Update'."; return
}
if ($Schedule) {
  $ps = "$PSScriptRoot\update.ps1"
  $action  = New-ScheduledTaskAction -Execute "powershell" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ps`""
  $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 3am
  Register-ScheduledTask -TaskName "FAP Update" -Action $action -Trigger $trigger -Force | Out-Null
  Write-Host "✅ Đã đăng ký task 'FAP Update' (CN 03:00). Gỡ: .\deploy\update.ps1 -Unschedule"
  return
}

if (-not (Test-Path "$repo\.git")) { Write-Host "⚠️ Không phải git checkout (ZIP/pip) — tải lại ZIP từ GitHub."; exit 1 }
if (git status --porcelain) { Write-Host "⚠️ Có thay đổi cục bộ chưa commit — `git stash` hoặc `git checkout -- .` trước."; exit 1 }

$before = (git rev-parse HEAD)
$pyb    = (git rev-parse HEAD:pyproject.toml)
git pull --ff-only
if ($LASTEXITCODE -ne 0) { Write-Host "❌ git pull lỗi (mất mạng? diverged? đang ở nhánh khác 'main'?)."; exit 1 }
$after = (git rev-parse HEAD)
if ($before -eq $after) { Write-Host "✅ Đã ở bản mới nhất — không có gì để cập nhật."; exit 0 }
Write-Host "✅ $before -> $after"

# Cài lại CHỈ khi deps (pyproject) đổi — bản '-e' đã có hiệu lực ngay cho thay đổi mã thường.
if ((git rev-parse HEAD:pyproject.toml) -ne $pyb) {
  $pip = Join-Path $repo ".venv\Scripts\pip.exe"
  if (-not (Test-Path $pip)) { $pip = "pip" }
  Write-Host "📦 pyproject đổi → cài lại deps…"
  & $pip install -q -e ".[gcal,bot]"
}

# Restart các Scheduled Task fap đang CHẠY (resident: watcher/bot); bỏ qua 'FAP Update' + task one-shot.
Get-ScheduledTask | Where-Object { $_.TaskName -like 'FAP*' -and $_.TaskName -ne 'FAP Update' -and $_.State -eq 'Running' } | ForEach-Object {
  try { Stop-ScheduledTask -TaskName $_.TaskName -ErrorAction SilentlyContinue } catch {}
  Start-ScheduledTask -TaskName $_.TaskName
  Write-Host "↻ restart task: $($_.TaskName)"
}
Write-Host "✅ Update xong. (Token hết hạn thì chạy: fap refresh)"
