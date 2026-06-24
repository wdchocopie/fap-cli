#!/usr/bin/env bash
# update.sh — CẬP NHẬT fap-cli trên server (Linux, systemd --user). Chạy TỪ GỐC REPO trên server.
#
#   bash deploy/update.sh                       # git pull + cài lại + selftest + restart service đang bật
#   EXTRAS='[gcal,bot]' bash deploy/update.sh   # cài lại kèm extras (khớp lúc setup)
#
# An toàn: pull --ff-only (không tự merge rối); chỉ restart unit ĐANG bật; selftest cảnh báo nếu hỏng.
set -euo pipefail
cd "$(dirname "$0")/.."
REPO="$(pwd)"
EXTRAS="${EXTRAS:-[gcal]}"
echo "== fap-cli update @ $REPO  (extras=$EXTRAS) =="

before="$(git rev-parse HEAD 2>/dev/null || echo none)"
git pull --ff-only
after="$(git rev-parse HEAD 2>/dev/null || echo none)"
if [ "$before" = "$after" ]; then
  echo "✅ Đã ở bản mới nhất ($after) — không có gì để cập nhật."
else
  echo "✅ $before → $after"
fi

# Cài lại (idempotent) — bắt trường hợp pyproject/deps đổi. Bản '-e' nên mã có hiệu lực ngay.
[ -d .venv ] || python3 -m venv .venv
./.venv/bin/pip install -q -e ".${EXTRAS}"

# Kiểm tra nhanh (không chặn nếu lỗi — chỉ cảnh báo)
./.venv/bin/fap selftest || echo "⚠️ selftest có lỗi — xem log ở trên trước khi tin bản mới."

# Khởi động lại các service THƯỜNG TRÚ đang bật để nạp mã mới (one-shot fap.timer thì lượt sau tự dùng mã mới)
systemctl --user daemon-reload 2>/dev/null || true
for u in fap-watch.service fap-gradewatch.service fap-bot.service; do
  if systemctl --user is-enabled "$u" >/dev/null 2>&1; then
    systemctl --user restart "$u" && echo "↻ restart $u"
  fi
done
echo "✅ Update xong. (Token hết hạn thì chạy:  ./.venv/bin/fap refresh )"
