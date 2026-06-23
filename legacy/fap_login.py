#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fap_login.py — TỰ ĐỘNG đăng nhập FAP và lấy token (không cần emulator).

Cơ chế login (reverse từ app, hàm AuthenticationByUsername):
    GET .../AuthenticationByUsername?CampusCode={campus}&userName={user}
        &Password={MD5(password)}&Authen=4e9800998ecf8427e
  - Password gửi dạng MD5(mật khẩu) chữ thường (KHÔNG gửi mật khẩu thô).
  - Authen là HẰNG SỐ cố định (không phải chữ ký động).
  - Response trả token + hồ sơ -> lưu vào output/token.json để mọi script dùng.

NGUỒN THÔNG TIN ĐĂNG NHẬP (ưu tiên theo thứ tự):
  1) biến môi trường: FAP_USER, FAP_PASS, FAP_CAMPUS
  2) file scripts/credentials.json: {"username","password","campus"}
     (hoặc {"username","password_md5","campus"} nếu không muốn lưu mật khẩu thô)
  3) nhập tay khi chạy (an toàn nhất — không lưu đâu cả)

Chạy:
    python fap_login.py            # tự refresh token -> output/token.json
Chỉ dùng cho TÀI KHOẢN CỦA CHÍNH BẠN.
"""
import os, sys, json, hashlib, getpass, urllib.parse
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)   # legacy/ -> repo root
OUT = os.path.join(ROOT, "output")
BASE = "https://api.fpt.edu.vn/fap/api/MyFAP"
AUTHEN_CONST = "4e9800998ecf8427e"      # hằng số gửi ở tham số &Authen= khi login

def md5(s):
    return hashlib.md5(s.encode()).hexdigest()

def get_creds():
    user = os.environ.get("FAP_USER")
    pw   = os.environ.get("FAP_PASS")
    pw_md5 = None
    campus = os.environ.get("FAP_CAMPUS")
    cfg = os.path.join(HERE, "credentials.json")
    if (not user or not pw) and os.path.exists(cfg):
        c = json.load(open(cfg, encoding="utf-8"))
        user = user or c.get("username")
        campus = campus or c.get("campus")
        if c.get("password_md5"): pw_md5 = c["password_md5"]
        elif c.get("password"):   pw = c["password"]
    if not user:
        user = input("Username (MSSV / tài khoản FAP): ").strip()
    if not campus:
        campus = input("CampusCode (chưa biết? chạy `fap campuses`): ").strip()
    if not pw and not pw_md5:
        pw = getpass.getpass("Password (không hiển thị): ")
    if not pw_md5:
        pw_md5 = md5(pw)
    return user, pw_md5, campus

def login(user, pw_md5, campus):
    url = (f"{BASE}/AuthenticationByUsername?CampusCode={urllib.parse.quote(campus)}"
           f"&userName={urllib.parse.quote(user)}&Password={pw_md5}&Authen={AUTHEN_CONST}")
    r = requests.get(url, timeout=25, headers={"User-Agent": "okhttp/4.9.2"})
    try: body = r.json()
    except Exception: body = r.text
    return r.status_code, body

def find_token(obj):
    """Tìm token trong response (cấu trúc có thể {code,message,data:{...}} hoặc phẳng)."""
    if isinstance(obj, dict):
        for k in ("token", "Token", "authenkey", "accessToken", "access_token"):
            if k in obj and obj[k]:
                return obj[k], obj
        if "data" in obj and obj["data"]:
            return find_token(obj["data"])
    return None, obj

def main():
    user, pw_md5, campus = get_creds()
    print(f"Đăng nhập: user={user} campus={campus} pwMD5={pw_md5[:8]}…")
    http, body = login(user, pw_md5, campus)
    if isinstance(body, dict):
        print(f"HTTP {http} code={body.get('code')} message={body.get('message')}")
    else:
        print(f"HTTP {http} (response không phải JSON): {str(body)[:150]}")
        sys.exit(2)

    token, src = find_token(body)
    if not token:
        print("Không tìm thấy token trong response. Kiểm tra username/password/campus.")
        print("Response:", json.dumps(body, ensure_ascii=False)[:400]); sys.exit(2)

    info = src if isinstance(src, dict) else {}
    out = {
        "authenkey": token,
        "campus": info.get("campus") or info.get("campusCode") or campus,
        "rollnumber": info.get("rollNumber") or info.get("rollnumber") or user,
        "email": info.get("email"),
        "fullname": info.get("fullname") or info.get("fullName"),
    }
    os.makedirs(OUT, exist_ok=True)
    json.dump(out, open(os.path.join(OUT, "token.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n✓ Lấy token thành công -> output/token.json")
    print(f"  campus={out['campus']} roll={out['rollnumber']} token={str(token)[:10]}…")
    print("  Mọi script khác sẽ tự dùng token này (fap_api ưu tiên token.json).")

if __name__ == "__main__":
    main()
