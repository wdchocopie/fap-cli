#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""webui.py — Web dashboard cục bộ (Python stdlib, KHÔNG thêm thư viện).

    fap web            # mở http://127.0.0.1:8000
    fap web 8765       # đổi cổng

Trang 1 file: bấm nút -> GET /q?c=<lệnh> -> bot_core.handle() (tái dùng đúng lõi như bot/CLI).
CHỈ bind 127.0.0.1 — KHÔNG phơi dữ liệu ra mạng. Cần token còn hạn (fap login/refresh).
Tự bật cache 2' (FAP_CACHE_MIN) để bấm nhiều lần không gọi lại API — nhẹ máy yếu / lịch sự với server.
"""
import os, json, http.server, urllib.parse, webbrowser
from .bot_core import handle, COMMANDS
from ..core.api import TOKEN_JSON
from ..i18n import t

# Nhóm nút (chỉ lệnh có trong COMMANDS) — gọn gàng theo chủ đề.
_GROUPS = [
    ("Tổng quan", [("status", "📋", "Tổng quan"), ("all", "📚", "Tất cả")]),
    ("Lịch", [("today", "📅", "Hôm nay"), ("tomorrow", "⏭️", "Ngày mai"), ("week", "📆", "Tuần"), ("exams", "📝", "Lịch thi")]),
    ("Điểm", [("grades", "📊", "Điểm"), ("grades-detail", "🧮", "Điểm TP"), ("gpa", "📈", "GPA"),
              ("whatif", "🎯", "What-if"), ("attendance", "🟢", "Điểm danh"), ("banrisk", "⚠️", "Cấm thi")]),
    ("Khác", [("notifications", "🔔", "Thông báo"), ("applications", "📄", "Đơn từ"), ("profile", "👤", "Hồ sơ")]),
]

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
 main{display:flex;gap:1rem;max-width:1000px;margin:1rem auto;padding:0 1rem;align-items:flex-start}
 nav{flex:0 0 210px;display:flex;flex-direction:column;gap:.9rem}
 .grp h2{font-size:.72rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin:.1rem .2rem .35rem}
 .grp{display:flex;flex-direction:column;gap:.3rem}
 button{display:flex;align-items:center;gap:.55rem;width:100%;text-align:left;padding:.5rem .7rem;border:0;
   border-radius:9px;background:var(--btn);color:var(--fg);cursor:pointer;font-size:.93rem;transition:.12s}
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
 <label class=toggle><input type=checkbox id=auto> tự làm mới 60s</label>
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
 let cur='status',timer=null,labels={};
 GROUPS.forEach(([g,items])=>{const d=document.createElement('div');d.className='grp';
   d.innerHTML='<h2>'+g+'</h2>';items.forEach(([c,e,l])=>{labels[c]=e+' '+l;
     const b=document.createElement('button');b.dataset.c=c;
     b.innerHTML='<span class=e>'+e+'</span>'+l;b.onclick=()=>load(c);d.appendChild(b)});nav.appendChild(d)});
 function mark(c){document.querySelectorAll('button').forEach(b=>b.classList.toggle('active',b.dataset.c===c))}
 async function load(c){cur=c;mark(c);title.textContent=labels[c]||c;hd.classList.add('loading');
   try{const r=await fetch('/q?c='+encodeURIComponent(c));out.textContent=await r.text()}
   catch(e){out.textContent='Lỗi kết nối: '+e}finally{hd.classList.remove('loading')}}
 document.getElementById('auto').onchange=e=>{clearInterval(timer);
   if(e.target.checked)timer=setInterval(()=>load(cur),60000)};
 fetch('/me').then(r=>r.json()).then(m=>{if(m&&m.roll)document.getElementById('who').textContent=
   '· '+(m.name||'')+' ('+m.roll+(m.campus?' · '+m.campus:'')+')'}).catch(()=>{});
 load('status');
</script></body></html>"""


def _page():
    return _PAGE.replace("__GROUPS__", json.dumps(_GROUPS, ensure_ascii=False))

def _me():
    try:
        with open(TOKEN_JSON, encoding="utf-8") as f:
            m = json.load(f)
        return {"name": m.get("fullname") or "", "roll": m.get("rollnumber") or "", "campus": m.get("campus") or ""}
    except Exception:                                    # noqa: BLE001 — chưa login -> header trống
        return {}

class _H(http.server.BaseHTTPRequestHandler):
    def _send(self, body, ctype="text/html; charset=utf-8", code=200):
        b = body.encode("utf-8")
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b))); self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == "/":
            return self._send(_page())
        if u.path == "/me":
            return self._send(json.dumps(_me(), ensure_ascii=False), "application/json; charset=utf-8")
        if u.path == "/q":
            c = urllib.parse.parse_qs(u.query).get("c", ["status"])[0]
            if c not in COMMANDS:
                c = "help"
            try:
                txt = handle(c)
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
