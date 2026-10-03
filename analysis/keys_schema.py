#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""keys_schema.py — sơ đồ TRƯỜNG (chỉ tên khoá) của các phản hồi API đã dump, KHÔNG BAO GIỜ in giá trị.

    fap extract                               # dump mọi endpoint đọc-được -> output/api/*.json
    python analysis/keys_schema.py            # in sơ đồ ra màn hình
    python analysis/keys_schema.py out.txt    # ghi ra file (để ngoài repo/scratchpad nếu muốn)

Dùng để kiểm lại "server trả thêm/bớt trường gì" sau khi FAP cập nhật app, và làm đầu vào an toàn cho
audit trường-chưa-dùng (docs/20-api-fields.md). Mỗi dòng: đường dẫn khoá | kiểu giá trị | số lần có giá trị/số lần xuất hiện.

QUYỀN RIÊNG TƯ: output/ chứa token + dữ liệu cá nhân (GetStudentById có CCCD, SĐT, thông tin phụ huynh…).
Script này chỉ in TÊN KHOÁ, KIỂU và TỈ LỆ CÓ GIÁ TRỊ. Khoá trông không giống định danh (có thể là dữ liệu:
mã SV, ngày, mã môn dùng làm khoá) bị gộp thành <dynamic> — nên dữ liệu cũng không lọt qua tên khoá.
Kiểu được suy từ HÌNH DẠNG (str(url), str(date), str(html)…), không chép giá trị.
"""
import collections, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "output", "api")
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,60}$")
_EMPTY = {"", "null", "none", "n/a", "na", "-", "undefined"}


def _empty(v):
    if v is None:
        return True
    if isinstance(v, str):
        return v.strip().lower() in _EMPTY
    if isinstance(v, (list, dict)):
        return not v
    return False


def _kind(v):
    """Kiểu theo HÌNH DẠNG — không bao giờ trả lại giá trị."""
    if v is None: return "null"
    if isinstance(v, bool): return "bool"
    if isinstance(v, int): return "int"
    if isinstance(v, float): return "float"
    if isinstance(v, list): return "list"
    if isinstance(v, dict): return "dict"
    s = str(v).strip()
    if s.lower() in ("true", "false"): return "str(bool)"
    if re.match(r"^-?\d+(\.\d+)?$", s): return "str(num)"
    if s.lower().startswith(("http://", "https://")): return "str(url)"
    if "<" in s and ">" in s: return "str(html)"
    if re.match(r"^\d{1,4}[-/]\d{1,2}[-/]\d{1,4}", s): return "str(date)"
    return "str"


def _walk(v, path, stats):
    st = stats[path]
    st["n"] += 1
    st["kinds"][_kind(v)] += 1
    st["filled"] += 0 if _empty(v) else 1
    if isinstance(v, dict):
        for k, sub in v.items():
            key = k if _IDENT.match(str(k)) else "<dynamic>"
            _walk(sub, f"{path}.{key}" if path else key, stats)
    elif isinstance(v, list):
        for item in v:
            _walk(item, f"{path}[]", stats)


def schema(src=SRC):
    """{endpoint: [(path, kinds, filled, n)]}. Dump courseAttendance__<môn>.json gộp thành getCourseAttendance."""
    groups = collections.defaultdict(list)
    for name in sorted(os.listdir(src)):
        if name.endswith(".json"):
            ep = "getCourseAttendance" if name.startswith("courseAttendance__") else name[:-5]
            groups[ep].append(os.path.join(src, name))
    out = {}
    for ep, files in groups.items():
        stats = collections.defaultdict(lambda: {"n": 0, "filled": 0, "kinds": collections.Counter()})
        for fp in files:
            try:
                with open(fp, encoding="utf-8") as f:
                    _walk(json.load(f), "", stats)
            except (OSError, ValueError) as e:
                stats["<unreadable>"]["n"] += 1
                stats["<unreadable>"]["kinds"][type(e).__name__] += 1
        out[ep] = (len(files), [(p, ",".join(k for k, _ in s["kinds"].most_common()), s["filled"], s["n"])
                                for p, s in sorted(stats.items()) if p])
    return out


def render(sch):
    lines = [f"# keys-only schema of {len(sch)} endpoints (values are never printed)",
             "# path | kinds | populated/occurrences", ""]
    for ep, (nfiles, rows) in sch.items():
        lines.append(f"## {ep}  ({nfiles} dump file{'s' if nfiles > 1 else ''})")
        lines += [f"  {p} | {k} | {f}/{n}" for p, k, f, n in rows]
        lines.append("")
    return "\n".join(lines)


def main(argv):
    if not os.path.isdir(SRC):
        sys.exit(f"Không thấy {SRC} — chạy `fap extract` trước. · Run `fap extract` first.")
    text = render(schema())
    if len(argv) > 1:
        with open(argv[1], "w", encoding="utf-8") as f:
            f.write(text)
        print(f"wrote {argv[1]}")
    else:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:                                  # noqa: BLE001
            pass
        print(text)


if __name__ == "__main__":
    main(sys.argv)
