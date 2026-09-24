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
| 3 | **VI —** Đăng nhập 1 lần: `fap calendar-auth` (DÁN URL redirect — chạy được cả trên máy chủ không màn hình) → `output/gcal_token.json` · **EN —** One-time login: `fap calendar-auth` (paste the redirect URL — works even on a headless server) → `output/gcal_token.json` |
| 4 | **VI —** Đẩy lịch: `fap calendar-sync` (chạy lại = cập nhật) · **EN —** Push: `fap calendar-sync` (re-run = update) |

> 💬 **VI —** Không muốn SSH vào máy chủ? Làm **tất cả bước 3–4 ngay trong chat** Telegram/Discord: `/calendar-auth`, `/calendar-sync`. Xem [§6](#6-cài--đồng-bộ-ngay-trong-chat--set-up--sync-from-chat). Muốn đẩy **1 lịch FAP sang nhiều tài khoản/lịch Google**? Xem [§7 multi-Google](#7-nhiều-tài-khoảnlịch-google--multi-google).
> 💬 **EN —** Don't want to SSH into the server? Do **all of steps 3–4 right in the Telegram/Discord chat**: `/calendar-auth`, `/calendar-sync`. See [§6](#6-cài--đồng-bộ-ngay-trong-chat--set-up--sync-from-chat). Want to push **one FAP schedule to several Google accounts/calendars**? See [§7 multi-Google](#7-nhiều-tài-khoảnlịch-google--multi-google).

---

## 0b. Giữ lịch KHỚP với FAP · Keep it matched

**VI —** `calendar-sync` **upsert** theo `iCalUID`: đổi **phòng/giờ** trên FAP → chạy lại là event **tự sửa** (không trùng). Nhưng buổi **bị hủy/dời** thì event cũ thành "mồ côi" → thêm `--prune` để dọn:
```bash
fap calendar-sync --prune          # đồng bộ + LIỆT KÊ event mồ côi (dry-run, CHƯA xóa)
fap calendar-sync --prune --yes    # + XÓA thật event mồ côi
fap calendar-prune                 # chỉ dọn (không đẩy lại); --yes để xóa; --force nếu >30%
```
> **An toàn:** prune **CHỈ xóa event do fap-cli tạo CHO CHÍNH MÃ SINH VIÊN NÀY** — mỗi event mang nhãn riêng `extendedProperties.private.fapc_owner=<mã SV>` (kèm `fapc=1` cho tương thích ngược), và bộ lọc chỉ nhận nhãn của chính mình. **Không bao giờ đụng event cá nhân, cũng không đụng lịch của người khác dùng chung calendar.** Dry-run mặc định; **từ chối nếu >30%** bị xóa (phòng lấy lịch lỗi), ép bằng `--force`.
**EN —** `calendar-sync` upserts by `iCalUID` (room/time edits auto-fix on re-run); add `--prune` to delete class events for sessions no longer on FAP. Prune only ever touches events fap-cli created **for this roll number** (tagged `fapc_owner=<roll>`) — never your personal events and never another person's, even on a shared calendar. Dry-run by default; refuses if >30% would be deleted.

> 👥 **VI —** Nhiều tài khoản trên 1 máy (`FAP_PROFILE`)? Mỗi profile có token Google **riêng** (`output/profiles/<tên>/gcal_token.json`) nên phải **tự chạy `fap calendar-auth` một lần**; `credentials.json` ở gốc repo dùng chung. Event **cũ chưa có nhãn `fapc_owner`** (tạo bởi bản fap-cli trước) chỉ thuộc về **profile mặc định** — profile có tên không bao giờ đụng vào. Chi tiết: [19-multi-profile §6.2](19-multi-profile.md#62--google-calendar-dùng-chung--sharing-one-google-calendar).
> 👥 **EN —** Running several accounts (`FAP_PROFILE`)? Each profile keeps its **own** Google token (`output/profiles/<name>/gcal_token.json`) and must run **`fap calendar-auth` once**; the root `credentials.json` is shared. **Untagged legacy events** belong to the **default profile only** — a named profile never touches them.

**VI — Tách hẳn khỏi lịch cá nhân (KHUYÊN):** tạo một Google Calendar riêng (vd "Lịch học FAP"), lấy **Calendar ID** của nó (Settings của calendar đó → *Integrate calendar* → *Calendar ID*) rồi đặt trong `.env`:
```dotenv
GCAL_CALENDAR_ID=abcdef...@group.calendar.google.com
```
→ Lịch học vào calendar riêng, muốn ẩn/tắt cả cụm rất dễ, và prune chỉ quét trong đó. Mặc định `GCAL_CALENDAR_ID=primary` (lịch chính).

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

## 3. Đăng nhập Google 1 lần (loopback-paste) · One-time Google login

```bash
fap calendar-auth
```

**VI —** Lệnh **in ra một URL** (không tự mở trình duyệt — nhờ vậy chạy được cả trên **máy chủ không màn hình**). Các bước:
1. Mở URL đó trên **bất kỳ máy nào có trình duyệt**, đăng nhập bằng **you@fpt.edu.vn** (đúng email đã thêm vào Test users) và đồng ý quyền **ghi sự kiện**. App ở chế độ Testing nên Google có thể cảnh báo "app chưa xác minh" — bấm **"Advanced" → "Go to … (unsafe)"** (an toàn vì là app của bạn).
2. Sau khi đồng ý, trình duyệt nhảy tới `http://127.0.0.1/?...&code=...` và báo **"không kết nối được 127.0.0.1"** — **ĐÚNG rồi**, không có server nào ở đó. **Copy nguyên URL trên thanh địa chỉ** rồi **dán lại vào lệnh** (chỗ `Dán URL redirect:`).

**EN —** The command **prints a URL** (it does NOT open a browser — so it works on a **headless server** too). Steps:
1. Open that URL on **any machine with a browser**, sign in as **you@fpt.edu.vn** (the email in Test users) and approve the **event-write** scope. In Testing mode Google may warn "app isn't verified" — click **"Advanced" → "Go to … (unsafe)"** (safe — it's your own app).
2. After approving, the browser lands on `http://127.0.0.1/?...&code=...` and says **"can't connect to 127.0.0.1"** — that is **EXPECTED** (nothing is listening there). **Copy the whole address-bar URL** and **paste it back into the command** (at the `Paste redirect URL:` prompt).

**VI —** Thành công sẽ in:
**EN —** On success it prints:

```text
✅ Đã xác thực Google cho đích 'mặc định'.
```

**VI —** Token lưu ở `output/gcal_token.json` (quyền `0600`). Lần sau hết hạn, tool **tự refresh không cần đăng nhập lại** (nhờ refresh token). Bạn chỉ chạy lại `calendar-auth` nếu xóa file token hoặc đổi quyền.
**EN —** The token is saved at `output/gcal_token.json` (mode `0600`). When it later expires, the tool **refreshes silently** (using the refresh token). You only re-run `calendar-auth` if you delete the token file or change scopes.

> 🖥️ **VI —** Trước đây lệnh này mở trình duyệt cục bộ (`run_local_server`) nên **vô dụng trên VPS**. Bản mới dùng **loopback-paste**: đăng nhập ở máy có màn hình, dán URL về máy chủ. Redirect vẫn là kiểu **"Desktop app"** (loopback `http://127.0.0.1`) — giữ nguyên OAuth client bạn tạo ở [Mục 1](#14-tạo-oauth-client-id-desktop-app--create-the-oauth-client-id).
> 🖥️ **EN —** This command used to open a local browser (`run_local_server`), which was **useless on a VPS**. It now uses **loopback-paste**: sign in on any machine with a screen, paste the URL back to the server. The redirect is still the **"Desktop app"** loopback (`http://127.0.0.1`) — the same OAuth client from [Section 1](#14-tạo-oauth-client-id-desktop-app--create-the-oauth-client-id).

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

**VI —** Mỗi buổi học thành 1 sự kiện với tiêu đề `<MãMôn> @ <Phòng>` (hoặc `(Online)`), kèm mô tả (lớp, slot, giảng viên, buổi). Buổi **online** có thêm **link Google Meet** ở cuối mô tả (Google Calendar tự biến thành link bấm được) — cách lấy link xem [13-notify §5](13-notify.md#5-nội-dung-tin-nhắn--what-the-digest-looks-like). Múi giờ luôn là **`Asia/Ho_Chi_Minh`** (cố định trong code, không phải biến `.env`).
**EN —** Each session becomes one event titled `<SubjectCode> @ <Room>` (or `(Online)`), with a description (group, slot, lecturer, session no.). **Online** sessions also get the **Google Meet link** at the end of the description (Google Calendar makes it clickable) — see [13-notify §5](13-notify.md#5-nội-dung-tin-nhắn--what-the-digest-looks-like) for where it comes from. The timezone is always **`Asia/Ho_Chi_Minh`** (hard-coded, not an `.env` key).

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

## 6. Cài & đồng bộ ngay trong chat · Set up & sync from chat

**VI —** Khi bot Telegram/Discord đang chạy, bạn làm **toàn bộ** việc Google Calendar **ngay trong chat** — không cần SSH vào máy chủ:
**EN —** With the Telegram/Discord bot running, you do **all** the Google-Calendar work **right in the chat** — no SSH into the server:

| Lệnh · Command | Việc · What it does |
|---|---|
| `/calendar-auth [nhãn·label]` | **VI —** Đăng nhập Google (loopback-paste): bot gửi 1 link, bạn đăng nhập rồi **dán URL redirect** vào chat; bot **XOÁ tin đó ngay** (URL có mã dùng-một-lần). Trên Discord: `/calendar-auth-finish <URL>` (trả lời **ẩn**). · **EN —** Google sign-in: the bot sends a link; you sign in and **paste the redirect URL**; the bot **deletes that message instantly**. On Discord: `/calendar-auth-finish <URL>` (ephemeral). |
| `/calendar-sync [nhãn] [prune] [yes]` | **VI —** Đẩy lịch học lên Google (chạy **nền**, không treo bot). `prune` = dọn, `yes` = xoá thật. · **EN —** Push the schedule (runs in the **background**). `prune` = clean up, `yes` = actually delete. |
| `/calendar-prune [nhãn] [yes]` | **VI —** Chỉ dọn buổi đã hủy/dời (mặc định **dry-run**; `yes` mới xoá). · **EN —** Prune cancelled/moved events (dry-run by default; `yes` deletes). |
| `/calendar-list` | **VI —** Xem các đích + trạng thái xác thực. · **EN —** List destinations + auth status. |
| `/calendar-add <nhãn> <calendar_id>` | **VI —** Thêm đích có nhãn (xem §7). · **EN —** Register a labelled destination (see §7). |
| `/calendar-remove <nhãn>` | **VI —** Bỏ một đích. · **EN —** Remove a destination. |

> 🔒 **VI —** **Token Google không bao giờ hiện trong chat** — bot chỉ trả câu xác nhận. URL redirect (mã dùng-một-lần) được **xoá ngay khi nhận** trên Telegram; các lệnh auth trên Discord trả lời **ẩn (ephemeral)**. Bot chỉ trả lời **chủ bot** (`TELEGRAM_CHAT` / `DISCORD_ALLOWED_USER_ID`) — xem [13-notify](13-notify.md).
> 🔒 **EN —** **The Google token never appears in chat** — the bot returns only a confirmation. The redirect URL (single-use code) is **deleted on arrival** on Telegram; Discord auth commands reply **ephemerally**. The bot answers **only its owner** (`TELEGRAM_CHAT` / `DISCORD_ALLOWED_USER_ID`).

---

## 7. Nhiều tài khoản/lịch Google (multi-Google) · Multiple Google accounts/calendars

**VI —** Một tài khoản FAP có thể đẩy sang **nhiều lịch / nhiều tài khoản Google** cùng lúc. Mỗi đích có một **NHÃN** (label). Nhãn **rỗng** = đích mặc định như cũ (không đổi gì); nhãn **có tên** = một đích riêng.
**EN —** One FAP account can push to **several Google calendars / accounts** at once. Each destination has a **label**. The **empty** label is the original default (unchanged); a **named** label is a separate destination.

| | Nhãn rỗng · empty (default) | Nhãn có tên · named, e.g. `work` |
|---|---|---|
| Token | `output/gcal_token.json` | `output/gcal/work.json` |
| `calendar_id` | `GCAL_CALENDAR_ID` (`.env`) | `output/gcal/destinations.json` |

**VI —** Thêm đích thứ hai (ví dụ lịch của một tài khoản Google khác):
**EN —** Add a second destination (e.g. another Google account's calendar):

```bash
fap calendar-add work you2@gmail.com   # calendar_id = email (lịch primary) HOẶC …@group.calendar.google.com
fap calendar-auth work                 # đăng nhập tài khoản Google thứ hai (loopback-paste)
fap calendar-sync work                 # đẩy lịch học sang đích 'work'
fap calendar-list                      # xem tất cả đích + trạng thái
```

> ⚠️ **CHỐT AN TOÀN · SAFETY —**
> **VI —** Hai đích **KHÔNG được trỏ vào cùng một `calendar_id` cụ thể**. Mọi sự kiện fap-cli mang dấu `fapc_owner=<mã SV>` **giống nhau** cho mọi nhãn của cùng một tài khoản FAP → nếu hai nhãn chung một lịch, prune nhãn này sẽ **xoá sự kiện nhãn kia** (và sinh `iCalUID` trùng). Vì thế nhãn có tên **phải khai một `calendar_id` cụ thể** (email hoặc `…@group.calendar.google.com`), **không nhận `primary`**, và tool **từ chối** khi phát hiện trùng (không phân biệt hoa-thường). `primary` ở **hai tài khoản khác nhau** vẫn hợp lệ (mỗi tài khoản có `primary` riêng). Prune trên một lịch **cụ thể** chỉ xoá sự kiện **đã gắn dấu của chính mã SV này** — không đụng sự kiện cũ chưa gắn dấu (có thể của người khác trên lịch dùng chung).
> **EN —** Two destinations **must not point at the same concrete `calendar_id`**. Every fap-cli event carries the **same** `fapc_owner=<roll>` across a student's labels → two labels on one calendar would make each label's prune **delete the other's events** (and mint duplicate `iCalUID`s). So a named label **must give a concrete `calendar_id`** (an email or `…@group.calendar.google.com`), **not `primary`**, and the tool **refuses** duplicates (case-insensitively). The same `primary` across **two different accounts** is fine. Prune on a **concrete** calendar only deletes events **tagged for this roll** — it never touches untagged legacy events (possibly someone else's on a shared calendar).

---

## 8. Khác gì so với `fap ics`? · How is this different from `fap ics`?

| | `fap calendar-sync` | `fap ics` |
|---|---|---|
| Cách hoạt động · How | **VI —** Đẩy thẳng qua Calendar API · **EN —** Pushes via the Calendar API | **VI —** Xuất file `output/lichhoc.ics` · **EN —** Exports `output/lichhoc.ics` |
| Cập nhật · Updates | **VI —** Tự upsert theo `iCalUID`, chạy lại = cập nhật · **EN —** Auto-upsert by `iCalUID`, re-run = update | **VI —** Import thủ công lại mỗi lần · **EN —** Manual re-import each time |
| Cài đặt · Setup | **VI —** Cần `credentials.json` + `[gcal]` + đăng nhập · **EN —** Needs `credentials.json` + `[gcal]` + login | **VI —** Không cần OAuth Google · **EN —** No Google OAuth |
| Đưa vào lịch · Into calendar | **VI —** Tự động · **EN —** Automatic | **VI —** Google Calendar → **Settings → Import** → chọn file `.ics` · **EN —** Google Calendar → **Settings → Import** → pick the `.ics` file |

**VI —** Tóm lại: dùng `calendar-sync` nếu muốn đồng bộ tự động lặp lại; dùng `ics` nếu chỉ cần 1 file để import nhanh hoặc import vào app lịch khác (Outlook, Apple Calendar…).
**EN —** In short: use `calendar-sync` for repeatable auto-sync; use `ics` if you just want a one-file quick import or to load into another calendar app (Outlook, Apple Calendar, …).

---

## 9. Khắc phục sự cố · Troubleshooting

| Triệu chứng · Symptom | Cách xử lý · Fix |
|---|---|
| `Thiếu credentials.json` · `Missing credentials.json` | **VI —** Làm lại Mục 1: tải OAuth "Desktop app" JSON, lưu thành `credentials.json` ở gốc repo · **EN —** Redo Section 1: download the "Desktop app" OAuth JSON, save as `credentials.json` at the repo root |
| `Thiếu thư viện Google` · `Missing Google libs` | **VI —** Chạy `pip install -e ".[gcal]"` · **EN —** Run `pip install -e ".[gcal]"` |
| `Chưa xác thực Google` · `Not authorized` | **VI —** Chạy `fap calendar-auth` trước · **EN —** Run `fap calendar-auth` first |
| **VI —** Google chặn "app chưa xác minh" · **EN —** Google blocks "app not verified" | **VI —** Email bạn phải nằm trong **Test users** (Mục 1.3, bước 10); rồi "Advanced → Go to … (unsafe)" · **EN —** Your email must be in **Test users** (1.3, step 10); then "Advanced → Go to … (unsafe)" |
| **VI —** `calendar-auth` không tự mở trình duyệt · **EN —** `calendar-auth` doesn't open a browser | **VI —** Đúng thiết kế (loopback-paste, chạy headless): copy URL nó in ra, mở ở máy có trình duyệt, rồi **dán URL redirect** lại (Mục 3). · **EN —** By design (loopback-paste, headless): copy the printed URL, open it on any browser, then **paste the redirect URL** back (Section 3). |
| **VI —** `Đích 'x' chưa đăng ký calendar_id` · **EN —** `Destination 'x' has no calendar_id` | **VI —** Chạy `fap calendar-add x <calendar_id>` trước khi `calendar-auth x`/`calendar-sync x` (§7). · **EN —** Run `fap calendar-add x <calendar_id>` before `calendar-auth x`/`calendar-sync x` (§7). |
| **VI —** `⛔ Đích … dùng CHUNG lịch …` · **EN —** `⛔ Destination … shares calendar …` | **VI —** Hai nhãn trỏ cùng một `calendar_id` cụ thể — đổi cho khác nhau (§7 chốt an toàn). · **EN —** Two labels share one concrete `calendar_id` — make them distinct (§7 safety). |
| **VI —** Tiếng Việt/emoji bị lỗi font trên Windows · **EN —** Vietnamese/emoji garbled on Windows | **VI —** Chạy `chcp 65001` hoặc đặt `PYTHONUTF8=1` · **EN —** Run `chcp 65001` or set `PYTHONUTF8=1` |

---

## 10. Tệp liên quan · Related files

| Đường dẫn · Path | Vai trò · Role |
|---|---|
| `credentials.json` *(gốc repo · repo root)* | **VI —** OAuth client "Desktop app" bạn tải về · **EN —** The "Desktop app" OAuth client you downloaded |
| `output/gcal_token.json` | **VI —** Token Google của đích MẶC ĐỊNH sau `calendar-auth` (gồm refresh token, quyền `0600`) · **EN —** Default-destination Google token after `calendar-auth` (incl. refresh token, mode `0600`) |
| `output/gcal/<nhãn>.json` | **VI —** Token của đích CÓ NHÃN (multi-Google, §7) · **EN —** Token for a labelled destination (multi-Google, §7) |
| `output/gcal/destinations.json` | **VI —** Sổ đăng ký đích: `{nhãn: {calendar_id}}` · **EN —** Destination registry: `{label: {calendar_id}}` |
| `output/lichhoc.ics` | **VI —** File lịch từ `fap ics` (cách thủ công) · **EN —** Calendar file from `fap ics` (the manual route) |
| `.env` | **VI —** Đặt `GCAL_CALENDAR_ID` (và `FAP_SEMESTER`) · **EN —** Where you set `GCAL_CALENDAR_ID` (and `FAP_SEMESTER`) |

> **VI —** Tất cả `output/`, `.env`, `credentials.json` đều đã `.gitignore` vì chứa bí mật/PII. **EN —** All of `output/`, `.env`, `credentials.json` are `.gitignore`d because they hold secrets/PII.
