# Khắc phục sự cố · Troubleshooting

**VI —** Bảng tra nhanh theo *triệu chứng → nguyên nhân → cách sửa*. Lệnh luôn ở dạng `fap <command>`; nếu chưa cài (`pip install -e .`) thì dùng `python -m fapc <command>`.
**EN —** Quick lookup by *symptom → cause → fix*. Commands are always `fap <command>`; if not installed (`pip install -e .`), use `python -m fapc <command>`.

> **VI —** Đây là dự án **KHÔNG chính thức**, chỉ dùng cho **tài khoản của chính bạn**. Mọi đường dẫn dưới đây nằm dưới gốc repo.
> **EN —** Unofficial project, **your own account only**. All paths below are relative to the repo root.

---

## 1. Đăng nhập & OAuth · Login & OAuth

### "scheme ... not registered" sau khi đăng nhập · after login

| | |
|---|---|
| **Triệu chứng · Symptom** | vi · Sau khi login Google @fpt.edu.vn, trình duyệt báo *"scheme io.identityserver.demo not registered"* (hoặc trang trắng / báo lỗi mở app). · en · After Google @fpt.edu.vn login the browser shows *"scheme … not registered"* (or a blank / can't-open-app page). |
| **Nguyên nhân · Cause** | vi · **BÌNH THƯỜNG.** `redirect_uri` là `io.identityserver.demo:/oauthredirect` — một custom scheme của app mobile mà trình duyệt PC không mở được. · en · **NORMAL.** The `redirect_uri` is `io.identityserver.demo:/oauthredirect`, a mobile app custom scheme the desktop browser can't open. |
| **Cách sửa · Fix** | vi · COPY nguyên URL trên thanh địa chỉ (bắt đầu `io.identityserver.demo:/oauthredirect?code=...`) rồi dán vào prompt, **hoặc** chạy `fap exchange "<url>"`. · en · Copy the full address-bar URL (starts `io.identityserver.demo:/oauthredirect?code=...`) and paste it at the prompt, **or** run `fap exchange "<url>"`. |

```bash
fap exchange "io.identityserver.demo:/oauthredirect?code=...&state=..."
```

### Đổi code lỗi · code exchange fails

| | |
|---|---|
| **Triệu chứng · Symptom** | vi · `Đổi code lỗi <http>: ...` khi `fap exchange`. · en · `Đổi code lỗi <http>: ...` (code exchange failed) when running `fap exchange`. |
| **Nguyên nhân · Cause** | vi · `code` trong URL **chỉ sống ~vài chục giây và dùng được 1 lần**. Dán muộn, dán lại lần 2, hoặc đã `exchange` rồi đều hỏng. · en · The `code` in the URL lives **only ~tens of seconds and is one-time use**. Pasting late, reusing it, or re-exchanging all fail. |
| **Cách sửa · Fix** | vi · Chạy lại `fap login` để lấy URL mới, rồi `exchange` **ngay**. · en · Re-run `fap login` to get a fresh URL, then `exchange` it **immediately**. |

### "Chưa có phiên đăng nhập" · no login session

| | |
|---|---|
| **Triệu chứng · Symptom** | vi · `Chưa có phiên đăng nhập. Chạy 'login' trước.` khi gọi `fap exchange`. · en · `Chưa có phiên đăng nhập` (no login session) when running `fap exchange`. |
| **Nguyên nhân · Cause** | vi · Thiếu file PKCE tạm `output/.pkce_state.json` (chứa `code_verifier`) — bạn `exchange` mà chưa `login`. · en · Missing transient PKCE file `output/.pkce_state.json` (holds the `code_verifier`) — you ran `exchange` without `login`. |
| **Cách sửa · Fix** | vi · Chạy `fap login` trước (nó tạo `.pkce_state.json`), rồi mới `exchange`. · en · Run `fap login` first (it creates `.pkce_state.json`), then `exchange`. |

### "Refresh lỗi ... refresh_token hết hạn" · refresh expired

| | |
|---|---|
| **Triệu chứng · Symptom** | vi · `Refresh lỗi <http>: ... — refresh_token hết hạn? Chạy 'login' lại.` khi `fap refresh`. · en · `Refresh lỗi ... refresh_token hết hạn?` when running `fap refresh`. |
| **Nguyên nhân · Cause** | vi · `refresh_token` trong `output/oauth_tokens.json` đã hết hạn / bị thu hồi. `refresh` chỉ chạy headless **đến khi** refresh_token còn sống. · en · The `refresh_token` in `output/oauth_tokens.json` has expired / been revoked. Headless `refresh` only works **while** the refresh_token is alive. |
| **Cách sửa · Fix** | vi · Đăng nhập lại bằng trình duyệt: `fap login`. · en · Log in again via browser: `fap login`. |

### "Không có refresh_token" · no refresh_token

| | |
|---|---|
| **Triệu chứng · Symptom** | vi · `Không có refresh_token — phải 'login' lại.` · en · `Không có refresh_token` (no refresh_token) on `fap refresh`. |
| **Nguyên nhân · Cause** | vi · `oauth_tokens.json` không có trường `refresh_token` (scope thiếu `offline_access`, hoặc file lưu lỗi). · en · `oauth_tokens.json` lacks a `refresh_token` field (missing `offline_access` scope, or a bad save). |
| **Cách sửa · Fix** | vi · Chạy `fap login` lại (scope mặc định `openid email profile offline_access` đã có `offline_access`). · en · Re-run `fap login` (the default scope already includes `offline_access`). |

### "Server FAP không trả 200" khi đổi token FAP · FAP token exchange not 200

| | |
|---|---|
| **Triệu chứng · Symptom** | vi · `AuthenticationByFeId -> HTTP <http> ...` + `✗ Server FAP không trả 200 — access_token có thể hết hạn ... hoặc sai scope.` · en · `AuthenticationByFeId -> HTTP <http>` + `✗ Server FAP không trả 200` (FAP token exchange didn't return 200). |
| **Nguyên nhân · Cause** | vi · `access_token` hết hạn, **hoặc** scope/audience chưa phù hợp cho `AuthenticationByFeId`. · en · The `access_token` expired, **or** its scope/audience isn't accepted by `AuthenticationByFeId`. |
| **Cách sửa · Fix** | vi · Thử `fap refresh` (làm mới access_token rồi đổi lại token FAP). Nếu vẫn lỗi, đây là vấn đề scope — xem `docs/04-feid-oauth-tool.md` (thử thêm scope như `fsp-mobile-front-end` / `identity-service`). · en · Try `fap refresh`. If it still fails it's a scope issue — see `docs/04-feid-oauth-tool.md` (try extra scopes like `fsp-mobile-front-end` / `identity-service`). |

### "Không bóc được token FAP" · couldn't extract FAP token

| | |
|---|---|
| **Triệu chứng · Symptom** | vi · HTTP 200 nhưng `✗ Không bóc được token FAP` (raw được lưu `output/feid_login_raw.json`). · en · HTTP 200 but `✗ Không bóc được token FAP` (couldn't extract FAP token; raw saved to `output/feid_login_raw.json`). |
| **Nguyên nhân · Cause** | vi · Server đổi cấu trúc trả về. Code **đã xử lý** trường hợp `data` là **list** (lấy phần tử đầu) và dò các khóa `authenKey`/`token`/`authenkey`/`accessToken`...; nếu vẫn không thấy nghĩa là khóa token đổi tên. · en · The response shape changed. The code **already handles** `data` being a **list** (takes element 0) and probes keys `authenKey`/`token`/`authenkey`/`accessToken`…; if none match, the token key was renamed. |
| **Cách sửa · Fix** | vi · Mở `output/feid_login_raw.json` xem trường nào chứa token (KHÔNG dán nội dung ra ngoài — chứa PII/token). Báo lỗi để cập nhật danh sách khóa trong `fapc/core/auth.py`. · en · Open `output/feid_login_raw.json` to see which field holds the token (do NOT share it — contains PII/token). Report it so the key list in `fapc/core/auth.py` can be updated. |

---

## 2. Token & gọi API dữ liệu · Token & data API calls

### "Chưa có token" · no token

| | |
|---|---|
| **Triệu chứng · Symptom** | vi · `Chưa có token. Đăng nhập trước: ...` khi chạy `fap extract` / `fap ics` / `fap grades` ... · en · `Chưa có token` (no token) on `fap extract` / `fap ics` / `fap grades` … |
| **Nguyên nhân · Cause** | vi · Chưa có `output/token.json` (trường `authenkey`) — bạn chưa đăng nhập lần nào. · en · No `output/token.json` (field `authenkey`) yet — you've never logged in. |
| **Cách sửa · Fix** | vi · `fap login` (lần đầu). Kiểm tra lại bằng `fap whoami`. · en · `fap login` (first time). Verify with `fap whoami`. |

### "Thiếu campus/rollNumber" · missing campus/roll

| | |
|---|---|
| **Triệu chứng · Symptom** | vi · `Thiếu campus/rollNumber trong token.json — đăng nhập lại`. · en · `Thiếu campus/rollNumber trong token.json` (missing campus/rollNumber). |
| **Nguyên nhân · Cause** | vi · `token.json` thiếu `campus` hoặc `rollnumber` (đăng nhập lỗi dở dang). · en · `token.json` is missing `campus` or `rollnumber` (a half-broken login). |
| **Cách sửa · Fix** | vi · `fap login` lại để ghi đủ trường. · en · Re-run `fap login` to repopulate the fields. |

### code=201 / 401 từ endpoint · code=201 / 401 from an endpoint

| | |
|---|---|
| **Triệu chứng · Symptom** | vi · API trả `{code: 201}` hoặc `{code: 401}`, không có dữ liệu. · en · API returns `{code: 201}` or `{code: 401}`, no data. |
| **Nguyên nhân · Cause** | vi · `Authen` token hết hạn **hoặc** `checksum` sai/quá hạn. Lưu ý `checksum` tính theo **giờ VN (UTC+7)** và chỉ ổn định trong **1 giờ**. · en · The `Authen` token expired **or** the `checksum` is wrong/stale. Note `checksum` is computed in **VN time (UTC+7)** and is only stable for **1 hour**. |
| **Cách sửa · Fix** | vi · Làm mới token: `fap refresh` (hoặc `fap login` nếu refresh hỏng). Kiểm tra đồng hồ máy đúng giờ. · en · Refresh the token: `fap refresh` (or `fap login` if refresh fails). Check your system clock is correct. |

### "Lỗi mạng" · network error

| | |
|---|---|
| **Triệu chứng · Symptom** | vi · `Lỗi mạng: ...` hoặc `Lỗi mạng tới FE Identity: ...`. · en · `Lỗi mạng` / `Lỗi mạng tới FE Identity` (network error). |
| **Nguyên nhân · Cause** | vi · Mất mạng, timeout (25s), proxy/DNS chặn `api.fpt.edu.vn` hoặc `feid.fpt.edu.vn`. · en · No connectivity, timeout (25s), or proxy/DNS blocking `api.fpt.edu.vn` / `feid.fpt.edu.vn`. |
| **Cách sửa · Fix** | vi · Kiểm tra mạng/VPN, thử lại. Không vòng lặp dồn dập (tôn trọng hạ tầng trường). · en · Check network/VPN and retry. Don't hammer it (respect school infra). |

### 404 trên GeFeeByRoll / GetSemesterMark / GetVersion · 404 on these endpoints

| | |
|---|---|
| **Triệu chứng · Symptom** | vi · `GeFeeByRoll`, `GetSemesterMark`, hoặc `GetVersion` trả HTTP 404. · en · `GeFeeByRoll`, `GetSemesterMark`, or `GetVersion` returns HTTP 404. |
| **Nguyên nhân · Cause** | vi · **Theo dữ liệu, KHÔNG phải lỗi tool.** Tài khoản **chưa có học kỳ nào hoàn tất** thì các endpoint này có thể không có dữ liệu/route. · en · **Data-driven, NOT a tool bug.** Accounts with **no completed semester** may simply have no data/route for these. |
| **Cách sửa · Fix** | vi · Bỏ qua — các endpoint khác vẫn chạy. Sẽ có dữ liệu khi bạn hoàn tất ít nhất một kỳ. · en · Ignore it — other endpoints still work. Data appears once you've finished at least one semester. |

### grades-detail trả code=201 · grades-detail returns code=201

| | |
|---|---|
| **Triệu chứng · Symptom** | vi · `fap grades-detail` trả `{code: 201}`, không có điểm chi tiết theo môn. · en · `fap grades-detail` returns `{code: 201}`, no per-course detail. |
| **Nguyên nhân · Cause** | vi · Checksum `cs12(rollNumber, campusCode)` cho `GetMarkByCourse` **đã kiểm chứng live = `code=200`** (đúng). Nếu **vẫn** ra `201` thì thường do **token/phiên**, không phải checksum. · en · The `cs12(rollNumber, campusCode)` checksum for `GetMarkByCourse` is **verified live = `code=200`**. A `201` now is usually a **token/session** issue, not the checksum. |
| **Cách sửa · Fix** | vi · Chạy `fap refresh` rồi thử lại. Lưu ý: môn **đang học chưa có điểm thành phần** thì data rỗng nhưng vẫn `code=200` — đó là bình thường. · en · Run `fap refresh` and retry. Note: an **in-progress course with no component marks yet** returns empty data but still `code=200` — that's normal. |

### banrisk cảnh báo "lệch" so với FAP · banrisk disagrees with FAP

| | |
|---|---|
| **Triệu chứng · Symptom** | vi · `fap banrisk` gắn cờ môn mà FAP chính thức **không** cấm thi (hoặc ngược lại). · en · `fap banrisk` flags a subject that official FAP does **not** ban (or vice-versa). |
| **Nguyên nhân · Cause** | vi · **Đây là ước lượng.** `banrisk` chỉ gắn cờ môn có **% điểm danh hiện tại < 80%** — dùng làm *proxy* cho luật cấm thi thật của FPT (tính trên **tổng số buổi dự kiến** của cả kỳ). · en · **It's an approximation.** `banrisk` flags subjects whose **current attendance% < 80%** as a *proxy* for FPT's real exam-ban rule (which is based on **total scheduled sessions** for the term). |
| **Cách sửa · Fix** | vi · Coi như tham khảo, không phải phán quyết. Đối chiếu số liệu chính thức trên FAP/app. · en · Treat it as a heads-up, not a verdict. Cross-check the official numbers on FAP/app. |

---

## 3. Google Calendar (extra `gcal`)

### "Thiếu thư viện Google" · missing Google libs

| | |
|---|---|
| **Triệu chứng · Symptom** | vi · `Thiếu thư viện Google. Cài: pip install ...` khi `fap calendar-auth` / `fap calendar-sync`. · en · `Missing Google libs` when running `fap calendar-auth` / `fap calendar-sync`. |
| **Nguyên nhân · Cause** | vi · Chưa cài nhóm phụ thuộc Google Calendar. · en · The Google Calendar dependencies aren't installed. |
| **Cách sửa · Fix** | vi · `pip install -e ".[gcal]"` (hoặc `pip install -r requirements-gcal.txt`). · en · `pip install -e ".[gcal]"` (or `pip install -r requirements-gcal.txt`). |

```bash
pip install -e ".[gcal]"
```

### "Thiếu credentials.json" · missing credentials.json

| | |
|---|---|
| **Triệu chứng · Symptom** | vi · `Thiếu <gốc repo>/credentials.json. Tạo OAuth client 'Desktop app' ...` · en · `Missing credentials.json … create a 'Desktop app' OAuth client`. |
| **Nguyên nhân · Cause** | vi · Chưa có file `credentials.json` (OAuth desktop-client JSON từ Google Cloud) ở **gốc repo**. · en · No `credentials.json` (OAuth desktop-client JSON from Google Cloud) at the **repo root**. |
| **Cách sửa · Fix** | vi · Google Cloud Console → bật **Calendar API** → tạo OAuth client loại **Desktop app** → tải JSON về lưu thành `credentials.json` ở gốc repo → `fap calendar-auth`. Xem `docs` về calendar để biết chi tiết. · en · Google Cloud Console → enable **Calendar API** → create a **Desktop app** OAuth client → download JSON to `credentials.json` at repo root → `fap calendar-auth`. |

### "Chưa xác thực Google" · Google not authorized

| | |
|---|---|
| **Triệu chứng · Symptom** | vi · `Chưa xác thực Google. Chạy: ...` khi `fap calendar-sync`. · en · `Not authorized` when running `fap calendar-sync`. |
| **Nguyên nhân · Cause** | vi · Chưa có `output/gcal_token.json` (token Google Calendar). · en · No `output/gcal_token.json` (Google Calendar token) yet. |
| **Cách sửa · Fix** | vi · Chạy `fap calendar-auth` (mở trình duyệt, đăng nhập Google 1 lần). · en · Run `fap calendar-auth` (browser, one-time Google login). |

> **VI —** `calendar-sync` dùng `import_` theo `iCalUID` nên chạy lại = **cập nhật**, không tạo trùng. Múi giờ cố định `Asia/Ho_Chi_Minh`.
> **EN —** `calendar-sync` upserts by `iCalUID`, so re-running **updates** rather than duplicating. Timezone is fixed to `Asia/Ho_Chi_Minh`.

---

## 4. Console Windows · Windows console

### Tiếng Việt / emoji bị lỗi font · garbled Vietnamese / emoji

| | |
|---|---|
| **Triệu chứng · Symptom** | vi · Tiếng Việt có dấu hoặc emoji hiện thành ký tự rác (`â`, `?`, ô vuông) trên Command Prompt / PowerShell. · en · Accented Vietnamese or emoji shows as garbage (`â`, `?`, boxes) in Command Prompt / PowerShell. |
| **Nguyên nhân · Cause** | vi · Console Windows mặc định không phải UTF-8 (cp1252/cp437). Package có gọi `sys.stdout.reconfigure("utf-8")` nhưng vài console vẫn cần ép thêm. · en · The Windows console defaults to non-UTF-8 (cp1252/cp437). The package calls `sys.stdout.reconfigure("utf-8")` but some consoles still need a nudge. |
| **Cách sửa · Fix** | vi · Chạy `chcp 65001` trước, **hoặc** đặt biến môi trường `PYTHONUTF8=1`. · en · Run `chcp 65001` first, **or** set `PYTHONUTF8=1`. |

```bash
chcp 65001
# hoặc · or (PowerShell)
$env:PYTHONUTF8 = "1"
```

---

## 5. Chạy 2 máy & nhiều tài khoản · Two machines & multi-profile

> **VI —** Nền tảng: [14-deploy §9](14-deploy.md#9-một-session-hai-máy--one-session-two-machines) (1 session, 2 máy) và [19-multi-profile](19-multi-profile.md) (nhiều tài khoản).
> **EN —** Background: [14-deploy §9](14-deploy.md#9-một-session-hai-máy--one-session-two-machines) (one session, two machines) and [19-multi-profile](19-multi-profile.md).

### Bot ngừng trả lời / 409 Conflict · bot stops answering / 409

| | |
|---|---|
| **Triệu chứng · Symptom** | vi · Bot Telegram **không trả lời gì nữa**; log lặp lại lỗi `getUpdates` mỗi ~5 giây, không bao giờ thoát. · en · The Telegram bot **answers nothing**; the log repeats a `getUpdates` error every ~5s forever. |
| **Nguyên nhân · Cause** | vi · **Hai tiến trình `fap telegram-bot` cùng một token** (thường: VPS **và** PC, hoặc một unit chạy 2 lần). Telegram trả **409 Conflict**; body 409 vẫn là JSON hợp lệ nên vòng lặp chỉ thấy `ok=false` → in lỗi → ngủ 5s → lặp **vô hạn**. · en · **Two `fap telegram-bot` processes on the same token** (typically VPS **and** PC). Telegram returns **409 Conflict**; the 409 body is still valid JSON, so the poller only sees `ok=false`, sleeps 5s and **loops forever**. |
| **Cách sửa · Fix** | vi · **Tắt bot ở một máy.** Chỉ chạy bot ở **máy sở hữu token** (VPS): `systemctl --user stop fap-bot` trên máy kia, và **để trống** `TELEGRAM_*` trong `.env` của PC. Nhiều profile: mỗi profile phải có **token bot RIÊNG** — hai profile dùng chung 1 `TELEGRAM_TOKEN` cũng ra đúng lỗi 409 này. · en · **Stop the bot on one machine.** Run it only on the **token-owning box** (the VPS): `systemctl --user stop fap-bot` elsewhere, and leave `TELEGRAM_*` **empty** in the PC's `.env`. With profiles: each profile needs its **own bot token** — two profiles sharing one `TELEGRAM_TOKEN` produce the same 409. |

### Nhắc lịch 2 lần · class reminders fire twice

| | |
|---|---|
| **Triệu chứng · Symptom** | vi · Mỗi tiết học nhận **2 tin nhắc** giống hệt nhau (đôi khi cách nhau vài giây). · en · Every class produces **two identical reminders** (sometimes seconds apart). |
| **Nguyên nhân · Cause** | vi · **Hai bot/watcher đang chạy song song** (2 máy, hoặc 2 unit trên cùng máy). Tập "đã nhắc" nằm **trong RAM**, **không có file state** ⇒ hai tiến trình không thể biết nhau ⇒ trùng **100%**. · en · **Two resident processes running in parallel.** The "already reminded" set lives **in RAM** with **no state file**, so the two can't see each other — duplication is **guaranteed**. |
| **Cách sửa · Fix** | vi · Chỉ giữ **một** tiến trình có bật nhắc lịch. Kiểm tra: `systemctl --user list-units 'fap-*'` trên **cả hai** máy. Muốn tắt nhắc ở một nơi mà vẫn giữ bot: đặt `FAP_REMIND_MINUTES=0`. · en · Keep **one** reminder-capable process. Check `systemctl --user list-units 'fap-*'` on **both** machines. To keep a bot but silence its reminders, set `FAP_REMIND_MINUTES=0`. |

### Phải login lại liên tục · you keep having to re-login

| | |
|---|---|
| **Triệu chứng · Symptom** | vi · Vài giờ/vài ngày một lần lại `Refresh lỗi ... refresh_token hết hạn?` dù mới `fap login` xong. · en · `Refresh lỗi … refresh_token hết hạn?` again and again, hours or days after a fresh `fap login`. |
| **Nguyên nhân · Cause** | vi · **Hai nơi cùng refresh một session.** `refresh_token` **XOAY VÒNG**: mỗi lần refresh thành công sẽ **vô hiệu hóa** bản cũ ⇒ máy chạy sau cầm token đã chết. Thường gặp khi PC copy `output/` từ VPS rồi vẫn chạy `fap refresh` (hoặc `run-fap.ps1`/cron). · en · **Two places refreshing one session.** The `refresh_token` **rotates** — each successful refresh **invalidates** the previous one, so whichever machine runs second holds a dead token. Classic cause: the PC copied `output/` from the VPS and still runs `fap refresh` (or `run-fap.ps1`/cron). |
| **Cách sửa · Fix** | vi · Chọn **MỘT** máy sở hữu token (VPS). Trên máy kia: đặt `FAP_TOKEN_READONLY=1` trong `.env`, gỡ mọi task/cron gọi `fap refresh`. Rồi `fap login` lại **một lần** ở máy sở hữu, `scp output/token.json output/oauth_tokens.json` sang máy kia + `chmod 600`. · en · Pick **ONE** owning machine (the VPS). On the other: set `FAP_TOKEN_READONLY=1` and remove every task/cron that calls `fap refresh`. Then `fap login` **once** on the owner and `scp output/token.json output/oauth_tokens.json` over + `chmod 600`. |

### "Máy này là CLIENT CHỈ-ĐỌC — TỪ CHỐI refresh" · READ-ONLY client, refusing to refresh

| | |
|---|---|
| **Triệu chứng · Symptom** | vi · Banner đỏ 5 dòng ra `stderr` + `fap refresh` thoát ngay; watcher/bot dần chết vì token hết hạn. · en · A 5-line banner on `stderr` and `fap refresh` exits immediately; watchers/bots die off as the token expires. |
| **Nguyên nhân · Cause** | vi · `FAP_TOKEN_READONLY` đang bật trên máy này (`.env`, `.env.<profile>`, hoặc `Environment=` trong unit file). · en · `FAP_TOKEN_READONLY` is set here (`.env`, `.env.<profile>`, or an `Environment=` line in the unit file). |
| **Cách sửa · Fix** | vi · **Đây có phải máy sở hữu token không?** Nếu **có** (máy chạy bot/watcher): **bỏ** `FAP_TOKEN_READONLY` rồi khởi động lại service — nếu không, mọi watcher sẽ im lặng chết. Nếu **không** (máy phụ chỉ xem): đúng như thiết kế — copy `token.json` mới từ máy sở hữu thay vì refresh. · en · **Is this the owning machine?** If **yes** (it runs the bots/watchers): **remove** the flag and restart — otherwise everything silently dies. If **no** (secondary viewer): working as intended — copy a fresh `token.json` from the owner instead of refreshing. |

### Profile không nhận được thông báo nào · a profile gets no notifications

| | |
|---|---|
| **Triệu chứng · Symptom** | vi · Chạy với `FAP_PROFILE=alice`: watcher chạy bình thường, log không lỗi, nhưng alice **không nhận tin nào**. · en · With `FAP_PROFILE=alice` the watcher runs fine and logs no error, but alice **receives nothing**. |
| **Nguyên nhân · Cause** | vi · **Đúng thiết kế.** Các khóa danh tính/kênh gửi (`TELEGRAM_TOKEN`, `TELEGRAM_CHAT`, `DISCORD_*`, `GCAL_CALENDAR_ID`, `FAP_ALLOW_UPDATE`) **KHÔNG** được thừa kế từ `.env` gốc — nếu không, điểm của alice sẽ bắn vào chat của **chủ máy**. Thiếu khóa ⇒ kênh **tắt hẳn**, im lặng. · en · **By design.** Identity/delivery keys are **never** inherited from the root `.env` — otherwise alice's marks would land in the **owner's** chat. A missing key means that channel is simply **off**. |
| **Cách sửa · Fix** | vi · Điền `TELEGRAM_TOKEN` + `TELEGRAM_CHAT` (hoặc `DISCORD_*`) **của chính alice** vào `<gốc repo>/.env.alice`, rồi khởi động lại unit của alice. Kiểm tra: `FAP_PROFILE=alice fap notify test`. · en · Put **alice's own** `TELEGRAM_TOKEN` + `TELEGRAM_CHAT` (or `DISCORD_*`) in `<repo-root>/.env.alice` and restart her unit. Verify with `FAP_PROFILE=alice fap notify test`. |

### Profile vẫn đọc/ghi vào `output/` của chủ máy · a profile still uses the owner's `output/`

| | |
|---|---|
| **Triệu chứng · Symptom** | vi · Đặt `FAP_PROFILE` rồi mà `output/profiles/<tên>/` **không được tạo**, dữ liệu vẫn ra `output/`; có thể có cảnh báo `FAP_PROFILE=... không hợp lệ` ở `stderr`. · en · `FAP_PROFILE` is set but `output/profiles/<name>/` is **never created** and data still lands in `output/`; a `FAP_PROFILE=… is invalid` warning may appear on `stderr`. |
| **Nguyên nhân · Cause** | vi · Tên profile **sai định dạng** (chỉ cho phép chữ/số/`.` `_` `-`) ⇒ **bị bỏ qua**, chạy như **không có profile** (dùng `.env` + `output/` của chủ máy). Hoặc biến chưa tới được tiến trình (thiếu `Environment=FAP_PROFILE=` trong unit). · en · The name is **malformed** (letters/digits/`._-` only) so it is **ignored** and the process runs with **no profile** — the owner's `.env` and `output/`. Or the variable never reached the process (missing `Environment=FAP_PROFILE=` in the unit). |
| **Cách sửa · Fix** | vi · Đổi tên profile cho hợp lệ (vd `alice`), hoặc thêm `Environment=FAP_PROFILE=alice` vào unit. Kiểm tra: `FAP_PROFILE=alice fap whoami` phải ra mã SV của alice. · en · Use a valid name (e.g. `alice`) or add `Environment=FAP_PROFILE=alice` to the unit. Verify: `FAP_PROFILE=alice fap whoami` must show alice's roll number. |

### `/update` báo bị cấm · the bot refuses `/update`

| | |
|---|---|
| **Triệu chứng · Symptom** | vi · Chủ bot gõ `/update`, bot trả lời rằng lệnh đang bị TẮT (dù trước đây chạy được). · en · The bot owner sends `/update` and the bot replies that the command is disabled (it used to work). |
| **Nguyên nhân · Cause** | vi · `/update` giờ **TẮT mặc định**: nó `git pull` + khởi động lại trên **checkout dùng chung của mọi profile**, nên phải bật rõ ràng. · en · `/update` is now **off by default**: it pulls and restarts the **checkout every profile shares**, so it must be enabled explicitly. |
| **Cách sửa · Fix** | vi · Thêm `FAP_ALLOW_UPDATE=1` vào `.env` (hoặc `Environment=FAP_ALLOW_UPDATE=1` trong unit) của **chủ máy** rồi khởi động lại bot. Đừng bật cho profile khách. Thay thế: `bash deploy/update.sh` trên server. · en · Add `FAP_ALLOW_UPDATE=1` to the **owner's** `.env` (or `Environment=…` in the unit) and restart the bot. Don't enable it for guest profiles. Alternative: run `bash deploy/update.sh` on the server. |

---

## 6. Tự kiểm tra & xem trạng thái · Self-check & status

| Lệnh · Command | Dùng để · Use |
|---|---|
| `fap doctor` | vi · Tự kiểm tra cấu hình/môi trường. · en · Self-check config/environment. |
| `fap whoami` | vi · Xem token FAP đã lưu (authenkey bị che bớt). · en · Show saved FAP token (authenkey masked). |
| `fap` *(không tham số · no arg)* | vi · Hiện trợ giúp song ngữ. · en · Show bilingual help. |

> **VI —** Nếu cách sửa nào ở trên không khớp với những gì source thực sự làm, hãy coi đó là **chưa xác minh** và kiểm tra lại `fapc/core/api.py`, `fapc/core/auth.py`, `fapc/app/gcal.py` trước khi tin.
> **EN —** If any fix above doesn't match what the source actually does, treat it as **unverified** and re-check `fapc/core/api.py`, `fapc/core/auth.py`, `fapc/app/gcal.py` first.
