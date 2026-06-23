"""fapc — fap-cli. Đăng nhập FAP qua OAuth + kéo dữ liệu + .ics + Google Calendar + notify."""
__version__ = "0.1.0"

# Nạp .env NGAY khi import package (trước mọi submodule) để api.py thấy FAP_SEMESTER.
import os as _os

def _load_env():
    root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    p = _os.path.join(root, ".env")
    if not _os.path.exists(p):
        return
    for line in open(p, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            _os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))   # bỏ nháy bao quanh

_load_env()
