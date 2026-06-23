@echo off
rem run-fap.cmd — 1 luot fap-cli (refresh -> calendar-sync -> notify today).
rem Tu cd ve goc repo (thu muc cha cua deploy\). Lich: schtasks /TR "...\deploy\run-fap.cmd".
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0.."
if not exist output mkdir output
where fap >nul 2>nul && (set "FAP=fap") || (set "FAP=python -m fapc")

call %FAP% refresh
if errorlevel 1 (
  echo refresh that bai - refresh_token het han? Chay "fap login" lai.
  exit /b 1
)
call %FAP% calendar-sync
call %FAP% notify today
