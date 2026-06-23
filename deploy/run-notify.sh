#!/usr/bin/env bash
# run-notify.sh <view> — refresh token roi day 1 'view' len kenh chat (Telegram/Discord).
#   view: today | tomorrow | weekly | banrisk | attendance | grades | status   (mac dinh: today)
# Tu tim goc repo, log ra output/deploy.log. Dung trong cron de hen gio thong bao.
set -uo pipefail
export PYTHONUTF8=1
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
mkdir -p output
LOG="$REPO_ROOT/output/deploy.log"
VIEW="${1:-today}"

if command -v fap >/dev/null 2>&1; then FAP=(fap); else FAP=(python -m fapc); fi

{
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] refresh + notify $VIEW"
  if "${FAP[@]}" refresh; then
    "${FAP[@]}" notify "$VIEW"
  else
    echo "refresh that bai — bo qua notify (chay 'fap login' lai?)."
  fi
} 2>&1 | tee -a "$LOG"
