#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cli.py — điểm vào lệnh `fap` (gói fapc). Chạy: `fap <command>` hoặc `python -m fapc <command>`."""
import os, sys

# In tiếng Việt/emoji không lỗi trên console Windows (cp1252) — kể cả nhánh help/doctor
# (không import api.py). Phải đặt ở đây vì `fap` (không tham số) in HELP ngay, chưa import gì khác.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HELP = """fap <command>   ·   fap-cli

  Đăng nhập / Login (OAuth FE Identity):
    campuses               liệt kê campusCode (trước khi login) · list campus codes (no login)
    login                  đăng nhập Google 1 lần · one-time Google login
    refresh                làm mới token headless · refresh token headless
    exchange "<url>"       đổi URL redirect -> token · exchange redirect URL
    fap [campus]           đổi access_token đã lưu -> token FAP (khi login lỗi) · re-exchange saved token
    whoami [--full|--json] thẻ định danh OFFLINE (decode JWT) + đếm ngược hết hạn · offline identity card from the JWT

  Tổng quan / Overview:
    status | dashboard     hôm nay + điểm + điểm danh · today + grades + attendance
    all                    MỌI thứ trong 1 lần · everything at once
    today | tomorrow       lịch hôm nay | lịch ngày mai · today's | tomorrow's schedule
    weekly                 tổng kết tuần: lịch + điểm danh + điểm (gửi kênh) · weekly recap → channels
    week [next|prev|N]     lịch tuần (lọc từ kỳ) · weekly schedule
    week-exact [week year] lịch tuần lấy thẳng server (chuẩn tuần nghỉ lễ) · weekly straight from server
    semester [pattern|weeks|list|<kỳ>]   lịch CẢ KỲ: mẫu lặp hằng tuần (mặc định) | từng tuần | liệt kê kỳ · whole-term view

  Dữ liệu / Data:
    extract                kéo toàn bộ -> output/ · pull everything
    ics                    xuất output/lichhoc.ics · export .ics
    grades | grades-detail [môn]   điểm | điểm thành phần (+ "cần gì để qua"); kèm mã/tên môn = chỉ môn đó (nhẹ hơn nhiều)
                           · grades | component grades (+ pass-projection); pass a subject to fetch just that one
    subjects               tải/cache danh mục môn → hiện TÊN + tín chỉ ở mọi nơi · cache subject names + credits
    courses                lớp đang học: môn/lớp/giảng viên/phòng · my classes this term
    attendance | banrisk   điểm danh | nguy cơ cấm thi · attendance | exam-ban risk
    transcript | gpa       bảng điểm tích lũy | GPA tích lũy (tín chỉ) · transcript | cumulative GPA
    gpa-trend              GPA theo từng kỳ + xu hướng (sparkline) · per-term GPA trend
    credits                tiến độ tín chỉ tới tốt nghiệp (thanh %) · credit progress to graduation
    conduct                điểm rèn luyện/phong trào (xét tốt nghiệp) · conduct / movement points
    whatif [target]        mô phỏng GPA · GPA what-if
    exams | exams-ics      lịch thi | xuất lịch thi ra .ics (Calendar tự nhắc) · exams | exams→.ics
    exam-countdown         đếm ngược ngày thi (gần nhất trước, kèm độ gấp) · days until each upcoming exam
    news [từ khoá] [--type=N] | fees   tin tức (tìm từ khoá: SearchNews) | học phí · news (keyword search) | fees
    notifications [số|từ khoá]   thông báo + trích nội dung; số = toàn văn, chữ = lọc · notifications (+preview; number = full text, word = filter)
    profile | applications hồ sơ SV | đơn từ + trạng thái xử lý · student profile | applications

  Giao diện / UI:
    web [port]             dashboard web cục bộ (stdlib, 0 dep) · local web dashboard

  Đẩy / Push:
    calendar-auth [nhãn]   xác thực Google (dán URL redirect, chạy được không màn hình) · authorize Google (paste redirect URL, headless)
    calendar-sync [nhãn] [--prune [--yes]]   đồng bộ (upsert: đổi phòng/giờ tự sửa) + tùy chọn dọn buổi đã hủy · sync (+optional prune)
    calendar-prune [nhãn] [--yes] [--force]  xóa event lịch-học MỒ CÔI (chỉ event fap-cli tạo; dry-run mặc định) · prune orphan class events
    calendar-list          liệt kê đích Google Calendar (nhiều tài khoản) · list Google Calendar destinations
    calendar-add <nhãn> <calendar_id>   thêm đích có nhãn (1 FAP → nhiều lịch) · add a labelled destination
    calendar-remove <nhãn> bỏ một đích có nhãn · remove a labelled destination
    notify [test|<bất kỳ lệnh bot nào> [tham số]]   gửi kết quả lên kênh (danh sách đầy đủ: fap notify help) · push any bot command
    watch-attendance [loop [phút]] [--absent-only]   báo khi VỪA điểm danh; --absent-only = chỉ báo vắng/muộn
    watch-grades [loop [phút]]   báo khi có ĐIỂM MỚI (thành phần/tổng kết) · ping on new marks

  Bot tương tác / Interactive bots (chạy nền · long-running):
    telegram-bot           bot Telegram trả lời lệnh · interactive Telegram bot
    discord-bot            bot Discord trả lời lệnh · interactive Discord bot (cần · needs [bot])

    update                 cập nhật code mới nhất (git pull) · pull the latest code
    doctor                 tự kiểm tra môi trường · self-check
    selftest               chạy toàn bộ test offline (kiểm tool chạy đúng) · run offline test suites
