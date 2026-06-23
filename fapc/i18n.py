#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""i18n.py — song ngữ tối giản. t(vi, en) -> chuỗi theo FAP_LANG."""
from .config import FAP_LANG

def t(vi, en):
    return en if str(FAP_LANG).lower().startswith("en") else vi
