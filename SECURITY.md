# Bảo mật & Sử dụng có trách nhiệm · Security & Responsible Use

**VI —** Công cụ này đăng nhập FAP **bằng chính tài khoản của bạn** và lưu token + dữ liệu cá nhân lên máy bạn.
Hãy đọc kỹ trước khi chạy, chia sẻ, hoặc public mã nguồn.
**EN —** This tool logs into FAP **with your own account** and stores tokens + personal data on your machine.
Read this before running, sharing, or publishing the source.

---

## 1. Nó lưu gì nhạy cảm? · What sensitive data it stores

| Đường dẫn · Path | Nội dung · Contents |
|---|---|
| `output/token.json` | Token FAP (`authenkey`), `campus`, `rollnumber`, email, họ tên · FAP token + identity |
| `output/oauth_tokens.json` | `access_token` + **`refresh_token`** FE Identity (đăng nhập headless lâu dài) · long-lived refresh token |
| `output/.pkce_state.json` | Verifier PKCE tạm thời · transient PKCE verifier |
| `output/gcal_token.json` | Token OAuth Google Calendar · Google Calendar OAuth token |
| `credentials.json` | OAuth client "Desktop app" của Google (bạn tải về) · your Google OAuth client |
| `output/api/*.json` | Dữ liệu cá nhân: điểm, điểm danh, học phí, CCCD, thông tin phụ huynh... · grades, attendance, fees, national ID, parent info |
| `.env` | Token Telegram, webhook Discord, cấu hình · bot token, webhook, config |

> **VI —** Bất kỳ ai có `output/oauth_tokens.json` hoặc `output/token.json` đều có thể truy cập dữ liệu FAP của bạn.
> **EN —** Anyone holding those token files can access your FAP data. Treat them like passwords.

## 2. Lá chắn sẵn có · Built-in guardrails

**VI —** `.gitignore` đã loại trừ: `output/`, `device-data/`, `.env`, `credentials.json`, và các file token.
**EN —** `.gitignore` already excludes `output/`, `device-data/`, `.env`, `credentials.json`, and token files.

- Các file token (`output/token.json`, `output/oauth_tokens.json`, `output/gcal_token.json`, dump lỗi) được tạo với quyền `0600` trên POSIX (Linux/macOS); trên Windows quyền này không áp dụng · token files are created `0600` on POSIX; on Windows this is a no-op (rely on `.gitignore` + user-profile isolation).
- `fap whoami` chỉ in token đã rút gọn (`authenkey` cắt còn 12 ký tự) · prints a truncated token only.
- Công cụ **chỉ gọi endpoint READ-ONLY**, bỏ qua các endpoint GHI (AddRate, UpdateToken...) · read-only by design.

## 3. Trước khi public repo · Before publishing the repo

1. **VI —** Chạy `git status` — KHÔNG được thấy `output/`, `device-data/`, `.env`, `credentials.json`.
   **EN —** Run `git status` — none of those paths may appear.
2. **VI —** Đừng bao giờ `git add -f` các đường dẫn trên. **EN —** Never force-add them.
3. **VI —** Nếu lỡ commit token: xoá khỏi **toàn bộ lịch sử git** (vd `git filter-repo`) **và** thu hồi token ngay (mục 4).
   **EN —** If a token was ever committed: purge it from the **entire git history** (e.g. `git filter-repo`) **and** revoke it (§4).
4. **VI —** Ghi rõ đây là **dự án không chính thức**. **EN —** State clearly it is **unofficial**.

> ⚠️ `SECRET` và `client_id` trong mã được trích từ **APK công khai** (ai giải nén cũng thấy). Chúng KHÔNG phải
> bí mật của riêng bạn, nhưng việc public chúng kèm hướng dẫn là phần bạn nên cân nhắc và ghi chú minh bạch. ·
> The embedded `SECRET`/`client_id` come from the public APK; publishing them is your call — be transparent.

## 4. Khi token bị lộ · If a token leaks

- **VI —** Đăng xuất khỏi FAP / FE Identity (đổi mật khẩu Google @fpt.edu.vn nếu nghi ngờ) để vô hiệu access/refresh token.
  **EN —** Sign out of FAP / FE Identity (change your Google @fpt.edu.vn password if in doubt) to invalidate tokens.
- **VI —** Xoá `output/oauth_tokens.json`, `output/token.json`, rồi `fap login` lại để lấy token mới.
  **EN —** Delete those files, then `fap login` again for fresh tokens.
- **VI —** Thu hồi quyền Google Calendar tại <https://myaccount.google.com/permissions> và xoá `output/gcal_token.json`.
  **EN —** Revoke the Google Calendar grant at the same URL and delete `output/gcal_token.json`.

## 5. Quy tắc sử dụng · Usage rules

- **VI —** Chỉ dùng cho **tài khoản & dữ liệu của chính bạn**. Không quét MSSV người khác, không giả mạo, không né xác thực.
  **EN —** Your **own account & data only**. No scraping others' roll numbers, no impersonation, no auth bypass.
- **VI —** Gọi **nhẹ nhàng** (vài lần/ngày). FAP/FE Identity là hệ thống thật — gây tải bất thường có thể bị chặn hoặc vi phạm quy định trường.
  **EN —** Call **gently** (a few times/day). These are real systems — abuse can get you blocked or breach school policy.
- **VI —** Trường có thể đổi secret/endpoint bất kỳ lúc nào → công cụ có thể hỏng; đó là rủi ro bạn chấp nhận.
  **EN —** The school may change secrets/endpoints anytime → the tool may break; that risk is yours.

## 6. Báo lỗi bảo mật · Reporting

**VI —** Đây là dự án cá nhân/giáo dục. Nếu bạn phát hiện lỗ hổng trong **mã nguồn này** (vd rò rỉ token ra log,
ghi file sai quyền), hãy mở issue **không kèm dữ liệu thật** hoặc liên hệ chủ repo riêng tư.
Lỗ hổng thuộc **hệ thống FAP/FPT** → hãy báo cho nhà trường, đừng khai thác.

**EN —** This is a personal/educational project. For a vulnerability in **this code** (e.g. token leakage to logs,
unsafe file permissions), open an issue **without real data**, or contact the repo owner privately.
Vulnerabilities in **FAP/FPT systems** belong to the university — report to them, do not exploit.
