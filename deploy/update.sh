#!/usr/bin/env bash
# update.sh — CẬP NHẬT fap-cli trên server (Linux, systemd --user). Chạy TỪ GỐC REPO trên server.
#
#   bash deploy/update.sh                       # git pull + cài lại + selftest + restart service đang bật
#   EXTRAS='[gcal,bot]' bash deploy/update.sh   # khớp extras lúc setup
#   bash deploy/update.sh --auto                # KHÔNG tương tác (cho fap-update.timer): lỗi/dirty → bỏ qua êm
#
# Xử lý mọi trường hợp: không-git, có thay đổi cục bộ, diverged, mất mạng, deps đổi, đã mới nhất.
# An toàn: pull --ff-only (không tự merge rối); chỉ restart unit ĐANG bật.
set -uo pipefail
cd "$(dirname "$0")/.."
REPO="$(pwd)"
EXTRAS="${EXTRAS:-[gcal]}"
# --schedule / --unschedule: bật/tắt auto-update hằng tuần (systemd --user timer)
UD="$HOME/.config/systemd/user"
if [ "${1:-}" = "--schedule" ]; then
  mkdir -p "$UD"
  sed "s#%h/fap-cli#$REPO#g" deploy/fap-update.service > "$UD/fap-update.service"
  cp deploy/fap-update.timer "$UD/fap-update.timer"
  loginctl enable-linger "$USER" 2>/dev/null || true
  systemctl --user daemon-reload
  systemctl --user enable --now fap-update.timer
  echo "✅ Bật auto-update hằng tuần (CN 03:00, --auto). Gỡ: bash deploy/update.sh --unschedule"
  systemctl --user list-timers fap-update.timer --no-pager 2>/dev/null | sed -n '1,2p' || true
  exit 0
fi
if [ "${1:-}" = "--unschedule" ]; then
  systemctl --user disable --now fap-update.timer 2>/dev/null || true
  rm -f "$UD/fap-update.timer" "$UD/fap-update.service"
  systemctl --user daemon-reload 2>/dev/null || true
  echo "✅ Đã tắt auto-update."; exit 0
fi

AUTO=0; [ "${1:-}" = "--auto" ] && AUTO=1
# --auto: lỗi nhẹ thì THOÁT 0 (timer không spam OnFailure); thủ công thì THOÁT 1 để thấy rõ.
soft() { echo "$1"; [ "$AUTO" = 1 ] && exit 0 || exit 1; }

echo "== fap-cli update @ $REPO  (extras=$EXTRAS${AUTO:+, auto=$AUTO}) =="
command -v git >/dev/null || soft "⚠️ Không có git."
[ -d .git ] || soft "⚠️ Không phải git checkout (ZIP/pip) — tải lại từ GitHub để cập nhật."
# Chỉ chặn khi có thay đổi file ĐÃ THEO DÕI (-uno bỏ qua untracked như .venv/output/logs — không cản pull).
[ -z "$(git status --porcelain --untracked-files=no)" ] || soft "⚠️ Có thay đổi file đã-theo-dõi chưa commit — git stash/checkout trước rồi chạy lại."

before="$(git rev-parse HEAD 2>/dev/null || echo none)"
pyb="$(git rev-parse HEAD:pyproject.toml 2>/dev/null || echo x)"
if ! git pull --ff-only; then
  soft "❌ git pull lỗi (mất mạng? diverged? nhánh khác 'main'?). Xử lý rồi chạy lại."
fi
after="$(git rev-parse HEAD 2>/dev/null || echo none)"
if [ "$before" = "$after" ]; then
  echo "✅ Đã ở bản mới nhất ($after) — không có gì để cập nhật."; exit 0
fi
echo "✅ $before → $after"

# Cài lại CHỈ khi deps (pyproject) đổi — nhanh hơn, bản '-e' vẫn có hiệu lực ngay cho thay đổi mã thường.
[ -d .venv ] || python3 -m venv .venv
if [ "$pyb" != "$(git rev-parse HEAD:pyproject.toml 2>/dev/null || echo y)" ]; then
  echo "📦 pyproject đổi → cài lại deps…"; ./.venv/bin/pip install -q -e ".${EXTRAS}"
fi

# Kiểm tra nhanh (không chặn — chỉ cảnh báo)
./.venv/bin/fap selftest || echo "⚠️ selftest có lỗi — xem log ở trên trước khi tin bản mới."

# Khởi động lại service THƯỜNG TRÚ đang bật để nạp mã mới (one-shot fap.timer lượt sau tự dùng mã mới)
systemctl --user daemon-reload 2>/dev/null || true
for u in fap-watch.service fap-gradewatch.service fap-bot.service; do
  if systemctl --user is-enabled "$u" >/dev/null 2>&1; then
    systemctl --user restart "$u" && echo "↻ restart $u"
  fi
done
echo "✅ Update xong. (Token hết hạn thì chạy:  ./.venv/bin/fap refresh )"
