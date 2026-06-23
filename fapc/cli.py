#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shim tương thích ngược · backward-compat shim.

Entry point chính giờ là `fapc.app.cli:main` (xem pyproject.toml). Giữ file này để:
  • bản đã cài CŨ có `fap.exe` trỏ `fapc.cli:main` vẫn chạy được (không cần cài lại);
  • `python -m fapc.cli ...` vẫn hoạt động.
"""
from .app.cli import main

if __name__ == "__main__":
    main()
