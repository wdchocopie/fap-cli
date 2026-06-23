# Cài đặt & Bắt đầu nhanh · Installation & Quickstart

**VI —** Tài liệu này hướng dẫn cài `fapc` (lệnh `fap`) và chạy lần đầu để kéo dữ liệu FAP của **chính bạn**. Chỉ dùng cho tài khoản & dữ liệu của bạn.
**EN —** This page covers installing `fapc` (the `fap` command) and the first run to pull **your own** FAP data. For your own account & data only.

## Yêu cầu · Requirements

| Mục · Item | Chi tiết · Detail |
|---|---|
| Python | `>=3.7` · đã kiểm trên 3.10 · tested on 3.10 |
| Phụ thuộc lõi · Core dep | `requests>=2.28` (`requirements.txt`) |
| Calendar (tuỳ chọn · optional) | `google-api-python-client`, `google-auth-httplib2`, `google-auth-oauthlib` (`requirements-gcal.txt`) |
| Tài khoản · Account | Google `@fpt.edu.vn` (đăng nhập qua FE Identity · login via FE Identity) |

## 1. Cài đặt · Install

**VI —** Từ thư mục gốc repo, cài ở chế độ editable để tạo lệnh `fap`:
**EN —** From the repo root, install in editable mode to create the `fap` command:

```bash
pip install -e .
```

**VI —** Nếu cần đẩy lịch thẳng lên Google Calendar, cài thêm extra `gcal`:
**EN —** If you want to push schedule directly to Google Calendar, add the `gcal` extra:

```bash
pip install -e ".[gcal]"
```

> **VI —** Extra `gcal` chỉ cần cho `fap calendar-auth` / `fap calendar-sync`. Các lệnh khác chạy được mà không cần nó.
> **EN —** The `gcal` extra is only needed for `fap calendar-auth` / `fap calendar-sync`. Everything else works without it.

## 2. Chạy lần đầu · First run

**VI —** Thứ tự khuyến nghị: đăng nhập → tự kiểm tra → kéo dữ liệu.
**EN —** Recommended order: login → self-check → pull data.

```bash
fap login        # đăng nhập Google @fpt.edu.vn 1 lần · one-time Google login → output/token.json
fap doctor       # tự kiểm tra môi trường · self-check
fap extract      # kéo toàn bộ dữ liệu · pull everything → output/
fap ics          # xuất lịch · export → output/lichhoc.ics
```

### `fap login`

**VI —** Mở trình duyệt 1 lần. Sau khi đăng nhập Google `@fpt.edu.vn`, trình duyệt sẽ hiện báo lỗi kiểu `scheme ... not registered` — **đây là bình thường**. Copy URL trên thanh địa chỉ rồi dán vào prompt, **hoặc** chạy `fap exchange "<url>"`.
**EN —** Opens the browser once. After the Google `@fpt.edu.vn` login, the browser shows a `scheme ... not registered` error — **this is normal**. Copy the address-bar URL and paste it at the prompt, **or** run `fap exchange "<url>"`.

> **VI —** Các lần sau dùng `fap refresh` để làm mới token **không cần trình duyệt**, cho tới khi `refresh_token` hết hạn.
> **EN —** Later, use `fap refresh` to renew the token **headlessly** (no browser) until the `refresh_token` expires.

### `fap doctor`

**VI —** Tự kiểm tra: phiên bản Python, có `output/token.json` chưa, có `.env` không, đã cài `requests` / google libs chưa, và kênh notify đang bật.
**EN —** Self-check: Python version, whether `output/token.json` exists, whether `.env` exists, whether `requests` / google libs are installed, and which notify channels are active.

```text
Python      : 3.10.x
token.json  : ✓
.env        : ✓
requests    : ✓
google libs : — (chỉ cần cho calendar-sync · only needed for calendar-sync)
kênh notify : Telegram, Discord
```

## 3. Không cài package · No-install fallback

**VI —** Nếu không muốn `pip install -e .`, cài phụ thuộc rồi gọi module trực tiếp:
**EN —** If you'd rather not `pip install -e .`, install deps then call the module directly:

```bash
pip install -r requirements.txt
python -m fapc login
python -m fapc extract
```

> **VI —** `python -m fapc <cmd>` tương đương `fap <cmd>`. Cho Calendar: `pip install -r requirements-gcal.txt`.
> **EN —** `python -m fapc <cmd>` is equivalent to `fap <cmd>`. For Calendar: `pip install -r requirements-gcal.txt`.

## 4. Console Windows & UTF-8

**VI —** Nếu tiếng Việt/emoji bị vỡ font trên Windows, bật UTF-8 cho console:
**EN —** If Vietnamese/emoji is garbled on Windows, enable UTF-8 for the console:

```bash
chcp 65001
# hoặc · or
set PYTHONUTF8=1
```

> **VI —** Package cũng tự gọi `sys.stdout.reconfigure` sang utf-8, nên thường không cần làm gì thêm.
> **EN —** The package also calls `sys.stdout.reconfigure` to utf-8, so usually nothing extra is needed.

## Đường dẫn lần đầu · Happy path

```bash
pip install -e .          # cài lệnh fap · install the fap command
fap login                 # đăng nhập 1 lần · one-time login → output/token.json
fap doctor                # kiểm tra · sanity check
fap extract               # kéo dữ liệu · pull data → output/api/*.json
fap ics                   # xuất lịch · export → output/lichhoc.ics
```

> **VI —** `output/`, `.env`, `credentials.json` đều đã `.gitignore` (chứa token & dữ liệu cá nhân). Kiểm `git status` trước khi commit, đừng `git add -f` chúng.
> **EN —** `output/`, `.env`, `credentials.json` are all `.gitignored` (they hold tokens & personal data). Check `git status` before committing; never `git add -f` them.

## Tiếp theo · Next

| Tài liệu · Doc | Nội dung · About |
|---|---|
| [`11-commands`](11-commands.md) | Toàn bộ lệnh `fap` · the full `fap` command set |
| [`12-google-calendar`](12-google-calendar.md) | `calendar-auth` / `calendar-sync` + `credentials.json` |
| [`13-notify`](13-notify.md) | `notify` qua Telegram / Discord · push via Telegram / Discord |
| [`15-config`](15-config.md) | `.env`: `FAP_LANG`, `FAP_SEMESTER`, token, GCAL... |
