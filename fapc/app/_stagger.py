#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_stagger.py — MỘT nơi duy nhất quyết định 3 service thường trú refresh token LỆCH NHAU.

`deploy/update.sh` restart gradewatch + attendwatch + reminders liên tiếp. Nếu cả ba bắt đầu với
`last_refresh = 0` thì cả ba gọi `refresh_tokens()` trong vài giây, cùng đọc MỘT refresh_token đang
XOAY VÒNG — hai đứa thua cuộc nhận 400, và nếu IdP thu hồi cả grant khi refresh_token bị dùng lại thì
hỏng luôn dù chỉ có 1 máy (xem docs/18-roadmap.md §2b).

Trước đây ba file tự chế ba cách khác nhau và các dải CHỒNG nhau (gradewatch dùng phút, hai file kia
dùng giây, mốc 180s của gradewatch trùng đúng đầu dải của reminders). Giờ chỉ còn bảng dưới đây.

Vì sao dải NHỎ (giây) chứ không phải phút: refresh mất ~1s, nên cách nhau vài giây là đủ hết đua —
và quan trọng hơn, service sau ĐỌC ĐƯỢC refresh_token mới do service trước vừa ghi, thay vì cầm bản
cũ đã bị xoay vòng. Giãn ra hàng phút không giải quyết được điều đó, chỉ dời nó đi.
"""
import random, time

# giây, mốc đầu dải của từng service — RỜI NHAU, không chồng.
_SLOT = {"gradewatch": 0, "attendwatch": 8, "reminders": 16}
_BAND = 8                     # jitter TRONG dải: 2 profile chạy cùng service cũng lệch nhau


def startup_delay(service):
    """Số giây NÊN chờ trước lần refresh đầu tiên. Dùng cho service có vòng lặp DÀI (watcher):
    ngủ chừng này rồi refresh ngay, để lần poll ĐẦU vẫn có token còn hạn (nếu seed vào `last_refresh`
    thì lần refresh đầu bị đẩy sang vòng lặp sau — có thể tận 60 phút)."""
    return _SLOT.get(service, 0) + random.random() * _BAND


def first_refresh_mark(service, refresh_min, now=None):
    """Giá trị `last_refresh` ban đầu cho service có vòng lặp NGẮN (reminders tick ~20–60s):
    lần refresh đầu rơi vào dải riêng, và vì tick dày nên nó vẫn xảy ra sớm. THUẦN, không IO."""
    now = time.time() if now is None else now
    return now - refresh_min * 60 + startup_delay(service)
