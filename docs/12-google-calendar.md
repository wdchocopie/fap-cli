# Đồng bộ Google Calendar · Sync to Google Calendar

**VI —** Hướng dẫn này giúp bạn đẩy thời khóa biểu FAP **thẳng lên Google Calendar** qua OAuth. Khác với file `.ics` (import thủ công 1 lần), cách này **tự đồng bộ**: chạy lại = cập nhật, không tạo trùng (dedup theo `iCalUID`). Có thể đặt lịch chạy định kỳ.
**EN —** This guide pushes your FAP timetable **directly into Google Calendar** via OAuth. Unlike the `.ics` file (a one-off manual import), this **auto-syncs**: re-running updates events instead of duplicating them (dedup by `iCalUID`). You can schedule it to run periodically.

> **VI —** Chỉ xin quyền **ghi sự kiện** (`calendar.events`) — không đọc/sửa lịch khác của bạn. Token Google lưu ở `output/gcal_token.json` và đã được `.gitignore` — **đừng commit**.
> **EN —** Only the **event-write** scope (`calendar.events`) is requested — it cannot read or touch your other calendars. The Google token lives in `output/gcal_token.json`, which is `.gitignore`d — **never commit it**.

---

## 0. Tổng quan luồng · Flow at a glance

| Bước · Step | Việc cần làm · What you do |
|---|---|
| 1 | **VI —** Lấy `credentials.json` từ Google Cloud Console (phần lớn của doc này) · **EN —** Get `credentials.json` from Google Cloud Console (most of this doc) |
| 2 | **VI —** Cài thư viện Google: `pip install -e ".[gcal]"` · **EN —** Install Google libs: `pip install -e ".[gcal]"` |
| 3 | **VI —** Đăng nhập 1 lần: `fap calendar-auth` → `output/gcal_token.json` · **EN —** One-time login: `fap calendar-auth` → `output/gcal_token.json` |
| 4 | **VI —** Đẩy lịch: `fap calendar-sync` (chạy lại = cập nhật) · **EN —** Push: `fap calendar-sync` (re-run = update) |

---

## 1. Lấy `credentials.json` từ Google Cloud Console · Get `credentials.json`

**VI —** Đây là phần dài nhất, nhưng chỉ làm **một lần**. Mỗi bước mô tả chính xác chỗ bấm. Console của Google đôi khi đổi giao diện nhẹ — nếu chữ hơi khác, tìm nút có nghĩa tương đương.
**EN —** This is the longest part but you do it **once**. Each step says exactly what to click. Google may tweak the UI slightly — if wording differs, look for the equivalent button.

### 1.1 Tạo / chọn project · Create or select a project

1. **VI —** Mở <https://console.cloud.google.com/> và đăng nhập bằng **chính tài khoản `@fpt.edu.vn`** của bạn (you@fpt.edu.vn).
   **EN —** Open <https://console.cloud.google.com/> and sign in with **your own `@fpt.edu.vn` account** (you@fpt.edu.vn).
2. **VI —** Trên thanh trên cùng, bấm vào ô chọn project (cạnh logo "Google Cloud") → bấm **"New Project"**.
   **EN —** In the top bar, click the project picker (next to the "Google Cloud" logo) → click **"New Project"**.

   > 📷 *VI — Ảnh: ô chọn project ở thanh trên cùng · EN — Screenshot: project picker in the top bar*

3. **VI —** Đặt tên bất kỳ, ví dụ `fap-cli`, để mục Organization mặc định → bấm **"Create"**. Chờ vài giây rồi chọn project vừa tạo.
   **EN —** Name it anything, e.g. `fap-cli`, leave Organization as default → click **"Create"**. Wait a few seconds, then select the new project.

### 1.2 Bật Google Calendar API · Enable the Google Calendar API

4. **VI —** Menu trái (☰) → **"APIs & Services"** → **"Library"**. Trong ô tìm kiếm gõ **`Google Calendar API`**.
   **EN —** Left menu (☰) → **"APIs & Services"** → **"Library"**. Search for **`Google Calendar API`**.
5. **VI —** Bấm vào kết quả **"Google Calendar API"** → bấm nút **"Enable"**.
   **EN —** Click the **"Google Calendar API"** result → click **"Enable"**.

   > 📷 *VI — Ảnh: trang Calendar API với nút "Enable" · EN — Screenshot: Calendar API page with the "Enable" button*

### 1.3 Cấu hình OAuth consent screen · Configure the OAuth consent screen

6. **VI —** Menu trái → **"APIs & Services"** → **"OAuth consent screen"**.
   **EN —** Left menu → **"APIs & Services"** → **"OAuth consent screen"**.
