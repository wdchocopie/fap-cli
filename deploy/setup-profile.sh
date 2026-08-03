#!/usr/bin/env bash
# setup-profile.sh — dựng systemd --user unit cho MỘT PROFILE (nhiều tài khoản trên CÙNG 1 máy).
# Set up systemd --user units for ONE PROFILE (several FAP accounts on one box).
#
#   ⚠️ ĐỒNG Ý TRƯỚC: người đó phải TỰ chạy `fap login` của chính họ. Bạn KHÔNG nhận mật khẩu,
#      KHÔNG login hộ. refresh_token của họ sẽ nằm trên server CỦA BẠN — họ phải biết & đồng ý.
#   ⚠️ CONSENT FIRST: that person runs their OWN `fap login`. You never take their password and
#      never log in for them. Their refresh_token will live on YOUR server — they must agree.
#
#   Chuẩn bị (1 lần / mỗi profile) · prepare once per profile:
#     1) cp .env.example .env.alice   → alice tự điền TELEGRAM_*/DISCORD_* CỦA ALICE; chmod 600
#     2) .gitignore phải có  .env.*  và  !.env.example   (nếu không, .env.alice BỊ COMMIT)
#     3) trên máy CÓ TRÌNH DUYỆT, alice tự chạy:  FAP_PROFILE=alice fap login
#        (server headless không mở được browser — copy output/profiles/alice/{token,oauth_tokens}.json
#         sang rồi chmod 600; chỉ MỘT máy được refresh — xem docs/14-deploy.md §9)
#
#   Dùng · usage (từ gốc repo trên server · from the repo root on the server):
#     bash deploy/setup-profile.sh alice                       # watch-attendance + watch-grades
#     UNITS='watch,grades,bot'   bash deploy/setup-profile.sh alice   # + bot Telegram RIÊNG của alice
#     UNITS='watch,grades,daily' bash deploy/setup-profile.sh alice   # + job hằng ngày 07:00
#     INTERVAL_ATT=20 INTERVAL_GRD=120 bash deploy/setup-profile.sh alice   # đổi chu kỳ dò (phút)
#     bash deploy/setup-profile.sh --remove alice              # tắt + gỡ unit của alice
#
#   Profile MẶC ĐỊNH (chủ máy) vẫn dùng deploy/setup-server.sh và các unit KHÔNG có @.
#   The DEFAULT profile keeps using deploy/setup-server.sh and the non-@ units. Both coexist.
#   Tài liệu · docs: docs/19-multi-profile.md
set -euo pipefail
cd "$(dirname "$0")/.."
REPO="$(pwd)"
UD="$HOME/.config/systemd/user"
FAP="$REPO/.venv/bin/fap"

REMOVE=0
if [ "${1:-}" = "--remove" ]; then REMOVE=1; shift; fi
P="${1:-}"
if [ -z "$P" ]; then
  echo "Dùng · usage:  bash deploy/setup-profile.sh <tên-profile>"
  echo "               bash deploy/setup-profile.sh --remove <tên-profile>"
  exit 1
fi
# Tên profile: GIỐNG HỆT luật trong fapc/core/paths.py (chữ/số/._-). Tên sai ⇒ fap-cli lặng lẽ
# chạy như KHÔNG có profile = dùng .env + output/ của CHỦ MÁY. Chặn ngay tại đây.
case "$P" in
  *[!A-Za-z0-9._-]*|""|.|..)
    echo "❌ Tên profile '$P' không hợp lệ — chỉ cho phép chữ, số và . _ -"
    echo "   Invalid profile name — letters, digits and . _ - only."
    exit 1 ;;
esac

INST_SVC="fap-watch@$P.service fap-gradewatch@$P.service fap-bot@$P.service"

if [ "$REMOVE" = 1 ]; then
  systemctl --user disable --now $INST_SVC 2>/dev/null || true
  systemctl --user disable --now "fap@$P.timer" 2>/dev/null || true
  systemctl --user daemon-reload 2>/dev/null || true
  echo "✅ Đã gỡ service của profile '$P'."
  echo "   Token & cấu hình KHÔNG bị xóa. Muốn xóa hẳn:  rm -rf output/profiles/$P .env.$P"
  echo "   (Units removed; token/config kept. To wipe: rm -rf output/profiles/$P .env.$P)"
  exit 0
fi

INTERVAL_ATT="${INTERVAL_ATT:-15}"
INTERVAL_GRD="${INTERVAL_GRD:-60}"
UNITS="${UNITS:-watch,grades}"
echo "== fap-cli profile setup: $P =="
echo "repo=$REPO  units=$UNITS"

# 1) venv (setup-server.sh dựng sẵn; ở đây chỉ kiểm tra — KHÔNG cài đè lên môi trường chung)
[ -x "$FAP" ] || { echo "❌ Chưa có $FAP — chạy 'bash deploy/setup-server.sh' trước (nó tạo .venv)."; exit 1; }

# 2) Cấu hình RIÊNG của profile — thiếu file này thì watcher chạy nhưng KHÔNG gửi được gì cho ai:
#    khóa kênh gửi (TELEGRAM_*/DISCORD_*) CỐ Ý không thừa kế từ .env của chủ máy.
if [ ! -f ".env.$P" ]; then
  echo "❌ Chưa có $REPO/.env.$P"
  echo "   → cp .env.example .env.$P  rồi để '$P' tự điền TELEGRAM_TOKEN/TELEGRAM_CHAT (hoặc DISCORD_*)"
  echo "     CỦA CHÍNH HỌ. Khóa kênh gửi KHÔNG thừa kế từ .env của chủ máy (cố ý — chống rò chat id)."
  echo "   → then chmod 600 .env.$P"
  exit 1
