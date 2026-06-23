#!/usr/bin/env bash
# run-fap.sh — 1 lượt fap-cli theo lịch (refresh -> calendar-sync -> notify today).
# Tự tìm gốc repo, tự cd, log ra output/deploy.log, DỪNG nếu refresh lỗi (token hết hạn).
# Auto-locates repo root, cds in, logs, stops if refresh fails. chmod +x trước khi dùng.
set -uo pipefail
export PYTHONUTF8=1

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
mkdir -p output
LOG="$REPO_ROOT/output/deploy.log"

if command -v fap >/dev/null 2>&1; then FAP=(fap); else FAP=(python -m fapc); fi

run() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ${FAP[*]} $*" | tee -a "$LOG"
  "${FAP[@]}" "$@" 2>&1 | tee -a "$LOG"
  return "${PIPESTATUS[0]}"
}

if ! run refresh; then
  echo "refresh that bai — refresh_token het han? Chay 'fap login' lai." | tee -a "$LOG"
  exit 1
fi
run calendar-sync || true
run notify today   || true