7. **VI —** Chọn **User Type = External** → **"Create"**. (Tài khoản `@fpt.edu.vn` là tổ chức ngoài Google Cloud project của bạn, nên dùng External.)
   **EN —** Choose **User Type = External** → **"Create"**. (Your `@fpt.edu.vn` account is external to your Cloud project, so use External.)
8. **VI —** Điền tối thiểu: **App name** (ví dụ `fap-cli`), **User support email** (chọn email của bạn), và **Developer contact email** (you@fpt.edu.vn). Các mục khác bỏ trống được → **"Save and Continue"**.
   **EN —** Fill the minimum: **App name** (e.g. `fap-cli`), **User support email** (pick yours), and **Developer contact email** (you@fpt.edu.vn). Leave the rest blank → **"Save and Continue"**.
9. **VI —** Bước **"Scopes"**: không cần thêm gì (tool tự xin `calendar.events` khi đăng nhập) → **"Save and Continue"**.
   **EN —** **"Scopes"** step: add nothing (the tool requests `calendar.events` itself at login) → **"Save and Continue"**.
10. **VI —** Bước **"Test users"** → bấm **"+ Add Users"** → nhập **you@fpt.edu.vn** (chính email bạn sẽ dùng để đồng bộ) → **"Add"** → **"Save and Continue"**.
    **EN —** **"Test users"** step → click **"+ Add Users"** → enter **you@fpt.edu.vn** (the very account you'll sync with) → **"Add"** → **"Save and Continue"**.

    > 📷 *VI — Ảnh: thêm email bạn vào danh sách Test users · EN — Screenshot: adding your email to Test users*

    > **VI —** App ở chế độ **"Testing"** là đủ — bạn không cần "Publish" hay xác minh. Chỉ những email trong Test users mới đăng nhập được, và đó chính là bạn.
    > **EN —** Leaving the app in **"Testing"** mode is fine — no "Publish" or verification needed. Only emails in Test users can sign in, which is exactly you.

### 1.4 Tạo OAuth client ID (Desktop app) · Create the OAuth client ID

11. **VI —** Menu trái → **"APIs & Services"** → **"Credentials"** → bấm **"+ Create Credentials"** → chọn **"OAuth client ID"**.
    **EN —** Left menu → **"APIs & Services"** → **"Credentials"** → click **"+ Create Credentials"** → choose **"OAuth client ID"**.
12. **VI —** Ở **"Application type"** chọn **"Desktop app"** (rất quan trọng — tool dùng luồng desktop, mở trình duyệt cục bộ). Đặt tên tùy ý → **"Create"**.
    **EN —** For **"Application type"** pick **"Desktop app"** (important — the tool uses the desktop flow with a local browser). Name it anything → **"Create"**.

    > 📷 *VI — Ảnh: chọn "Desktop app" làm Application type · EN — Screenshot: selecting "Desktop app" as the Application type*

13. **VI —** Hộp thoại hiện ra → bấm **"Download JSON"** (hoặc biểu tượng tải ⬇ ở dòng client trong danh sách Credentials).
    **EN —** A dialog appears → click **"Download JSON"** (or the download ⬇ icon on the client's row in the Credentials list).

### 1.5 Lưu thành `credentials.json` ở gốc repo · Save as `credentials.json` at the repo root

14. **VI —** Đổi tên file vừa tải (kiểu `client_secret_....json`) thành đúng **`credentials.json`** và đặt ngay **gốc repo** (cùng cấp với `.env`):
    **EN —** Rename the downloaded file (something like `client_secret_....json`) to exactly **`credentials.json`** and place it at the **repo root** (next to `.env`):

    ```
    fap-cli/
    ├─ .env
    ├─ credentials.json   ← đặt ở đây · put it here
    └─ fapc/
    ```

    > **VI —** `credentials.json` đã nằm trong `.gitignore` — nó không phải mật khẩu Google, nhưng vẫn là bí mật ứng dụng, **đừng commit / chia sẻ**.
    > **EN —** `credentials.json` is already `.gitignore`d — it isn't your Google password, but it is an app secret, so **don't commit or share it**.

---

## 2. Cài thư viện Google · Install the Google libraries

**VI —** Phần đồng bộ Calendar cần thêm thư viện Google. Cài bằng "extra" `gcal` (chạy từ gốc repo):
**EN —** Calendar sync needs extra Google libraries. Install them via the `gcal` extra (run from the repo root):

```bash
pip install -e ".[gcal]"
```

**VI —** Lệnh này kéo về `google-api-python-client`, `google-auth-oauthlib`, `google-auth-httplib2` (liệt kê trong `requirements-gcal.txt`). Nếu thiếu, `fap calendar-auth`/`calendar-sync` sẽ báo lỗi nhắc cài.
**EN —** This pulls in `google-api-python-client`, `google-auth-oauthlib`, `google-auth-httplib2` (listed in `requirements-gcal.txt`). If they're missing, `fap calendar-auth`/`calendar-sync` will print an install reminder.

> **VI —** Chưa cài gói? Dùng dạng dự phòng `python -m fapc <lệnh>` thay cho `fap <lệnh>`.
> **EN —** Haven't installed the package? Use the fallback form `python -m fapc <command>` instead of `fap <command>`.

---

## 3. Đăng nhập Google 1 lần · One-time Google login

```bash
fap calendar-auth
```

**VI —** Lệnh mở trình duyệt → bạn đăng nhập bằng **you@fpt.edu.vn** (đúng email đã thêm vào Test users) và đồng ý quyền **ghi sự kiện**. Vì app đang ở chế độ Testing, Google có thể cảnh báo "app chưa được xác minh" — bấm **"Advanced" → "Go to … (unsafe)"** để tiếp tục (an toàn vì đây là app của chính bạn).
**EN —** This opens a browser → sign in with **you@fpt.edu.vn** (the email you added to Test users) and approve the **event-write** permission. Because the app is in Testing mode, Google may warn that the "app isn't verified" — click **"Advanced" → "Go to … (unsafe)"** to continue (safe, since it's your own app).

**VI —** Thành công sẽ in:
**EN —** On success it prints:

```text
✓ Đã xác thực Google -> output/gcal_token.json
```

**VI —** Token lưu ở `output/gcal_token.json`. Lần sau hết hạn, tool **tự refresh không cần mở trình duyệt** (nhờ refresh token). Bạn chỉ chạy lại `calendar-auth` nếu xóa file token hoặc đổi quyền.
**EN —** The token is saved at `output/gcal_token.json`. When it later expires, the tool **refreshes silently without a browser** (using the refresh token). You only re-run `calendar-auth` if you delete the token file or change scopes.

---

## 4. Đẩy lịch lên Google Calendar · Push to Google Calendar

```bash
fap calendar-sync
```

**VI —** Tool sẽ: lấy thời khóa biểu của **kỳ hiện tại** (auto-detect hoặc theo `FAP_SEMESTER`), rồi đẩy từng buổi lên Google Calendar. Ví dụ output:
**EN —** The tool fetches your **current semester** timetable (auto-detected, or forced via `FAP_SEMESTER`), then pushes each session to Google Calendar. Example output:

```text
Lấy 96 buổi (kỳ Summer2026). Đang đẩy lên Calendar 'primary'...
✓ Đồng bộ 96 sự kiện (lỗi 0). Chạy lại = cập nhật, không trùng.
```

**VI —** Mỗi buổi học thành 1 sự kiện với tiêu đề `<MãMôn> @ <Phòng>` (hoặc `(Online)`), kèm mô tả (lớp, slot, giảng viên, buổi). Múi giờ luôn là **`Asia/Ho_Chi_Minh`** (cố định trong code, không phải biến `.env`).
**EN —** Each session becomes one event titled `<SubjectCode> @ <Room>` (or `(Online)`), with a description (group, slot, lecturer, session no.). The timezone is always **`Asia/Ho_Chi_Minh`** (hard-coded, not an `.env` key).

### Chạy lại = cập nhật, không trùng · Re-run = update, no duplicates

**VI —** Mỗi sự kiện có `iCalUID` ổn định dạng `fapc-YYYYMMDD-<Môn>-<Slot>@fap.fpt.edu.vn`. Khi đồng bộ, tool dùng cơ chế **upsert theo `iCalUID`** — nên chạy lại sau khi đổi phòng/giờ sẽ **cập nhật** đúng sự kiện cũ thay vì tạo bản trùng.
**EN —** Every event has a stable `iCalUID` like `fapc-YYYYMMDD-<Subject>-<Slot>@fap.fpt.edu.vn`. On sync the tool **upserts by `iCalUID`** — so re-running after a room/time change **updates** the existing event instead of creating a duplicate.

---

## 5. Chọn lịch đích · Choosing the target calendar (`GCAL_CALENDAR_ID`)

**VI —** Mặc định tool đẩy vào lịch chính của bạn (`primary`). Muốn đẩy vào một lịch riêng (ví dụ lịch tên "Trường"), đặt biến trong `.env`:
**EN —** By default the tool pushes to your main calendar (`primary`). To target a separate calendar (e.g. one named "School"), set this in `.env`:

```ini
# .env
GCAL_CALENDAR_ID=primary
```

| Giá trị · Value | Ý nghĩa · Meaning |
|---|---|
| `primary` *(mặc định · default)* | **VI —** Lịch chính của tài khoản · **EN —** Your account's main calendar |
| `xxxxx@group.calendar.google.com` | **VI —** ID của một lịch phụ (lấy ở Google Calendar → Settings của lịch đó → "Integrate calendar" → "Calendar ID") · **EN —** A secondary calendar's ID (Google Calendar → that calendar's Settings → "Integrate calendar" → "Calendar ID") |

> **VI —** Lịch phụ phải do **chính tài khoản đã `calendar-auth`** sở hữu (hoặc có quyền ghi), vì tool chỉ xin scope `calendar.events`.
> **EN —** The secondary calendar must be owned (or writable) by the **same account you ran `calendar-auth` with**, since the tool only requests the `calendar.events` scope.

---

## 6. Khác gì so với `fap ics`? · How is this different from `fap ics`?

| | `fap calendar-sync` | `fap ics` |
|---|---|---|
| Cách hoạt động · How | **VI —** Đẩy thẳng qua Calendar API · **EN —** Pushes via the Calendar API | **VI —** Xuất file `output/lichhoc.ics` · **EN —** Exports `output/lichhoc.ics` |
| Cập nhật · Updates | **VI —** Tự upsert theo `iCalUID`, chạy lại = cập nhật · **EN —** Auto-upsert by `iCalUID`, re-run = update | **VI —** Import thủ công lại mỗi lần · **EN —** Manual re-import each time |
| Cài đặt · Setup | **VI —** Cần `credentials.json` + `[gcal]` + đăng nhập · **EN —** Needs `credentials.json` + `[gcal]` + login | **VI —** Không cần OAuth Google · **EN —** No Google OAuth |
| Đưa vào lịch · Into calendar | **VI —** Tự động · **EN —** Automatic | **VI —** Google Calendar → **Settings → Import** → chọn file `.ics` · **EN —** Google Calendar → **Settings → Import** → pick the `.ics` file |

**VI —** Tóm lại: dùng `calendar-sync` nếu muốn đồng bộ tự động lặp lại; dùng `ics` nếu chỉ cần 1 file để import nhanh hoặc import vào app lịch khác (Outlook, Apple Calendar…).
**EN —** In short: use `calendar-sync` for repeatable auto-sync; use `ics` if you just want a one-file quick import or to load into another calendar app (Outlook, Apple Calendar, …).

---

## 7. Khắc phục sự cố · Troubleshooting

| Triệu chứng · Symptom | Cách xử lý · Fix |
|---|---|
| `Thiếu credentials.json` · `Missing credentials.json` | **VI —** Làm lại Mục 1: tải OAuth "Desktop app" JSON, lưu thành `credentials.json` ở gốc repo · **EN —** Redo Section 1: download the "Desktop app" OAuth JSON, save as `credentials.json` at the repo root |
| `Thiếu thư viện Google` · `Missing Google libs` | **VI —** Chạy `pip install -e ".[gcal]"` · **EN —** Run `pip install -e ".[gcal]"` |
| `Chưa xác thực Google` · `Not authorized` | **VI —** Chạy `fap calendar-auth` trước · **EN —** Run `fap calendar-auth` first |
| **VI —** Google chặn "app chưa xác minh" · **EN —** Google blocks "app not verified" | **VI —** Email bạn phải nằm trong **Test users** (Mục 1.3, bước 10); rồi "Advanced → Go to … (unsafe)" · **EN —** Your email must be in **Test users** (1.3, step 10); then "Advanced → Go to … (unsafe)" |
| **VI —** Tiếng Việt/emoji bị lỗi font trên Windows · **EN —** Vietnamese/emoji garbled on Windows | **VI —** Chạy `chcp 65001` hoặc đặt `PYTHONUTF8=1` · **EN —** Run `chcp 65001` or set `PYTHONUTF8=1` |

---

## 8. Tệp liên quan · Related files

| Đường dẫn · Path | Vai trò · Role |
|---|---|
| `credentials.json` *(gốc repo · repo root)* | **VI —** OAuth client "Desktop app" bạn tải về · **EN —** The "Desktop app" OAuth client you downloaded |
| `output/gcal_token.json` | **VI —** Token Google sau `calendar-auth` (gồm refresh token) · **EN —** Google token after `calendar-auth` (incl. refresh token) |
| `output/lichhoc.ics` | **VI —** File lịch từ `fap ics` (cách thủ công) · **EN —** Calendar file from `fap ics` (the manual route) |
| `.env` | **VI —** Đặt `GCAL_CALENDAR_ID` (và `FAP_SEMESTER`) · **EN —** Where you set `GCAL_CALENDAR_ID` (and `FAP_SEMESTER`) |

> **VI —** Tất cả `output/`, `.env`, `credentials.json` đều đã `.gitignore` vì chứa bí mật/PII. **EN —** All of `output/`, `.env`, `credentials.json` are `.gitignore`d because they hold secrets/PII.
