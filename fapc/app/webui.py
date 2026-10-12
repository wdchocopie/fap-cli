#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""webui.py — Web dashboard cục bộ (Python stdlib, KHÔNG thêm thư viện).

    fap web            # mở http://127.0.0.1:8000
    fap web 8765       # đổi cổng

Trang 1 file: bấm nút -> GET /q?c=<lệnh>[&a=<tham số>] -> bot_core.handle() (tái dùng đúng lõi như bot/CLI).
Nút bấm SINH TỪ bot_core.COMMAND_INFO — thêm lệnh mới là dashboard có nút ngay.
CHỈ bind 127.0.0.1 — KHÔNG phơi dữ liệu ra mạng. Cần token còn hạn — hết hạn thì /login ngay trên trang.
Tự bật cache 2' (FAP_CACHE_MIN) để bấm nhiều lần không gọi lại API — nhẹ máy yếu / lịch sự với server.

/login — đăng nhập FAP từ trình duyệt (tái dùng botlogin, y như /login của bot): device flow ưu tiên (trang
tự hỏi GET /login/status ~3s), PKCE dự phòng (dán URL redirect -> POST /login/finish). Chốt an toàn: Host
phải là localhost đúng cổng (chống DNS-rebinding), mọi POST cần mã CSRF của tiến trình + Origin cùng gốc,
thân POST bị kẹp BODY_MAX, mọi chữ đều html.escape, KHÔNG bao giờ in token hay URL đã dán.
"""
import os, json, html, hmac, secrets, http.server, urllib.parse, webbrowser
from .bot_core import handle, COMMANDS, command_groups
from . import botlogin
from .gcal import looks_like_gredirect
from ..core import auth
from ..core.api import TOKEN_JSON
from ..i18n import t

ARG_MAX = 64          # kẹp độ dài tham số ?a= — chỉ là mã môn / điểm / tên view, không bao giờ dài hơn
BODY_MAX = 8192       # POST /login/* chỉ chở campus hoặc MỘT URL redirect — lớn hơn là bất thường
# Mã CSRF MỖI tiến trình: chỉ trang cùng gốc đọc được nó (SOP + chặn Host lạ), nên trang độc không POST hộ được.
_CSRF = secrets.token_urlsafe(32)
# MỘT phiên đăng nhập cho cả tiến trình (2 phiên song song sẽ ghi đè .pkce_state.json của nhau).
_LOGIN = botlogin.LoginSession()
# Kết quả device flow do THREAD NỀN ghi; ghi msg TRƯỚC rồi mới đổi state -> ai đọc thấy 'done' là có msg.
_DEVICE = {"state": "idle", "msg": ""}

def _groups():
    """Nút bấm SINH TỪ bot_core.COMMAND_INFO (qua command_groups) — thêm lệnh mới là có nút ngay,
    không còn danh sách chép tay để lệch. Shape cho JS: [[tiêu đề, [[lệnh, emoji, nhãn], …]], …]."""
    return [[title, [[name, emoji, label] for name, emoji, label in items]]
            for title, items in command_groups()]

_PAGE = """<!doctype html><html lang=vi><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>fap-cli</title>
<style>
 :root{--bg:#0f1115;--card:#161a22;--fg:#e8eaed;--muted:#8a93a6;--accent:#4f8cff;
       --btn:#222834;--btnh:#2f3744;--line:#262c38;--ok:#3fb950;--warn:#d29922}
 @media (prefers-color-scheme:light){:root{--bg:#f4f6fb;--card:#fff;--fg:#1a1f2b;--muted:#5b6472;
       --accent:#2563eb;--btn:#e9edf5;--btnh:#dde3ef;--line:#e3e8f0}}
 *{box-sizing:border-box} body{font-family:system-ui,'Segoe UI',Roboto,sans-serif;margin:0;background:var(--bg);
   color:var(--fg);line-height:1.5}
 header{display:flex;align-items:center;gap:.7rem;flex-wrap:wrap;padding:.9rem 1.1rem;border-bottom:1px solid var(--line)}
 header h1{font-size:1.1rem;margin:0;font-weight:650} header .who{color:var(--muted);font-size:.85rem}
 header .sp{flex:1} .toggle{color:var(--muted);font-size:.82rem;display:flex;align-items:center;gap:.35rem;cursor:pointer}
 .login{color:var(--muted);font-size:.85rem;text-decoration:none;padding:.3rem .6rem;border-radius:8px;border:1px solid var(--line)}
 .login.hot{background:var(--warn);color:#111;border-color:var(--warn);font-weight:650}
 #arg{background:var(--btn);color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:.35rem .6rem;
   font-size:.85rem;width:14rem;max-width:45vw}
 main{display:flex;gap:1rem;max-width:1000px;margin:1rem auto;padding:0 1rem;align-items:flex-start}
 nav{flex:0 0 210px;display:flex;flex-direction:column;gap:.9rem}
 .grp h2{font-size:.72rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin:.1rem .2rem .35rem}
 .grp{display:flex;flex-direction:column;gap:.3rem}
 button{display:flex;align-items:center;gap:.55rem;width:100%;text-align:left;padding:.5rem .7rem;border:0;
   border-radius:9px;background:var(--btn);color:var(--fg);cursor:pointer;font-size:.9rem;transition:.12s;
   white-space:normal;line-height:1.25}
 button:hover{background:var(--btnh)} button.active{background:var(--accent);color:#fff}
 button .e{font-size:1.05rem;width:1.3rem;text-align:center}
 section{flex:1;min-width:0;background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden}
 .hd{display:flex;align-items:center;gap:.5rem;padding:.7rem 1rem;border-bottom:1px solid var(--line);font-weight:600}
 .hd .spin{width:14px;height:14px;border:2px solid var(--muted);border-top-color:transparent;border-radius:50%;
   animation:r .7s linear infinite;display:none} .hd.loading .spin{display:inline-block}
 @keyframes r{to{transform:rotate(360deg)}}
 pre{white-space:pre-wrap;word-break:break-word;margin:0;padding:1rem 1.1rem;font-size:.97rem;
   font-family:ui-monospace,'Cascadia Code',Consolas,monospace;min-height:8rem}
 footer{color:var(--muted);font-size:.78rem;text-align:center;padding:.6rem 1rem 1.4rem}
 @media (max-width:720px){main{flex-direction:column} nav{flex:none;width:100%;flex-direction:row;flex-wrap:wrap}
   .grp{flex:1 1 46%} }
</style></head><body>
<header>
 <h1>📚 fap-cli</h1><span class=who id=who></span><span class=sp></span>
 <input id=arg maxlength=64 placeholder="tham số · arg (IAP491 · weeks · 8)"
   title="Tham số cho lệnh có nhận: grades-detail mã môn · semester pattern|weeks|list · whatif điểm">
 <label class=toggle><input type=checkbox id=auto> tự làm mới 60s</label>
 <a class=login id=login href=/login>__LOGIN__</a>
</header>
<main>
 <nav id=nav></nav>
 <section><div class=hd id=hd><span class=spin></span><span id=title>Tổng quan</span></div><pre id=out>…</pre></section>
</main>
<footer>Chạy cục bộ (localhost) · dữ liệu lấy trực tiếp từ FAP bằng token của bạn · không gửi đi đâu khác.</footer>
<script>
 const GROUPS=__GROUPS__;
 const nav=document.getElementById('nav'),out=document.getElementById('out'),hd=document.getElementById('hd'),
   title=document.getElementById('title');
 let cur='status',timer=null,labels={},loadedFor=null;   // loadedFor: lệnh mà ô tham số đang thuộc về
 GROUPS.forEach(([g,items])=>{const d=document.createElement('div');d.className='grp';
   d.innerHTML='<h2>'+g+'</h2>';items.forEach(([c,e,l])=>{labels[c]=e+' '+l;
     const b=document.createElement('button');b.dataset.c=c;
     b.innerHTML='<span class=e>'+e+'</span>'+l;b.onclick=()=>load(c);d.appendChild(b)});nav.appendChild(d)});
 function mark(c){document.querySelectorAll('button').forEach(b=>b.classList.toggle('active',b.dataset.c===c))}
 const argbox=document.getElementById('arg');
 async function load(c,keepArg){cur=c;mark(c);title.textContent=labels[c]||c;hd.classList.add('loading');
   // ĐỔI lệnh -> XOÁ ô tham số. Ô này dùng chung cho mọi nút; giữ nguyên sẽ khiến tham số gõ cho
   // lệnh trước (vd 'IAP301') lặng lẽ áp sang lệnh vừa bấm (vd 'whatif') -> chạy sai mà không báo.
   if(!keepArg&&c!==loadedFor){argbox.value=''} loadedFor=c;
   const a=(argbox.value||'').trim();                       // ?a= — lệnh không nhận tham số sẽ bỏ qua
   try{const r=await fetch('/q?c='+encodeURIComponent(c)+(a?'&a='+encodeURIComponent(a):''));
     out.textContent=await r.text()}
   catch(e){out.textContent='Lỗi kết nối: '+e}finally{hd.classList.remove('loading')}}
 argbox.onkeydown=e=>{if(e.key==='Enter')load(cur,true)};   // Enter = chạy lại lệnh HIỆN TẠI, GIỮ tham số
 document.getElementById('auto').onchange=e=>{clearInterval(timer);
   if(e.target.checked)timer=setInterval(()=>load(cur,true),60000)};   // tự làm mới: giữ tham số
 const hot=()=>document.getElementById('login').classList.add('hot');   // chưa đăng nhập / hết hạn -> nút nổi bật
 fetch('/me').then(r=>r.json()).then(m=>{if(m&&m.roll)document.getElementById('who').textContent=
   '· '+(m.name||'')+' ('+m.roll+(m.campus?' · '+m.campus:'')+')';if(!m||!m.roll||m.expired)hot()}).catch(hot);
 load('status');
</script></body></html>"""


def _page():
    return _PAGE.replace("__LOGIN__", html.escape(t("🔐 Đăng nhập FAP", "🔐 FAP sign-in"))) \
                .replace("__GROUPS__", json.dumps(_groups(), ensure_ascii=False))

def _me():
    try:
        with open(TOKEN_JSON, encoding="utf-8") as f:
            m = json.load(f)
        me = {"name": m.get("fullname") or "", "roll": m.get("rollnumber") or "", "campus": m.get("campus") or ""}
    except Exception:                                    # noqa: BLE001 — chưa login -> header trống
        return {}
    try:                                                 # CHỈ trả cờ hết hạn (từ claim exp) — token không rời máy chủ
        with open(auth.OAUTH_JSON, encoding="utf-8") as f:
            claims = auth.decode_jwt(json.load(f).get("access_token") or "")
        me["expired"] = auth.token_freshness(claims)[0] == "expired"
    except (OSError, ValueError, AttributeError):
        pass
    return me

# ---------- /login: đăng nhập FAP từ trình duyệt ----------
_LOGIN_PAGE = """<!doctype html><html lang=vi><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>fap-cli · login</title>
<style>
 :root{--bg:#0f1115;--card:#161a22;--fg:#e8eaed;--muted:#8a93a6;--accent:#4f8cff;--line:#262c38}
 @media (prefers-color-scheme:light){:root{--bg:#f4f6fb;--card:#fff;--fg:#1a1f2b;--muted:#5b6472;--accent:#2563eb;--line:#e3e8f0}}
 *{box-sizing:border-box} body{font-family:system-ui,'Segoe UI',Roboto,sans-serif;margin:0;background:var(--bg);
   color:var(--fg);line-height:1.5}
 main{max-width:640px;margin:2rem auto;padding:0 1rem}
 .card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:1.1rem 1.2rem}
 h1{font-size:1.15rem;margin:0 0 .8rem} .muted{color:var(--muted);font-size:.88rem}
 pre{white-space:pre-wrap;word-break:break-word;font-family:ui-monospace,Consolas,monospace;margin:.6rem 0}
 input,textarea{width:100%;background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:8px;
   padding:.5rem .6rem;font-size:.95rem}
 button{margin-top:.7rem;padding:.55rem 1rem;border:0;border-radius:9px;background:var(--accent);color:#fff;
   font-size:.95rem;cursor:pointer}
 a{color:var(--accent);word-break:break-all} .code{font-size:1.4rem;font-weight:700;letter-spacing:.08em}
</style></head><body><main><div class=card>__BODY__</div>
<p class=muted><a href=/>__BACK__</a></p></main></body></html>"""

# Hỏi trạng thái device flow ~3s; 'idle' (vd server vừa khởi động lại) -> về trang /login, hết hỏi.
_POLL_JS = """<script>
(function poll(){fetch('/login/status').then(r=>r.json()).then(s=>{
 if(s.state==='done'){document.getElementById('st').textContent=s.msg;return}
 if(s.state==='idle'){location.href='/login';return}
 setTimeout(poll,3000)}).catch(()=>setTimeout(poll,3000))})();
</script>"""

def _e(s):
    return html.escape(str(s or ""), quote=True)

def _link(url):
    """Chỉ https:// mới thành link bấm được — chặn scheme lạ (javascript:…) dù nguồn là FE Identity."""
    u = str(url or "")
    return f'<a href="{_e(u)}" target=_blank rel="noopener noreferrer">{_e(u)}</a>' if u.startswith("https://") else _e(u)

def _form(action, inner, label):
    return (f'<form method=post action={action}><input type=hidden name=csrf value="{_e(_CSRF)}">'
            f'{inner}<button type=submit>{_e(label)}</button></form>')

def _start_form():
    return _form("/login/start",
                 f'<p><label for=campus>{_e(t("Mã campus (vd APHL)", "Campus code (e.g. APHL)"))}</label></p>'
                 f'<input id=campus name=campus maxlength={ARG_MAX} value="{_e(botlogin.default_campus())}">',
                 t("Bắt đầu đăng nhập", "Start sign-in"))

def _finish_form():
    return _form("/login/finish", '<textarea name=url rows=4 required autocomplete=off spellcheck=false></textarea>',
                 t("Hoàn tất đăng nhập", "Finish sign-in"))

def _waiting():
    """Đang chờ duyệt device flow (vd người dùng tải lại trang) -> khung trạng thái tự cập nhật."""
    if _DEVICE["state"] != "pending":
        return ""
    return "<pre id=st>" + _e(t("⏳ Đang chờ bạn duyệt trên trang FE Identity… trang tự cập nhật, không cần dán gì.",
                                "⏳ Waiting for your approval on the FE Identity page… this page updates "
                                "itself; nothing to paste.")) + "</pre>" + _POLL_JS

def _login_page(body):
    return _LOGIN_PAGE.replace("__BACK__", _e(t("← Về dashboard", "← Back to the dashboard"))) \
                      .replace("__BODY__", "<h1>🔐 " + _e(t("Đăng nhập FAP", "FAP sign-in")) + "</h1>" + body)

def _login_home():
    me, who = _me(), ""
    if me.get("roll"):
        who = t("Đang dùng: ", "Current: ") + me["roll"] + (" · " + me["campus"] if me.get("campus") else "") \
              + (t(" — token đã HẾT HẠN", " — token EXPIRED") if me.get("expired") else "")
    return _login_page(("<p class=muted>" + _e(who) + "</p>" if who else "") + "<p>" + _e(t(
        "Bạn đăng nhập Google @fpt.edu.vn trên trang của Google — mật khẩu không đi qua đây.",
        "You sign in with your @fpt.edu.vn Google account on Google's own page — no password passes "
        "through here.")) + "</p>" + _waiting() + _start_form())

def _login_start(form):
    campus = " ".join((form.get("campus") or [""])[0].split())[:ARG_MAX] or botlogin.default_campus()
    ok, text, mode = _LOGIN.start(campus)
    if not ok:                                           # thiếu campus (kèm danh sách) / bận / chỉ-đọc / lỗi mạng
        return _login_page("<pre>" + _e(text) + "</pre>" + _waiting() + _start_form())
    d = dict(_LOGIN.data or {})
    body = "<p>" + _e(t("Mở link này rồi đăng nhập Google @fpt.edu.vn:",
                        "Open this link and sign in with your @fpt.edu.vn Google account:")) + "</p><p>" \
           + _link(d.get("url")) + "</p>"
    if mode == "device":
        if d.get("user_code"):
            body += f'<p>{_e(t("Mã xác nhận:", "Confirmation code:"))} <span class=code>{_e(d["user_code"])}</span></p>'
        _DEVICE.update(state="pending", msg="")
        botlogin.finish_device(_LOGIN, _device_done)
        return _login_page(body + _waiting())
    return _login_page(body + "<p>" + _e(t(
        "Sau khi đăng nhập, trình duyệt sẽ báo lỗi kiểu “scheme … not registered” — ĐÚNG rồi. COPY URL trên "
        "thanh địa chỉ (io.identityserver.demo:/oauthredirect?code=…) rồi DÁN vào ô dưới, trong vòng vài chục giây.",
        "After signing in the browser fails with “scheme … not registered” — that is EXPECTED. Copy the URL "
        "from the address bar (io.identityserver.demo:/oauthredirect?code=…) and paste it below within "
        "a few dozen seconds.")) + "</p>" + _finish_form())

def _device_done(msg):
    _DEVICE["msg"] = msg                                 # msg TRƯỚC, state SAU (xem _DEVICE)
    _DEVICE["state"] = "done"

def _login_finish(form):
    pasted = (form.get("url") or [""])[0].strip()
    # dán nhầm -> nhắc, KHÔNG đóng phiên đang chờ. URL Google (calendar) cũng khớp mẫu FAP -> chặn, kẻo mã
    # Google bị gửi sang FE Identity.
    if not auth.looks_like_redirect(pasted) or looks_like_gredirect(pasted):
        return _login_page("<pre>" + _e(t(
            "Không thấy URL redirect — dán NGUYÊN URL trên thanh địa chỉ (io.identityserver.demo:/oauthredirect?code=…).",
            "That is not a redirect URL — paste the WHOLE address-bar URL "
            "(io.identityserver.demo:/oauthredirect?code=…).")) + "</pre>" + _finish_form())
    ok, msg = botlogin.finish_paste(_LOGIN, pasted)      # msg chỉ có roll + campus / lý do lỗi — không có URL
    return _login_page("<pre>" + _e(msg) + "</pre>" + ("" if ok else _start_form()))

class _H(http.server.BaseHTTPRequestHandler):
    def _send(self, body, ctype="text/html; charset=utf-8", code=200):
        b = body.encode("utf-8")
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("X-Frame-Options", "DENY")      # không cho trang khác nhúng (clickjacking nút đăng nhập)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def _host_ok(self):
        # Chống DNS-rebinding: CHỈ phục vụ khi Host là localhost đúng cổng. Bind 127.0.0.1 KHÔNG đủ —
        # trang web độc có thể rebind tên miền của nó về 127.0.0.1:<port> rồi đọc /me, /q (điểm/lịch/hồ sơ).
        port = self.server.server_address[1]
        allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if port == 80:                                    # trình duyệt LƯỢC ':80' (cổng HTTP mặc định) khỏi Host
            allowed |= {"127.0.0.1", "localhost"}
        return (self.headers.get("Host") or "").strip().lower() in allowed

    def do_POST(self):
        if not self._host_ok():
            return self._send("forbidden", "text/plain; charset=utf-8", 403)
        # Origin có mặt thì phải CÙNG gốc (trình duyệt luôn gửi Origin với POST cross-site).
        origin = self.headers.get("Origin")
        if origin is not None and origin.strip().lower() != "http://" + (self.headers.get("Host") or "").strip().lower():
            return self._send("forbidden", "text/plain; charset=utf-8", 403)
        path = urllib.parse.urlparse(self.path).path
        if path not in ("/login/start", "/login/finish"):
            return self._send("not found", "text/plain; charset=utf-8", 404)
        try:
            n = int(self.headers.get("Content-Length") or "")
        except ValueError:
            return self._send("length required", "text/plain; charset=utf-8", 411)
        if not 0 <= n <= BODY_MAX:
            return self._send("too large", "text/plain; charset=utf-8", 413)
        form = urllib.parse.parse_qs(self.rfile.read(n).decode("utf-8", "replace"))
        if not hmac.compare_digest((form.get("csrf") or [""])[0].encode("utf-8"), _CSRF.encode("utf-8")):
            return self._send("forbidden (csrf)", "text/plain; charset=utf-8", 403)
        return self._send(_login_start(form) if path == "/login/start" else _login_finish(form))

    def do_GET(self):
        if not self._host_ok():
            return self._send("forbidden", "text/plain; charset=utf-8", 403)
        u = urllib.parse.urlparse(self.path)
        if u.path == "/":
            return self._send(_page())
        if u.path == "/login":
            return self._send(_login_home())
        if u.path == "/login/status":                    # đọc state TRƯỚC msg (xem _device_done)
            st = _DEVICE["state"]
            return self._send(json.dumps({"state": st, "msg": _DEVICE["msg"] if st == "done" else ""},
                                         ensure_ascii=False), "application/json; charset=utf-8")
        if u.path == "/me":
            return self._send(json.dumps(_me(), ensure_ascii=False), "application/json; charset=utf-8")
        if u.path == "/q":
            q = urllib.parse.parse_qs(u.query)
            c = q.get("c", ["status"])[0]
            if c not in COMMANDS:
                c = "help"
            # ?a= tham số (mã môn / view / điểm). Kẹp như `c`: gom khoảng trắng (bỏ xuống dòng, tab)
            # rồi cắt ARG_MAX ký tự — không để query lạ bơm chuỗi dài vào lõi.
            a = " ".join((q.get("a", [""])[0] or "").split())[:ARG_MAX] or None
            try:
                txt = handle(c, a)
            except SystemExit as e:                      # token hết hạn... -> hiện thông điệp, không 500
                txt = str(e)
            except Exception as e:                       # noqa: BLE001
                txt = f"Lỗi · error: {e}"
            return self._send(txt, "text/plain; charset=utf-8")
        self._send("not found", "text/plain; charset=utf-8", 404)

    def log_message(self, *a):                           # im lặng, không spam console
        pass

def run(port=8000):
    try: port = int(port)
    except (TypeError, ValueError): port = 8000
    os.environ.setdefault("FAP_CACHE_MIN", "2")           # bấm nhiều nút không gọi lại API trong 2' (nhẹ máy yếu)
    try:
        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), _H)   # CHỈ localhost
    except OSError as e:                                   # cổng đang bận -> báo rõ thay vì traceback
        print(t(f"❌ Không mở được cổng {port} ({e}). Thử cổng khác, ví dụ: fap web 8765",
                f"❌ Cannot bind port {port} ({e}). Try another port, e.g.: fap web 8765"))
        return
    url = f"http://127.0.0.1:{port}/"
    print(t(f"🌐 Web dashboard: {url}   (Ctrl+C để dừng)", f"🌐 Web dashboard: {url}   (Ctrl+C to stop)"))
    try: webbrowser.open(url)
    except Exception: pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã dừng."); httpd.shutdown()

def main():
    import sys
    run(sys.argv[1] if len(sys.argv) > 1 else 8000)

if __name__ == "__main__":
    main()
