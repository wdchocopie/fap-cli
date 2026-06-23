#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pull_token.py — TỰ ĐỘNG lấy token FAP từ máy ảo LDPlayer (cho tài khoản Google OAuth).

Gói trọn các bước thủ công thành 1 lệnh:
  1) Bật LDPlayer instance (nếu chưa chạy) + chờ boot
  2) (tùy chọn --refresh) mở app FAP để nó tự đăng nhập lại Google -> token mới
  3) su pull databases/RKStorage  (CHỈ adb cục bộ — không gọi server trường)
  4) Đọc token -> output/token.json  (mọi script khác tự dùng)
  5) (tùy chọn --quit) tắt instance

Yêu cầu 1 lần: trong LDPlayer bật ADB + Root (đã làm). App FAP đã đăng nhập Google.

Dùng:
    python pull_token.py            # bật->pull->giữ máy chạy
    python pull_token.py --quit     # bật->pull->tắt máy   (hợp cho Task Scheduler)
    python pull_token.py --refresh --quit   # mở app cho token mới rồi pull->tắt
"""
import subprocess, os, time, json, sqlite3, sys

# ===== CẤU HÌNH (đổi nếu LDPlayer cài chỗ khác) =====
LDDIR = os.environ.get("LDPLAYER_DIR", r"D:\LDPlayer\LDPlayer9")  # đổi qua env nếu cài chỗ khác
ADB = os.path.join(LDDIR, "adb.exe")
LDC = os.path.join(LDDIR, "ldconsole.exe")
IDX = "0"
PKG = "com.fuct"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # legacy/ -> repo root
DBDIR = os.path.join(ROOT, "device-data", "com.fuct", "databases")
TOKEN_JSON = os.path.join(ROOT, "output", "token.json")

def adb(*a):  return subprocess.run([ADB, *a], capture_output=True, text=True)
def ldc(*a):  return subprocess.run([LDC, *a], capture_output=True, text=True)

def is_running():
    return ldc("isrunning", "--index", IDX).stdout.strip() == "running"

def ensure_running():
    if not is_running():
        print("• Bật LDPlayer instance...")
        ldc("launch", "--index", IDX)
    adb("start-server")
    print("• Chờ thiết bị + boot...")
    for i in range(80):
        if adb("shell", "getprop", "sys.boot_completed").stdout.strip() == "1":
            print(f"  ✓ Booted (sau ~{i*3}s)")
            return True
        time.sleep(3)
    print("  ✗ Boot quá lâu / không kết nối được adb.")
    return False

def has_root():
    return adb("shell", "su -c id").stdout.strip().startswith("uid=0")

def refresh_app():
    print("• Mở app FAP để làm mới token (Google auto sign-in)...")
    adb("shell", f"monkey -p {PKG} -c android.intent.category.LAUNCHER 1")
    time.sleep(12)
    adb("shell", f"am force-stop {PKG}")

def pull_db():
    os.makedirs(DBDIR, exist_ok=True)
    print("• Copy RKStorage ra /sdcard rồi pull về...")
    adb("shell", "su -c \"rm -f /sdcard/RKStorage*\"")   # dọn bản CŨ trước (tránh pull nhầm token cũ)
    r = adb("shell", f'su -c "cp -f /data/data/{PKG}/databases/RKStorage /sdcard/RKStorage; '
                     f'cp -f /data/data/{PKG}/databases/RKStorage-wal /sdcard/RKStorage-wal 2>/dev/null; '
                     f'cp -f /data/data/{PKG}/databases/RKStorage-shm /sdcard/RKStorage-shm 2>/dev/null; '
                     f'chmod 666 /sdcard/RKStorage*"')
    if r.returncode != 0:
        raise SystemExit(f"✗ Copy bằng su thất bại (Root chưa bật?). stderr: {r.stderr.strip()[:200]}")
    for f in ("RKStorage", "RKStorage-wal", "RKStorage-shm"):
        adb("pull", f"/sdcard/{f}", os.path.join(DBDIR, f))
    adb("shell", "su -c \"rm -f /sdcard/RKStorage*\"")

def extract_token():
    db = os.path.join(DBDIR, "RKStorage")
    con = sqlite3.connect(db); c = con.cursor()
    def g(k):
        c.execute("SELECT value FROM catalystLocalStorage WHERE key=?", (k,)); r = c.fetchone(); return r[0] if r else None
    out = {"authenkey": g("authenkey"), "campus": g("campus"), "rollnumber": g("rollnumber"),
           "email": g("email"), "fullname": g("fullname")}
    con.close()
    if not out["authenkey"]:
        print("  ✗ Không thấy token trong RKStorage (app đã đăng nhập chưa?)"); return None
    os.makedirs(os.path.dirname(TOKEN_JSON), exist_ok=True)
    json.dump(out, open(TOKEN_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return out

def main():
    args = sys.argv[1:]
    if not os.path.exists(ADB):
        print(f"Không thấy adb tại {ADB} — sửa LDDIR trong script."); sys.exit(1)
    if not ensure_running():
        sys.exit(2)
    if not has_root():
        print("✗ Chưa có Root trong LDPlayer (Settings → Other → ROOT permission)."); sys.exit(3)
    if "--refresh" in args:
        refresh_app()
    pull_db()
    out = extract_token()
    if out:
        print(f"\n✓ Token -> output/token.json")
        print(f"  campus={out['campus']} roll={out['rollnumber']} token={str(out['authenkey'])[:10]}…")
    if "--quit" in args:
        print("• Tắt LDPlayer instance..."); ldc("quit", "--index", IDX)

if __name__ == "__main__":
    main()
