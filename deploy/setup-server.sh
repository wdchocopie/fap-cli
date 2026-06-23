#!/usr/bin/env bash
# setup-server.sh — TỰ DỰNG fap-cli trên server Linux (systemd --user). Chạy TRÊN SERVER.
#
#   ⚠️ TRƯỚC TIÊN (1 lần, không tự động được): trên máy CÓ TRÌNH DUYỆT chạy `fap login`,
#      rồi copy thư mục output/ lên server:  scp -r output/ user@server:~/fap-cli/
#      (server headless KHÔNG mở được browser cho OAuth Google.)
#
#   Cách dùng (từ gốc repo trên server):
#     bash deploy/setup-server.sh                       # job hằng ngày + watch-attendance + watch-grades
#     EXTRAS='[gcal,bot]' bash deploy/setup-server.sh   # + bot Telegram thường trú (cần TELEGRAM_* trong .env)
#     INTERVAL_ATT=20 INTERVAL_GRD=120 bash deploy/setup-server.sh   # đổi chu kỳ dò (phút)
#
#   Gỡ sạch:  bash deploy/setup-server.sh --remove
set -euo pipefail
cd "$(dirname "$0")/.."
REPO="$(pwd)"
UD="$HOME/.config/systemd/user"
UNITS="fap.service fap.timer fap-watch.service fap-gradewatch.service fap-bot.service"

if [ "${1:-}" = "--remove" ]; then
  systemctl --user disable --now $UNITS 2>/dev/null || true
  for u in $UNITS; do rm -f "$UD/$u"; done
  systemctl --user daemon-reload 2>/dev/null || true
  echo "✅ Đã gỡ toàn bộ service fap-cli."; exit 0
fi

EXTRAS="${EXTRAS:-[gcal]}"
INTERVAL_ATT="${INTERVAL_ATT:-15}"
INTERVAL_GRD="${INTERVAL_GRD:-60}"
echo "== fap-cli server setup =="
echo "repo=$REPO  extras=$EXTRAS"

# 1) Python venv + cài gói
command -v python3 >/dev/null || { echo "❌ Cần python3 (apt install python3 python3-venv)"; exit 1; }
[ -d .venv ] || python3 -m venv .venv
./.venv/bin/pip install -q --upgrade pip
./.venv/bin/pip install -q -e ".${EXTRAS}"
FAP="$REPO/.venv/bin/fap"
echo "✅ Cài xong: $($FAP --help >/dev/null 2>&1 && echo OK || echo '(fap chạy được)')"

# 2) Token (PHẢI có sẵn từ máy có browser)
if [ ! -f output/token.json ]; then
  echo "❌ Chưa có output/token.json."
  echo "   → Trên máy có browser:  fap login"
  echo "   → Rồi copy lên đây:     scp -r output/ <user>@<server>:$REPO/"
  exit 1
fi
"$FAP" refresh && echo "✅ refresh headless OK — token còn hạn."

# 3) Sinh systemd --user units (đường dẫn THẬT của repo + venv)
mkdir -p "$UD"
sed_paths() { sed -e "s#%h/fap-cli#$REPO#g" -e "s#%h/.venv/bin/fap#$FAP#g"; }
sed_paths < deploy/fap.service        > "$UD/fap.service"
cp        deploy/fap.timer              "$UD/fap.timer"
sed_paths < deploy/fap-watch.service  | sed "s#loop 15#loop $INTERVAL_ATT#" > "$UD/fap-watch.service"
sed_paths < deploy/fap-gradewatch.service | sed "s#loop 60#loop $INTERVAL_GRD#" > "$UD/fap-gradewatch.service"
ENABLE="fap.timer fap-watch.service fap-gradewatch.service"
case "$EXTRAS" in *bot*)
  sed_paths < deploy/fap-bot.service > "$UD/fap-bot.service"
  ENABLE="$ENABLE fap-bot.service" ;;
esac

# 4) enable-linger (service chạy KHÔNG cần đăng nhập) + bật
loginctl enable-linger "$USER" 2>/dev/null || sudo -n loginctl enable-linger "$USER" 2>/dev/null \
  || echo "⚠️ Bật linger thủ công để service sống khi logout:  sudo loginctl enable-linger $USER"
systemctl --user daemon-reload
systemctl --user enable --now $ENABLE
echo ""
echo "✅ XONG — đang chạy: $ENABLE"
systemctl --user list-timers fap.timer --no-pager 2>/dev/null | sed -n '1,2p' || true
echo ""
echo "Kiểm tra · check:   systemctl --user status fap-gradewatch.service"
echo "Xem log  · logs:    journalctl --user -u fap-watch.service -n 50 -f"
echo "Gỡ sạch  · remove:  bash deploy/setup-server.sh --remove"