"""

def selftest():
    """Chạy 2 bộ test OFFLINE (test_logic + integration_offline) — kiểm tool còn chạy đúng trên máy này.
    Không gọi mạng, không cần token. Trả 0 nếu tất cả pass."""
    import subprocess
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    rc = ran = 0
    for f in ("tests/test_logic.py", "tests/integration_offline.py"):
        path = os.path.join(root, f)
        if not os.path.exists(path):
            print(f"  — {f}: (không thấy)"); continue
        ran += 1
        print(f"▶ {f}")
        rc |= subprocess.run([sys.executable, path], cwd=root).returncode
    if ran == 0:        # cài qua wheel -> tests/ không đi kèm: KHÔNG báo PASS giả khi chẳng chạy gì
        print("\n⚠️ selftest: không tìm thấy bộ test nào (tests/ không đi kèm bản cài qua pip — chạy từ gốc repo).")
        return 1
    print("\n✅ selftest PASS — mọi thứ chạy đúng." if rc == 0 else "\n❌ selftest FAIL — xem dòng FAIL ở trên.")
    return rc

def update():
    """Cập nhật fap-cli: `git pull` từ gốc repo, xử lý MỌI trường hợp (ZIP/không-git, có thay đổi cục bộ,
    diverged, mất mạng, deps đổi, đã mới nhất). Bản cài '-e' nên mã mới có hiệu lực NGAY (trừ khi đổi deps).
    Logic `git pull` dùng CHUNG với bot/watcher qua selfupdate.pull() (nguồn duy nhất)."""
    from .selfupdate import pull
    res = pull()
    st = res["status"]
    # (1) Cài qua ZIP/pip (không có .git) → không pull được
    if st == "notgit":
        print("⚠️ Bản này KHÔNG phải git checkout (cài qua ZIP/pip) → không tự `git pull` được.\n"
              "   Cập nhật: tải lại ZIP mới ở https://github.com/wdchocopie/fap-cli (Code → Download ZIP),\n"
              "   hoặc cài lại bằng git:  git clone https://github.com/wdchocopie/fap-cli")
        return 1
    # (2) Có thay đổi file ĐÃ THEO DÕI chưa commit → pull --ff-only sẽ fail; hướng dẫn rõ.
    if st == "dirty":
        print("⚠️ Có thay đổi file đã-theo-dõi chưa commit — xử lý trước khi update:")
        print("   • Giữ tạm:  git stash   →  fap update   →  git stash pop")
        print("   • Bỏ hẳn :  git checkout -- .   (MẤT chỉnh sửa cục bộ)")
        for ln in (res.get("detail", "") or "").splitlines()[:8]:
            print("     " + ln)
        return 1
    # (3) Pull lỗi (mạng / diverged / nhánh khác)
    if st == "pullerror":
        print("❌ git pull lỗi. Nguyên nhân thường gặp:")
        print("   • Mất mạng → kiểm internet rồi thử lại.")
        print("   • Có commit cục bộ (diverged):  git pull --rebase   rồi `fap update` lại.")
        print("   • Đang ở nhánh khác:  git checkout main")
        print("   ↳ " + res["message"])
        return 1
    if st == "uptodate":
        print("✅ Đã ở bản mới nhất — không có gì để cập nhật."); return 0
    # (4) Đã cập nhật
    print(f"✅ Cập nhật {res['message']}")
    if res.get("deps_changed"):        # deps đổi → cần cài lại; không thì '-e' đã có hiệu lực
        print("📦 pyproject.toml ĐỔI (deps có thể thay đổi) → cài lại:  pip install -e \".[gcal,bot]\"")
    else:
        print("   (deps không đổi — mã mới có hiệu lực ngay nhờ bản cài '-e')")
    # (5) Nhắc restart service thường trú + kiểm tra
    print("   Service thường trú — khởi động lại để nạp mã mới:")
    print("     • VPS systemd :  bash deploy/update.sh   (tự pull+cài+selftest+restart)")
    print("     • Windows task:  .\\deploy\\update.ps1     (tự pull+cài+restart task)")
    print("     • Thủ công    :  systemctl --user restart fap-bot fap-watch fap-gradewatch")
    print("     • Bot đang chạy: gõ /update trong chat → tự pull + selftest + khởi động lại")
    print("   Kiểm tra:  fap selftest   ·   Token hết hạn thì:  fap refresh")
    return 0

def doctor():
    from .. import config
    from ..core.api import TOKEN_JSON
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    print("Python      :", sys.version.split()[0])
    print("token.json  :", "✓" if os.path.exists(TOKEN_JSON) else "✗ (chạy: fap login)")
    print(".env        :", "✓" if os.path.exists(os.path.join(root, ".env")) else "—")
    try: import requests; print("requests    : ✓")  # noqa: F401
    except ImportError: print("requests    : ✗ (pip install -r requirements.txt)")
    try: import googleapiclient; print("google libs : ✓")  # noqa: F401
    except ImportError: print("google libs : — (chỉ cần cho calendar-sync)")
    print("kênh notify :", ", ".join(filter(None, [
        "Telegram" if config.TELEGRAM_TOKEN else "", "Discord" if config.DISCORD_WEBHOOK_URL else ""])) or "—")

def _core_cmd(cmd):
    """True nếu `cmd` là lệnh lõi (bot_core.COMMAND_INFO) chưa có nhánh CLI riêng.
    - 'help' bị loại: `fap help` phải in TRANG HELP của CLI, không phải /help của bot.
    - Import trễ + nuốt ImportError: lệnh gõ sai vẫn in HELP dù thiếu `requests`."""
    if cmd == "help":
        return False
    try:
        from .bot_core import COMMANDS
    except ImportError:
        return False
    return cmd in COMMANDS

def _pos(rest, i):
    """Positional thứ i (bỏ các cờ --xxx), '' nếu thiếu. Dùng cho label/calendar_id của lệnh calendar-*."""
    vals = [a for a in rest if not a.startswith("--")]
    return vals[i] if i < len(vals) else ""

def main():
    args = sys.argv[1:]
    cmd = args[0] if args else "help"
    rest = args[1:]
    if   cmd == "campuses":       from ..core.extras import campuses; campuses()
    elif cmd == "login":          from ..core.auth import cmd_login; cmd_login()
    elif cmd == "refresh":        from ..core.auth import refresh_tokens; refresh_tokens()
    elif cmd == "exchange":       from ..core.auth import exchange_code; exchange_code(rest[0] if rest else "")
    elif cmd == "fap":            from ..core.auth import cmd_fap; cmd_fap(rest[0] if rest else None)
    elif cmd == "whoami":         from ..core.auth import cmd_whoami; cmd_whoami("--full" in rest, "--json" in rest)
    elif cmd == "extract":        from ..core.extract import main as m; m()
    elif cmd in ("ics", "run"):   from ..core.schedule import main as m; m()
    elif cmd == "calendar-auth":  from .gcal import cmd_auth; cmd_auth(_pos(rest, 0))
    elif cmd == "calendar-sync":  from .gcal import cmd_sync; cmd_sync(prune="--prune" in rest, yes="--yes" in rest, force="--force" in rest, label=_pos(rest, 0))
    elif cmd == "calendar-prune": from .gcal import cmd_prune; cmd_prune(yes="--yes" in rest, force="--force" in rest, label=_pos(rest, 0))
    elif cmd == "calendar-add":   from .gcal import cmd_add; cmd_add(_pos(rest, 0), _pos(rest, 1))
    elif cmd == "calendar-remove": from .gcal import cmd_remove; cmd_remove(_pos(rest, 0))
    elif cmd in ("calendar-list", "calendars"): from .gcal import cmd_list; cmd_list()
    elif cmd == "notify":         from .notify import run; run(" ".join(rest) if rest else "test")
    elif cmd == "watch-attendance": from .attendwatch import run; run(rest)
    elif cmd == "grades":         from ..core.grades import report; report()
    elif cmd == "grades-detail":
        from ..core.grades import detail
        # `fap grades-detail IAP491` -> chỉ kéo 1 môn (8 request -> 3). Giữ NGUYÊN cụm nhiều từ (tên môn).
        detail(raw="--raw" in rest, only=" ".join(a for a in rest if not a.startswith("--")) or None)
    elif cmd == "subjects":       from ..core.subjects import report; report()
    elif cmd == "courses":        from ..core.courses import report; report()
    elif cmd == "weekly":         from .notify import run; run("weekly")
    elif cmd == "attendance":     from ..core.attendance import report; report()
    elif cmd == "banrisk":        from ..core.attendance import banrisk; sys.exit(banrisk())
    elif cmd in ("status", "dashboard"): from .dashboard import status; status()
    elif cmd == "all":            from .bot_core import handle; print(handle("all"))
    elif cmd == "week":           from .dashboard import week; week(rest[0] if rest else None)
    elif cmd == "week-exact":     from .dashboard import week_exact; week_exact(rest[0] if rest else None, rest[1] if len(rest) > 1 else None)
    elif cmd == "transcript":     from ..core.transcript import report; report()
    elif cmd == "gpa":            from ..core.transcript import gpa_report; gpa_report()
    elif cmd == "gpa-trend":      from ..core.transcript import trend_report; trend_report()
    elif cmd == "credits":        from ..core.transcript import credits_report; credits_report()
    elif cmd == "conduct":        from ..core.conduct import report; report()
    elif cmd == "exam-countdown": from ..core.extras import exam_countdown_cmd; exam_countdown_cmd()
    elif cmd == "whatif":         from ..core.whatif import run; run(rest[0] if rest else None)
    elif cmd == "exams":          from ..core.extras import exams; exams()
    elif cmd == "exams-ics":      from ..core.extras import exams_ics; exams_ics()
    elif cmd == "news":
        from ..core.extras import news
        _kw = " ".join(a for a in rest if not a.startswith("--")) or None         # `fap news học bổng` (giữ NGUYÊN cụm nhiều từ)
        _ty = next((a.split("=", 1)[1] for a in rest if a.startswith("--type=")), "1")   # type 1 = bảng tin trường (0 hay rỗng)
        news(_kw, type=_ty)
    elif cmd == "fees":           from ..core.extras import fees; fees()
    elif cmd == "notifications":  from ..core.extras import notifications; notifications(" ".join(rest) or None)
    elif cmd == "profile":        from ..core.extras import profile; profile()
    elif cmd == "applications":   from ..core.extras import applications; applications()
    elif cmd == "watch-grades":   from .gradewatch import run; run(rest)
    elif cmd == "web":            from .webui import run; run(rest[0] if rest else 8000)
    elif cmd == "telegram-bot":   from .telegrambot import main as m; m()
    elif cmd == "discord-bot":    from .discordbot import main as m; m()
    elif cmd == "update":         sys.exit(update())
    elif cmd == "doctor":         doctor()
    elif cmd == "selftest":       sys.exit(selftest())
    # Mọi lệnh CÒN LẠI của bot_core.COMMAND_INFO (today, tomorrow, semester, …) chạy qua lõi chung.
    # Nhờ nhánh này, lệnh mới thêm vào COMMAND_INFO là gọi được từ CLI ngay — không bao giờ lệch nữa.
    elif _core_cmd(cmd):
        from .bot_core import handle
        print(handle(cmd, " ".join(rest) or None))     # giữ NGUYÊN cụm nhiều từ (vd tên môn có dấu cách)
    else: print(HELP)

if __name__ == "__main__":
    main()