fi
chmod 600 ".env.$P" 2>/dev/null || true
if git -C "$REPO" rev-parse --git-dir >/dev/null 2>&1; then
  # .gitignore của repo đã có `.env.*` + `!.env.example`. Nếu vì lý do nào đó file này VẪN không bị
  # ignore thì DỪNG HẲN: nó chứa bot token + chat id của người khác, một `git add -A` là lộ ra public.
  if ! git -C "$REPO" check-ignore -q ".env.$P" 2>/dev/null; then
    echo "❌ .env.$P KHÔNG được .gitignore — nó chứa bot token/chat id của NGƯỜI KHÁC."
    echo "   Thêm vào .gitignore:   .env.*   và   !.env.example   rồi chạy lại."
    echo "❌ .env.$P is NOT gitignored — it holds someone else's bot token/chat id. Fix .gitignore first."
    exit 1
  fi
fi

# 3) Token của profile — PHẢI do chính người đó tạo (`FAP_PROFILE=$P fap login` trên máy có browser)
if [ ! -f "output/profiles/$P/token.json" ]; then
  echo "❌ Chưa có output/profiles/$P/token.json"
  echo "   → Trên máy CÓ TRÌNH DUYỆT, CHÍNH '$P' chạy:   FAP_PROFILE=$P fap login"
  echo "   → Rồi copy 2 file này lên server (KHÔNG copy .pkce_state.json / *_state.json):"
  echo "        scp output/profiles/$P/token.json output/profiles/$P/oauth_tokens.json \\"
  echo "            <user>@<server>:$REPO/output/profiles/$P/"
  echo "        chmod 600 $REPO/output/profiles/$P/*.json"
  exit 1
fi
chmod 700 "output/profiles/$P" 2>/dev/null || true
FAP_PROFILE="$P" "$FAP" refresh && echo "✅ refresh headless OK cho profile '$P' — token còn hạn."

# 4) Cài unit TEMPLATE (1 lần dùng chung cho mọi profile) với đường dẫn THẬT
mkdir -p "$UD"
sed_paths() { sed -e "s#%h/fap-cli#$REPO#g" -e "s#%h/.venv/bin/fap#$FAP#g"; }

# Nhịp poll phải nằm ở DROP-IN RIÊNG TỪNG INSTANCE, không phải trong file template.
# `foo@.service` là MỘT file dùng chung cho mọi `foo@<tên>.service`: nếu ghi interval thẳng vào đó
# thì cài profile thứ hai sẽ lặng lẽ ĐỔI nhịp của profile thứ nhất. Drop-in `foo@<tên>.service.d/`
# chỉ áp cho đúng instance đó. `ExecStart=` rỗng là cú pháp systemd để XOÁ dòng cũ trước khi đặt lại.
dropin_interval() {   # $1=tên unit  $2=lệnh fap  $3=số phút
  mkdir -p "$UD/$1@$P.service.d"
  printf '[Service]\nExecStart=\nExecStart=%s %s loop %s\n' "$FAP" "$2" "$3" \
    > "$UD/$1@$P.service.d/interval.conf"
}

ENABLE=""
case ",$UNITS," in *,watch,*)
  sed_paths < deploy/fap-watch@.service > "$UD/fap-watch@.service"
  dropin_interval fap-watch "watch-attendance" "$INTERVAL_ATT"
  ENABLE="$ENABLE fap-watch@$P.service" ;;
esac
case ",$UNITS," in *,grades,*)
  sed_paths < deploy/fap-gradewatch@.service > "$UD/fap-gradewatch@.service"
  dropin_interval fap-gradewatch "watch-grades" "$INTERVAL_GRD"
  ENABLE="$ENABLE fap-gradewatch@$P.service" ;;
esac
case ",$UNITS," in *,bot,*)
  sed_paths < deploy/fap-bot@.service > "$UD/fap-bot@.service"
  ENABLE="$ENABLE fap-bot@$P.service" ;;
esac
case ",$UNITS," in *,daily,*)
  sed_paths < deploy/fap@.service > "$UD/fap@.service"
  cp        deploy/fap@.timer       "$UD/fap@.timer"
  ENABLE="$ENABLE fap@$P.timer" ;;
esac
[ -n "$ENABLE" ] || { echo "❌ UNITS='$UNITS' không chọn được unit nào (dùng: watch,grades,bot,daily)."; exit 1; }

# 5) linger (service sống khi logout) + bật
loginctl enable-linger "$USER" 2>/dev/null || sudo -n loginctl enable-linger "$USER" 2>/dev/null \
  || echo "⚠️ Bật linger thủ công để service sống khi logout:  sudo loginctl enable-linger $USER"
systemctl --user daemon-reload
systemctl --user enable --now $ENABLE
echo ""
echo "✅ XONG — profile '$P' đang chạy:$ENABLE"
echo "Kiểm tra · check:   systemctl --user status fap-watch@$P.service"
echo "Xem log  · logs:    journalctl --user -u fap-gradewatch@$P.service -n 50 -f"
echo "Ai đây?  · who:     FAP_PROFILE=$P $FAP whoami"
echo "Gỡ       · remove:  bash deploy/setup-profile.sh --remove $P"
