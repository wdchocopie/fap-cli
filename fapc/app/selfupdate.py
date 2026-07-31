#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""selfupdate.py — cập nhật code KHI TIẾN TRÌNH ĐANG CHẠY (bot/watcher thường trú).

Dùng chung cho telegram-bot, discord-bot, watch-attendance, watch-grades:

    git pull --ff-only  →  fap selftest (offline)  →  nếu PASS thì os.execv (tự khởi động lại
    chính mình để nạp mã mới).

An toàn:
- Chỉ CHỦ tài khoản kích hoạt lệnh /update (bot đã khoá theo owner).
- selftest FAIL sau pull  → KHÔNG restart (giữ mã CŨ đang chạy) → không rơi vào vòng crash.
- deps đổi (pyproject)     → KHÔNG tự restart (mã mới có thể import lib chưa cài) → báo cài lại thủ công.
- không phải git / dirty / mất mạng → báo rõ, không làm gì nguy hiểm.

`pull()` là NGUỒN DUY NHẤT của logic `git pull` (lệnh `fap update` ngoài CLI cũng gọi lại — xem cli.py).
"""
import os, sys, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Vân tay phụ thuộc: đổi ở BẤT KỲ manifest nào (không chỉ pyproject) đều coi là deps_changed.
_DEP_FILES = ("pyproject.toml", "requirements.txt", "requirements-bot.txt", "requirements-gcal.txt")


def _git(*a):
    return subprocess.run(["git", "-C", ROOT, *a], capture_output=True, text=True)


def _dep_fingerprint():
    """Vân tay blob của mọi manifest phụ thuộc đã theo-dõi tại HEAD hiện tại. File không có -> '' (nhất quán)."""
    return "|".join(_git("rev-parse", f"HEAD:{f}").stdout.strip() for f in _DEP_FILES)


def has_git():
    """True nếu ROOT là một git checkout thật (không phải bản cài qua ZIP/pip)."""
    return (os.path.isdir(os.path.join(ROOT, ".git"))
            and _git("rev-parse", "--is-inside-work-tree").returncode == 0)


def pull():
    """`git pull --ff-only` xử lý mọi trường hợp. Trả dict:
        {"status": "notgit"|"dirty"|"pullerror"|"uptodate"|"updated",
         "before", "after", "n", "deps_changed", "message"}
    THUẦN kết quả (không in, không restart) — caller quyết định hiển thị/khởi động lại."""
    if not has_git():
        return {"status": "notgit",
                "message": "Không phải git checkout (cài qua ZIP/pip) → không tự cập nhật được."}
    # File đã-theo-dõi bị sửa chưa commit sẽ chặn fast-forward; -uno bỏ qua untracked (output/.venv/logs).
    dirty = _git("status", "--porcelain", "--untracked-files=no").stdout.strip()
    if dirty:
        return {"status": "dirty",
                "message": "Có thay đổi cục bộ chưa commit — `git stash` rồi thử lại.",
                "detail": dirty}
    before = _git("rev-parse", "HEAD").stdout.strip()
    deps_before = _dep_fingerprint()
    pr = _git("pull", "--ff-only")
    if pr.returncode != 0:
        return {"status": "pullerror",
                "message": (pr.stderr or pr.stdout).strip()[:300] or "git pull lỗi (mạng? diverged?)."}
    after = _git("rev-parse", "HEAD").stdout.strip()
    if before == after:
        return {"status": "uptodate", "before": before, "after": after,
                "message": "Đã ở bản mới nhất."}
    n = _git("rev-list", "--count", f"{before}..{after}").stdout.strip() or "?"
    deps = _dep_fingerprint() != deps_before          # đổi ở pyproject HOẶC bất kỳ requirements-*.txt
    return {"status": "updated", "before": before, "after": after, "n": n,
            "deps_changed": deps, "message": f"{before[:7]} → {after[:7]} ({n} commit mới)."}


def run_selftest():
    """Chạy `fap selftest` (2 bộ test offline) trong tiến trình con. Trả (ok, tail_output)."""
    p = subprocess.run([sys.executable, "-m", "fapc", "selftest"],
                       cwd=ROOT, capture_output=True, text=True)
    out = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode == 0, out[-600:]


def restart():
    """Thay thế tiến trình hiện tại bằng chính nó (os.execv) để nạp mã mới. KHÔNG trả về.
    Dựng lại lệnh gốc qua `python -m fapc <args>` — chạy đúng dù khởi động bằng `fap ...`
    hay `python -m fapc ...` (sys.argv[1:] là các tham số lệnh con)."""
    try:
        sys.stdout.flush(); sys.stderr.flush()
    except Exception:                                   # noqa: BLE001
        pass
    os.execv(sys.executable, [sys.executable, "-m", "fapc", *sys.argv[1:]])


def perform_update(run_tests=True):
    """Điều phối 1 lần cập nhật: pull → (nếu updated) selftest → quyết định restart.
    Trả (summary_text, do_restart). KHÔNG tự restart — caller GỬI summary trước rồi mới gọi restart()
    (để người dùng thấy tin nhắn trước khi bot khởi động lại)."""
    from ..i18n import t
    res = pull()
    st = res["status"]
    if st == "notgit":
        return "⚠️ " + t("Không phải git checkout (cài qua ZIP/pip) → không tự cập nhật được.",
                          "Not a git checkout (installed via ZIP/pip) → can't self-update."), False
    if st == "dirty":
        return "⚠️ " + t("Có thay đổi cục bộ chưa commit — `git stash` rồi thử lại.",
                          "Uncommitted local changes — `git stash` then retry."), False
    if st == "pullerror":
        return "❌ " + t("git pull lỗi:\n", "git pull failed:\n") + res["message"], False
    if st == "uptodate":
        return "✅ " + t("Đã ở bản mới nhất — không có gì để cập nhật.",
                         "Already up to date — nothing to update."), False
    # status == "updated"
    lines = ["✅ " + t(f"Cập nhật {res['message']}", f"Updated {res['message']}")]
    if res.get("deps_changed"):
        lines.append("📦 " + t("pyproject đổi (deps) — cài lại rồi khởi động lại THỦ CÔNG "
                               "(`pip install -e \".[gcal,bot]\"`); KHÔNG tự restart để tránh thiếu lib.",
                               "pyproject changed (deps) — reinstall and restart MANUALLY "
                               "(`pip install -e \".[gcal,bot]\"`); not auto-restarting to avoid a missing lib."))
        return "\n".join(lines), False
    if run_tests:
        ok, tail = run_selftest()
        if not ok:
            lines.append("❌ " + t("selftest FAIL sau khi pull — GIỮ mã cũ đang chạy, KHÔNG khởi động lại.",
                                   "selftest FAILED after pull — keeping the old code, NOT restarting."))
            lines.append(tail[-400:])
            return "\n".join(lines), False
        lines.append("🧪 " + t("selftest PASS.", "selftest PASS."))
    lines.append("🔄 " + t("Khởi động lại để nạp mã mới…", "Restarting to load the new code…"))
    return "\n".join(lines), True


def autoupdate_min():
    """Số phút giữa mỗi lần tự-dò-cập-nhật (FAP_AUTOUPDATE_MIN). 0 = tắt."""
    from .. import config
    try:
        return max(0, int(str(getattr(config, "AUTOUPDATE_MIN", "0")).strip() or 0))
    except (TypeError, ValueError):
        return 0


def maybe_autoupdate(last_check, now_ts, log=print):
    """Gọi trong vòng lặp nền (watcher/bot). Nếu bật (FAP_AUTOUPDATE_MIN>0) & tới hạn & có bản mới &
    selftest PASS & deps không đổi → restart() (KHÔNG trả về). Ngược lại trả mốc last_check mới.
    Best-effort: mọi lỗi git/test được nuốt, chỉ log — không làm chết vòng lặp."""
    mins = autoupdate_min()
    if mins <= 0 or (now_ts - last_check) < mins * 60:
        return last_check
    try:
        res = pull()
        if res["status"] == "updated":
            if res.get("deps_changed"):
                log("⚠️ Auto-update: " + res["message"]
                    + " — deps đổi, cài lại + khởi động lại THỦ CÔNG (không tự restart).")
            else:
                ok, tail = run_selftest()
                if ok:
                    log("🔄 Auto-update: " + res["message"] + " — selftest PASS, đang khởi động lại…")
                    restart()                                  # không trả về (os.execv)
                    log("⚠️ Auto-update: os.execv KHÔNG khởi động lại được — vẫn chạy mã CŨ, restart thủ công.")
                else:
                    log("⚠️ Auto-update: đã pull nhưng selftest FAIL — GIỮ mã cũ.\n" + tail[-300:])
    except Exception as e:                                     # noqa: BLE001 — không làm chết loop
        log("  auto-update lỗi · error: " + str(e))
    return now_ts
