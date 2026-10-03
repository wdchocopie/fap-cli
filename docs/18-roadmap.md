# 18 · Nhật ký quyết định · Decision log *(đã triển khai · implemented)*

> ✅ **VI —** Cả 4 quyết định ở đây **ĐÃ ĐƯỢC CODE**. Giữ file này lại vì nó chứa **lý do** và [§5 sự thật đã kiểm chứng](#5-sự-thật-đã-kiểm-chứng--verified-facts) — đừng điều tra lại những gì đã đo ở đây.
> ✅ **EN —** All four decisions below are **IMPLEMENTED**. This file stays because it records the **why** and the [§5 verified facts](#5-sự-thật-đã-kiểm-chứng--verified-facts) — don't re-investigate what was already measured here.

**Chốt ngày:** 2026-08-02 · **Nền:** commit `3c42ca9` · **Trạng thái lúc chốt:** 169/169 test offline PASS

**Tài liệu người dùng sinh ra từ file này · user-facing docs that came out of this:** [14-deploy §9](14-deploy.md#9-một-session-hai-máy--one-session-two-machines) (1 session, 2 máy) · [19-multi-profile](19-multi-profile.md) (nhiều tài khoản) · [15-config](15-config.md) (`FAP_PROFILE`, `FAP_TOKEN_READONLY`, `FAP_ALLOW_UPDATE`) · [16-troubleshooting §5](16-troubleshooting.md#5-chạy-2-máy--nhiều-tài-khoản--two-machines--multi-profile) (409 / nhắc 2 lần / login lại liên tục) · [deploy/README.md](../deploy/README.md).

Mọi số liệu dưới đây là **đo thật** (render offline bằng chính code hiện tại), không phải ước lượng. Đã qua 1 vòng agent kiểm chứng chéo — các chỗ phân tích ban đầu nói sai đã được sửa và ghi chú ở [§5](#5-sự-thật-đã-kiểm-chứng--verified-facts).

---

## 0. Bốn quyết định đã chốt · The four decisions

| # | Việc | Quyết định | Trạng thái · Status |
|---|---|---|---|
| 1 | Hiển thị thông báo điểm mới | **Nhóm theo loại + gộp dòng LAB** (phương án B+A2) | ✅ `fapc/app/gradewatch.py` — `render_events` gom nhóm 🔬📝📎🏁 + gộp run ≥4, header `· N điểm mới` |
| 2 | 2 bug thật vừa phát hiện | **Sửa cả hai** | ✅ (a) chunk qua `fmt.chunks` ở `notify.py` + 2 bot (hết cắt cụt) · (b) tên tmp theo PID ở `auth._save` + lệch giờ refresh lúc khởi động ở cả 3 watcher |
| 3 | 1 session chạy 2 nơi | **Viết tài liệu + thêm cờ `FAP_TOKEN_READONLY`** | ✅ cờ ở `fapc/config.py` + `auth.refresh_tokens()` từ chối kèm banner; tài liệu [14-deploy §9](14-deploy.md#9-một-session-hai-máy--one-session-two-machines) + [deploy/README](../deploy/README.md) |
| 4 | Nhiều account | **Hướng "bạn bè tự login"** — mỗi người tự `fap login`, dữ liệu chỉ về kênh của chính họ | ✅ `fapc/core/paths.py` + 1 loader `.env` duy nhất + dấu chủ sở hữu trên Google Calendar; tài liệu [19-multi-profile](19-multi-profile.md), unit `deploy/fap-*@.service` + `deploy/setup-profile.sh` |

**Thứ tự làm:** §1 → §2 → §3 → §4. §1 không dính gì tới phần còn lại nên làm trước được ngay.

---

## 1. ✅ Gộp dòng LAB cho thông báo điểm mới · Compact grade alert

> ✅ **ĐÃ LÀM · DONE** — `fapc/app/gradewatch.py`: `render_events` nay gom nhóm cố định 🔬 → 📝 → 📎 → 🏁, gộp run ≥4 mục thành "chủ đạo + ngoại lệ" (chỉ khi số **thật sự liên tiếp**), header môn có `· N điểm mới`. Mẫu 47 event: **54 dòng/896 ký tự → 19 dòng/560 ký tự**; ca 3 điểm vẫn ngắn như cũ.

**Vì sao:** hiện tại 1 thông báo = **54 dòng / 896 ký tự**. KHÔNG bị cắt (Discord cắt ở 1900, Telegram 4000) — nên đây thuần là chuyện dễ đọc, **không phải bug**.

> 💡 Vụ "47 điểm một lúc" là **một lần duy nhất**: commit `64bd944` thêm parser HTML nên baseline cũ rỗng → lần poll đầu coi mọi thành phần là mới. Bình thường chỉ 1–3 điểm/lần. **Cách gộp mới không được làm ca ít điểm xấu đi.**

### Kết quả mong muốn (19 dòng)

```
🎯 Có điểm mới!
━━━━━━━━━━━━━━━━
📘 HOD402 · 16 điểm mới
   🔬 LAB 1–12: toàn 9  ·  LAB 6: 10 · LAB 12: 8
   📝 Progress test 1: 9.7 · Progress test 2: 10
   📎 Project: 8
   🏁 Final exam: 7.6

📘 IAP301 · 14 điểm mới
   🔬 Lab 1–10: toàn 8  ·  Lab 3: 7 · Lab 6: 5
   📝 Midterm Progress Test: 7.6
   📎 Group Assignment Presentation: 9 · Participation in Discussions: 10
   🏁 Final Exam: 8.4
```

Ca thường (2–3 điểm) giữ nguyên ngắn gọn như hiện tại:

```
📘 HOD402 · 3 điểm mới
   🔬 LAB 12: 8
   🏁 Final exam: 7.6
   ★ Điểm tổng kết: 8.5
```

### Cách làm

- Sửa **duy nhất** `fapc/app/gradewatch.py` — thay list-comp ở `render_events` (dòng ~92), thêm ~45 dòng helper THUẦN cạnh `_natkey` (~dòng 76).
- **Nhóm cố định:** `🔬 Lab` → `📝 Progress/Midterm` → `📎 Khác` → `🏁 Final`. Nhóm ít mục thì nối 1 dòng bằng `·`.
- **Gộp run:** các mục cùng tiền tố + đánh số liên tiếp → 1 dòng "chủ đạo + ngoại lệ" (`toàn 9 · LAB 6: 10 · LAB 12: 8`). Chỉ gộp khi run đủ dài (≥4), dưới ngưỡng thì in bình thường.
- ⚠️ **BẮT BUỘC thêm `· N điểm mới`** vào header môn. Không có nó, "LAB 1–12" bị hiểu nhầm là *toàn bộ lab của môn*, trong khi event chỉ chứa lab **vừa đổi** — cách gộp tự nó tạo ra một lời nói dối.
- Dùng heuristic theo TÊN, **không** cần đụng `category`. (FAP có trả `category` ở `grades.py:102` nhưng `gradewatch.py:26` `_NAME_KEYS` đang bỏ đi — plumb sau cũng được, không chặn việc này.)

### Rủi ro
Thấp. `render_events` chỉ được gọi 1 chỗ (`gradewatch.py:136`), không import ở đâu khác, không đọc config. Test `tests/test_logic.py:449` dùng fixture 2 LAB (dưới ngưỡng gộp) nên **pass nguyên không cần sửa**. Không đổi schema state → không phải baseline lại.

---

## 2. ✅ Hai bug thật · Two real bugs

> ✅ **ĐÃ LÀM · DONE** — (a) `notify.py`, `telegrambot.py`, `discordbot.py` **chunk** qua `fmt.chunks` (4000 / 1900) thay vì `[:N]`, nghỉ 0.4s giữa mẩu, chỉ báo thành công khi **mọi** mẩu gửi xong. (b) `auth._save` dùng tên tmp theo **PID** + dọn khi lỗi; cả 3 watcher **seed `last_refresh` lệch nhau** lúc khởi động (gradewatch / attendwatch / reminders ở 3 dải thời gian rời nhau) nên `update.sh` restart liên tiếp không còn tạo 3 lượt refresh cùng lúc.

### (a) 🔴 `/grades-detail` và `/all` đang bị cắt mất chữ — MẤT DỮ LIỆU

Đo thật: `detail_text` = **2691 ký tự / 62 dòng** với 3 môn, **5325 / 122 dòng** với 6 môn.

| Kênh | Giới hạn | 3 môn | 6 môn |
|---|---|---|---|
| Discord | `[:1900]` | **mất 791 ký tự** | **mất 3425** |
| Telegram | `[:4000]` | ok | **mất 1325** |

Cắt bằng `[:N]` cứng, **không có dấu `…`**, không chunk ở đâu cả → người dùng không biết mình đang mất chữ.

**6 chỗ phải sửa:** `notify.py:62`, `notify.py:78`, `telegrambot.py:38`, `discordbot.py:58/71/98/150/162`.

**Cách sửa:** **chunk** (chia nhiều tin), KHÔNG phải nâng số. Trần thật là Telegram 4096 / Discord 2000 — nâng lên vẫn cắt ở 6 môn. Hoặc làm `detail_text` chat-native (bỏ `fmt.table`) — xem ghi chú ở §5.

### (b) 🔴 3 tiến trình cùng refresh token một lúc

`reminders.py:64`, `gradewatch.py:153`, `attendwatch.py:174` đều khởi động với `last_refresh = 0.0` → **refresh ngay ở vòng lặp đầu**. `deploy/update.sh:66-70` restart cả 3 unit liên tiếp ⇒ sau **mỗi lần** `update.sh`, cả 3 gọi `refresh_tokens()` trong vài giây, cùng đọc 1 refresh_token (`auth.py:210`), cùng ghi qua **một tên tmp cố định** (`auth.py:45`).

Nếu FE Identity xoay vòng refresh_token **và** thu hồi cả grant khi bị dùng lại → **tự hỏng dù chỉ có 1 máy**, không cần máy thứ hai nào.

**Cách sửa (2 phần, cần cả hai):**
1. `auth.py:45` — tên tmp riêng theo tiến trình: `f"{path}.{os.getpid()}.tmp"` + dọn khi lỗi. (Đóng lỗ hổng ghi đè; giữ nguyên fallback `OSError` ở `auth.py:50-52` và mode 0600.)
2. **Làm lệch giờ refresh lúc khởi động** — seed `last_refresh` khác 0 / jitter ở `reminders.py:64`, `gradewatch.py:153`, `attendwatch.py:174`, để 3 tiến trình không refresh cùng lúc. *Chỉ sửa (1) là chưa đủ.*

---

## 3. ✅ Một session dùng cả PC lẫn VPS · Shared session

> ✅ **ĐÃ LÀM · DONE** — cờ `FAP_TOKEN_READONLY` có ở `fapc/config.py`; `auth.refresh_tokens()` kiểm tra **đầu tiên** rồi in banner 5 dòng song ngữ ra `stderr` (kèm nhãn profile) trước khi `SystemExit`. Tài liệu cho người dùng: **[14-deploy §9](14-deploy.md#9-một-session-hai-máy--one-session-two-machines)** (copy file nào / không copy file nào, doctrine 1-nơi-refresh, vì sao đừng chạy bot 2 nơi), tóm tắt ở **[deploy/README](../deploy/README.md)**, triệu chứng ở **[16-troubleshooting §5](16-troubleshooting.md#5-chạy-2-máy--nhiều-tài-khoản--two-machines--multi-profile)**.

### (i) Dùng chung 1 lần login → ✅ ĐƯỢC

Token FAP là **bearer-style** (`Authen` trên mọi call), **không device binding**: User-Agent cố định `okhttp/4.9.2` (`api.py:37`), checksum chỉ phụ thuộc đồng hồ (`api.py:76-88`, đã retry ±1h), login chỉ gửi `{"token": access_token}` (`auth.py:90`). Đây vốn đã là quy trình trong `deploy/README.md:37`.

```bash
scp output/token.json output/oauth_tokens.json user@vps:~/fap-cli/output/
```

Rồi `chmod 600` cả hai (scp **không** giữ mode; `auth._save` chmod 0600 nhưng chỉ khi chính nó ghi).

**KHÔNG copy:**
- `output/.pkce_state.json` — dùng một lần, bị tiêu thụ ở `auth.py:196-201`
- `output/grade_state.json`, `attendance_state.json`, `seen_notifications.json` — baseline riêng từng máy, copy sang sẽ báo trùng/báo sót

**Cái bẫy:** `refresh_token` **xoay vòng** (`refresh_tokens()`, `auth.py:210-219`). Máy nào refresh trước thì bản của máy kia thành vô hiệu.

**Doctrine:** **VPS là nơi refresh DUY NHẤT.** PC chỉ chạy lệnh đọc (`fap status/grades/week/whatif`, `fap web`, `fap whoami`) và **để trống** `TELEGRAM_*` / `DISCORD_*` trong `.env` của PC.

**Cần code:** thêm cờ `FAP_TOKEN_READONLY=1` cho máy PC — `refresh_tokens()` gặp cờ này thì từ chối refresh kèm thông báo rõ ràng, thay vì lỡ tay làm hỏng token của VPS. (Đặt cờ nhầm trên VPS thì watcher sẽ im lặng ngừng refresh → thông báo phải thật to.)

### (ii) Chạy song song bot/watcher ở cả 2 nơi → ❌ ĐỪNG

- **Telegram 409 Conflict:** `telegrambot.py:84-89` — body 409 vẫn là JSON hợp lệ nên `.json()` chạy được, `ok=False` → in lỗi, ngủ 5s, `continue` **vòng vô hạn**, không bao giờ phân biệt 409 với lỗi khác.
- **Nhắc lịch trùng 100%:** `ClassReminder.sent` là set **trong RAM** (`reminders.py:61`), không có file state → 2 instance nhắc y hệt nhau, chắc chắn trùng.
- Watcher trùng: 2 máy 2 baseline riêng → mỗi máy tự báo một lần.

---

## 4. ✅ Nhiều account · Multi-profile

> ✅ **ĐÃ LÀM · DONE** — `fapc/core/paths.py` (`profile()`/`out_dir()`/`out()`/`ensure_dir()`/`label()`) + ~11 hằng đường dẫn chuyển sang `paths.out(...)` **giữ nguyên tên hằng**; `.env` chỉ còn **một** loader (`fapc/__init__.py:load_env()`) hiểu profile và **chặn khóa danh tính**; Google Calendar gắn `fapc_owner=<mã SV>`; state/`api/*.json` chmod `0600`; unit template `deploy/fap-*@.service` + `deploy/setup-profile.sh`. Tài liệu: **[19-multi-profile](19-multi-profile.md)**.

**Hướng đã chốt:** mỗi người bạn **tự chạy `fap login` của họ**, dữ liệu chỉ chảy về kênh của **chính họ**. Không nhận hộ mật khẩu/token của người khác.

**Thiết kế:** `FAP_PROFILE=alice` → `output/profiles/alice/*.json`; mỗi profile 1 process/systemd unit. Không đặt biến ⇒ đường dẫn resolve **y hệt hiện tại** ⇒ VPS đang chạy không cần migrate, không phải login lại.

Thêm `fapc/core/paths.py` (~25 dòng): `profile()` / `out_dir()` / `out(*parts)`. Viết lại ~11 hằng đường dẫn để gọi `paths.out(...)` nhưng **GIỮ NGUYÊN TÊN hằng ở module level** — `tests/integration_offline.py:63` và `tests/test_logic.py:564` gán thẳng `aw.STATE` / `gw.STATE` / `notify._SEEN_NOTIF`; biến chúng thành hàm là **hỏng cả 2 bộ test**.

### ✅ Ba cửa ải — ĐÃ ĐÓNG cả ba · all three gates CLEARED

| | Đã xử lý thế nào · How it was closed |
|---|---|
| ✅ 1 | **Gộp làm MỘT loader.** `fapc/config.py` không còn tự đọc `.env`; nó gọi `fapc/__init__.py:load_env()` (idempotent). Có profile ⇒ nạp `.env.<tên>` **trước** (setdefault = thắng), rồi `.env` gốc **bỏ hẳn** 9 khóa danh tính (`TELEGRAM_*`, `DISCORD_*`, `GCAL_CALENDAR_ID`, `FAP_ALLOW_UPDATE`, `FAP_PROFILE`). Loader còn **ngó `FAP_PROFILE` trong `.env` gốc trước**, nếu không thì đường dẫn theo profile mà env lại của chủ máy = vẫn rò. |
| ✅ 2 | **Google Calendar: sửa UID + nhãn trong cùng PR** (không phải chặn gcal). Mỗi event mang `fapc_owner=<mã SV>` và `iCalUID` chứa mã SV; `_list_fapc_events` lọc theo nhãn của **chính mình** (lọc lại client-side vì Calendar API không có "khác giá trị này"); event **cũ chưa gắn nhãn** chỉ thuộc profile **mặc định**, và được "nhận nuôi" **cập nhật tại chỗ** (giữ uid cũ) nên không nhân đôi. Liệt kê lỗi ⇒ **DỪNG** thay vì đẩy (tránh nhân đôi cả kỳ). |
| ✅ 3 | **`output/api/` tách theo profile + chmod 0600.** `extract.OUT/APIOUT`, `subjects.CACHE`, `schedule.OUT`, `extras`, `attendwatch.STATE`, `gradewatch.STATE`, `notify._SEEN_NOTIF`, `gcal.TOKEN_FILE`, `auth.*` đều qua `paths.out(...)`; `api/*.json`, `local_data.json`, `attendance_state.json`, `seen_notifications.json` chmod `0600` (như `auth._save`/`gcal._save` vốn có). **Còn sót:** `gradewatch._save_state` **chưa** chmod `0600` — nên có 1 helper dùng chung thay vì 3 bản sao. |

<details><summary>Nội dung 3 cửa ải lúc chốt (giữ lại để tra cứu) · the original gate table</summary>

| | Vấn đề | Bắt buộc |
|---|---|---|
| 🔴 | **Rò chat id của chủ máy.** `fapc/__init__.py:7-18` và `fapc/config.py:12-21` là **HAI** loader `.env` độc lập, cả hai `setdefault`. Chặn danh sách khóa ở loader thứ nhất là **vô ích** vì loader thứ hai bơm lại `TELEGRAM_CHAT` của chủ máy ngay sau đó (`config.py:19` chạy trước `config.py:29`) ⇒ **điểm của bạn bè bắn vào chat của bạn**. | Sửa **cả hai** loader, hoặc gộp làm một |
| 🔴 | **Google Calendar phá dữ liệu.** `iCalUID` không chứa mã sinh viên (`gcal.py:98`), `_list_fapc_events` lọc bằng mỗi `fapc=1` (`gcal.py:119`), `_prune_plan` xóa mọi event fapc không có trong lần fetch hiện tại (`gcal.py:127-130`) ⇒ `calendar-prune` chạy dưới profile A **xóa sạch cả kỳ của profile B**. Guard 30% (`gcal.py:138-141`) không cứu được vì tỉ lệ tính lại mỗi lần; `--force` bỏ qua luôn. | Fix UID+tag **cùng PR**, hoặc **chặn hẳn** gcal khi có profile |
| 🔴 | **`output/api/` đè nhau.** `fap extract` ghi tên file cố định (`extract.py:20-21`) — học phí, hồ sơ, CCCD của người này đè lên người kia. Ngoài ra `gradewatch._save_state`, `attendwatch`, `notify._save_seen` **không** chmod 0600 (khác `auth._save`/`gcal._save`). | Tách theo profile + chmod 0600 |

</details>

> 🔴 **CÒN LẠI — việc thủ công, KHÔNG có trong code:** `.gitignore` mới chỉ có dòng `.env` (khớp **đúng** tên đó), nên `.env.<tên>` **SẼ BỊ COMMIT** cùng bot token/chat id của người khác. Phải thêm `.env.*` **và** `!.env.example` **trước khi** tạo profile đầu tiên. Xem [19-multi-profile §3](19-multi-profile.md#3-file-cấu-hình-của-profile--the-per-profile-env-file).

### ⚠️ Ràng buộc chéo với §3
Doctrine §3 là "chỉ MỘT nơi được refresh". Nếu một người bạn cũng copy `token.json` về laptop của họ thì profile đó có **hai** nơi refresh → đua rotation, và lần này **người bạn đó không tự sửa được**. ⇒ Doctrine §3 phải thành **chính sách onboarding từng profile**, viết thành tài liệu.

> ✅ **ĐÃ LÀM** — viết thành [19-multi-profile §4 (onboarding)](19-multi-profile.md#4-thêm-một-người--onboarding-a-second-person) + [§6.3](19-multi-profile.md#63--refresh_token-của-mỗi-người-nằm-trên-server-của-bạn--everyones-refresh-token-lives-on-your-server), và nhắc lại ngay trong `deploy/setup-profile.sh`.

### ⚠️ Bug (b) ở §2 là điều kiện tiên quyết
3 tiến trình/profile × N profile = **3N** lần refresh đồng thời sau mỗi `update.sh`. Trong cùng 1 profile, 3 tiến trình vẫn dùng chung 1 `oauth_tokens.json` và 1 tên tmp cố định. **Phải sửa §2(b) trước khi làm §4.**

> ✅ **ĐÃ LÀM TRƯỚC** — §2(b) xong (tmp theo PID + seed `last_refresh` lệch nhau) nên §4 mới ship. Lưu ý vẫn đúng: **mỗi profile 1 bộ tiến trình riêng**, đừng chạy 2 instance cùng một profile.

### Câu hỏi còn mở → ĐÃ TRẢ LỜI · answered

- ~~Các profile có **cùng campus** không?~~ → **Tách theo profile.** `subjects_catalog.json` nằm trong `output/profiles/<tên>/`: dữ liệu nhỏ, và profile khác campus vẫn ra đúng danh mục. Đổi lại mỗi profile tự dựng cache một lần.
- ~~Google Calendar: dùng chung 1 tài khoản Google hay mỗi người một?~~ → **Cả hai đều an toàn**, vì quyền sở hữu tính theo **mã sinh viên** (`fapc_owner`) chứ không theo lịch: `calendar-prune` chỉ xóa event mang mã SV của chính nó. Dùng chung 1 tài khoản thì lịch bị **trộn** (không mất dữ liệu) — muốn tách thì đặt `GCAL_CALENDAR_ID` trong `.env.<tên>` (khóa này **không** thừa kế, nhưng mặc định vẫn là `primary`). Mỗi profile phải tự chạy `fap calendar-auth` một lần (token Google riêng theo profile). Chi tiết: [19-multi-profile §6.2](19-multi-profile.md#62--google-calendar-dùng-chung--sharing-one-google-calendar).
- ~~`/update` có nên cho mọi profile gọi không?~~ → **KHÔNG.** `/update` giờ **TẮT mặc định**, cần `FAP_ALLOW_UPDATE=1` (đúng như đề xuất) và khóa này nằm trong danh sách **không thừa kế**, nên chỉ unit/`.env` của chủ máy bật được. Kiểm tra chủ sở hữu bot vẫn chạy trước như cũ.
- **Đồng ý (không phải kỹ thuật):** refresh_token của mỗi người bạn sẽ nằm trên VPS **của bạn**, scope `openid email profile offline_access`. Mỗi người phải biết và đồng ý rõ ràng. → Đã thành **quy trình onboarding bắt buộc**, bước 1: [19-multi-profile §4](19-multi-profile.md#4-thêm-một-người--onboarding-a-second-person). `deploy/setup-profile.sh` **từ chối chạy** nếu chưa có token do chính người đó tạo.

---

## 5. Sự thật đã kiểm chứng · Verified facts

Ghi lại để mai khỏi điều tra lại. Đã đo/đọc code thật:

- Thông báo điểm mới: **54 dòng / 896 ký tự** — dưới cả 1900 (Discord) lẫn 4000 (Telegram) ⇒ **không bị cắt**. Nén lại là vì dễ đọc, không phải sửa bug.
- `output/grade_state.json` **chưa tồn tại** trên máy này ⇒ vụ 47 điểm đúng là một lần baseline lại sau `64bd944`.
- `detail_text`: **2691 ký tự** (3 môn) / **5325** (6 môn). *(Phân tích ban đầu ghi 3482/6965 là **sai ~30%** — đã tính dư một cột "comment" mà parser không hề sinh ra. Kết luận "đang bị cắt" thì vẫn đúng.)*
- `fmt.py:6` viết "dùng emoji + xuống dòng **thay vì căn cột**", nhưng `fmt.py:79-81` lại `.ljust()` căn cột ⇒ `fmt.table` là renderer **sai mô hình** cho chat, và chính nó chiếm phần lớn số ký tự bị cắt ở `detail_text`. **Đừng copy `fmt.table` làm mẫu.**
- `grades.py:102` **có** trả `category` thật; `gradewatch.py:26` `_NAME_KEYS` chứa `'categoryName'` chứ không phải `'category'` nên bị bỏ đi. Thêm key vào event dict là **an toàn** — mọi test đều dùng `any(e["item"]==…)`, không so sánh dict.
- Telegram 409: 2 instance **hiếm khi** trả lời trùng (cả hai bỏ backlog lúc khởi động, `telegrambot.py:63-68`) — nhưng **vòng lặp 409 vô hạn** và **nhắc lịch trùng** thì chắc chắn xảy ra. *(Phân tích ban đầu thổi phồng vụ trả lời trùng.)*
- `/update` chỉ `os.execv` **tiến trình gọi nó**, không restart cả cụm. *(Phân tích ban đầu thổi phồng.)*

---

## 6. Đợt 09–10/2026 · Sep–Oct 2026

**VI —** Nhật ký các thay đổi + quyết định của đợt này. Chi tiết trường API: [20-api-fields](20-api-fields.md).
**EN —** Changes and decisions from this round. Field details: [20-api-fields](20-api-fields.md).

| Thay đổi · Change | Quyết định chính · Key decision | Trạng thái · Status |
|---|---|---|
| Google Calendar **ngay trong chat** + **nhiều đích Google** (`40c783d`) | OAuth kiểu **loopback-paste** (chạy được trên VPS không màn hình); mỗi đích một nhãn; **từ chối** 2 nhãn trỏ cùng một `calendar_id` cụ thể (prune xoá chéo) | ✅ `main` |
| **Link Meet** cho buổi online trong nhắc tiết + lịch (PR #1, `a834324`) | `meetURL` là **mã Meet trần** → ghép URL; buổi thiếu mã **mượn** mã của lớp chỉ khi lớp có đúng 1 mã cả kỳ; Discord không bao giờ ping (`allowed_mentions`) | ✅ `main` |
| 4 trường API chưa dùng: điểm danh từng buổi, trạng thái đơn, nội dung thông báo, giai đoạn môn (PR #2) | Mã trạng thái lấy từ **hàm của app chính thức**; mã lạ hiện ❔; sửa **báo nhầm nguy cơ cấm thi** đầu kỳ bằng 2 điều kiện tuỳ chọn, fail-safe; thông báo khoá theo `#id` | 🔄 PR #2 (CI xanh) |
| **Bẫy mạng** trong test offline (`tests/test_logic.py`) | Test nào thử gọi mạng thật là FAIL — kể cả khi code nuốt lỗi; chỉ ghi host (token bot Telegram nằm trong path) | 🔄 PR #2 |
| `docs/20-api-fields.md` + `analysis/keys_schema.py` | Ghi lại sự thật đã đo để khỏi điều tra lại; sơ đồ trường **chỉ tên khoá**, không bao giờ in giá trị | 🔄 PR #2 |

**Còn mở · Open:**
- ~~`/profile` gửi CCCD / SĐT / ngày sinh / email qua bot → nên chỉ hiện ở CLI~~ → **xong** ([§7](#7-đợt-2026-10-03--round-of-2026-10-03)): CCCD / SĐT / ngày sinh chỉ ở CLI; `email` vẫn hiện trong chat.
- Ứng viên còn lại: [20](20-api-fields.md) §3 (tài liệu môn, cờ qua/trượt transcript, điểm chính thức từ `GetMarkByCourse`, ~~đợt feedback~~ → xong ở §7…).
- ~~Lỗi phụ từ audit: `_news_get` phân biệt hoa thường; `exam_countdown` không nhận `examSubject`; `fees()` báo "chưa có chi tiết" khi thật ra 404; `conduct.fetch` coi mọi code 201 là "chưa có dữ liệu".~~ → **xong cả bốn** ([§7](#7-đợt-2026-10-03--round-of-2026-10-03)).
- ~~Kiểm bản app mới **versionCode 29**~~ → **xong (2.0.5)**: v1 không đổi ⇒ fap-cli chạy bình thường; mới có **API v2** qua `fap-proxy` (chưa bật được kiểm chứng, [21](21-api-v2.md)), **OTA tự host** ⇒ JS có thể đổi không cần bản Play mới ([20](20-api-fields.md) §5), và **`studentStatus` đổi nghĩa** (`2` = Hủy, `3` = Chờ thanh toán) — đã sửa ngay trong PR #2 trước khi merge.
- ~~Chuẩn bị cho v2 (chưa làm): `check_auth` hiểu lỗi kiểu v2 (tránh "danh sách rỗng im lặng"); bộ phân loại thuần cảnh báo sớm khi v1 bị tắt; script so APK offline có che dữ liệu.~~ → **xong cả ba**, thêm client v2 opt-in ([§7](#7-đợt-2026-10-03--round-of-2026-10-03)).

---

## 7. Đợt 2026-10-03 · Round of 2026-10-03

**VI —** Nhánh `feat/v2-prep-todo`: chuẩn bị cho API v2 của myFAP 2.0.5 + các việc "chỉ bạn làm được" + cảnh báo đơn từ + dọn các lỗi phụ còn mở ở §6. Lúc chốt: **181/181 unit + 195/195 integration** test offline PASS.
**EN —** Branch `feat/v2-prep-todo`: groundwork for myFAP 2.0.5's API v2 + a to-do block + application alerts + the minor bugs left open in §6. At sign-off: **181/181 unit + 195/195 integration** offline tests PASS.

| Thay đổi · Change | Quyết định chính · Key decision | Tài liệu · Docs |
|---|---|---|
| **Client API v2 opt-in** (`fapc/core/apiv2.py`, `FAP_API_VERSION=v2`) | Mặc định **v1**, hành vi v1 y nguyên. v2 **thử nghiệm, chưa kiểm chứng thật**. Khoá ký v2 **không nhúng, không commit** — chỉ trong `.env`, mỗi người tự trích từ APK của mình. `token.json` đóng dấu `api_version`; lệch ⇒ `fap refresh`. Mọi request v2 ký bằng **token của chính người dùng** · opt-in, experimental; key only in `.env`, never committed; version-stamped token | [21](21-api-v2.md) §5 · [15](15-config.md) |
| `analysis/apk_drift.py` | So APK/bundle **offline**, thư viện chuẩn, không in secret/PII; exit `0/1/2` cho cron/CI; `--write-v2-key` ghi `.env` mà không in giá trị · offline drift checker | [20](20-api-fields.md) §5.1 |
| `check_auth` nhận lỗi phiên kiểu v2 + gợi ý drift thụ động (`classify_drift`) | `code 401` / `Unauthorized` trong HTTP 200 = hết phiên; **HTTP 500 không tính** (tránh vòng refresh, khác app); drift chỉ soi phản hồi đã có (**0 request thêm**), in **1 lần/tiến trình**, không URL/token | [16](16-troubleshooting.md) · [21](21-api-v2.md) §4 |
| **Một** quy tắc chọn kỳ (`select_semester`) | Kỳ đầu tiên chứa hôm nay, so theo **ngày** — **ngày cuối kỳ vẫn trong kỳ** (**cố ý lệch app**, app so thời điểm với 00:00 ngày cuối ⇒ mất lịch ngày cuối); không có ⇒ `startDate` gần nhất (như app); dùng chung cho `current_semester` + `pick_semester` · last day inclusive, a deliberate deviation | [16](16-troubleshooting.md) · [17](17-architecture.md) §2 |
| **Việc cần làm** (`fap todo`, `/todo`, cuối `/all`, gắn vào `fap notify today` chỉ khi có việc) | **Chỉ đọc**, chỉ dẫn tới kênh chính thức; `CheckUpdateProfile` chặt hơn app (chỉ boolean `false` trên v1; v2: khác rỗng); `GetStudentRate` **không dùng** (nghĩa trường chưa kiểm chứng) · read-only, points to official channels | [13](13-notify.md) §11 |
| **Đơn đổi trạng thái** trong `fap notify notifications` | Cùng nhịp, **không job mới**; khoá theo `w_APP_ID`; lần đầu ghi mốc im lặng; `output/applications_state.json` **riêng từng máy / từng profile**, không copy | [13](13-notify.md) §10 · [14](14-deploy.md) §9 · [19](19-multi-profile.md) |
| `fap fees`: link hoá đơn điện tử `dng.fpt.edu.vn` + 404 `GeFeeByRoll`; khoá tin tức / thẻ lịch thi 2.0.5; `conduct` 201 | Link chứa MSSV ⇒ **chỉ CLI**; 404 = "không dùng được", không phải "chưa có học phí"; khoá so **không phân biệt hoa/thường**; `201` do token/checksum được **báo**, chỉ NullReference mới là "chưa có điểm" | [11](11-commands.md) · [03](03-extraction-catalog.md) · [20](20-api-fields.md) §1 |
| `/profile` trên bot/web ẩn ngày sinh · SĐT · CCCD | PII nhạy cảm **chỉ ở CLI** (`fap profile`); mặc định an toàn (`full=False`) | [20](20-api-fields.md) §4 |
| `fap doctor` | In phiên bản API; đang v2 thì `FAP_V2_KEY` **có/thiếu** — không bao giờ in giá trị | [11](11-commands.md) |

**Quyết định · Decisions:**
- **VI —** Ngày cuối kỳ **tính là trong kỳ** — lệch app myFAP 2.0.5 có chủ ý. · **EN —** The last day of a term **counts as inside it** — a deliberate deviation from myFAP 2.0.5.
- **VI —** v2 là **opt-in**; khoá chỉ ở `.env` (hoặc biến môi trường), **không bao giờ** commit, in ra, hay nằm trong `token.json`/log. · **EN —** v2 is **opt-in**; the key lives only in `.env`/the environment and is **never** committed, printed, or written to `token.json`/logs.
- **VI —** PII hồ sơ (ngày sinh, SĐT, CCCD) **chỉ ở CLI**. · **EN —** Profile PII (DOB, phone, ID card) is **CLI-only**.
- **VI —** `GetApiActive` **không bao giờ** được gọi — fap-cli không tự dò cờ v1/v2 của server; người dùng tự chọn bằng `FAP_API_VERSION`. · **EN —** `GetApiActive` is **never** called — fap-cli doesn't probe the server's v1/v2 flag; the user picks with `FAP_API_VERSION`.
- **VI —** `GetStudentRate` **không dùng** (nghĩa trường chưa kiểm chứng; v2 cũng không có). · **EN —** `GetStudentRate` stays **unused** (unverified field meanings; absent on v2 anyway).

**Chưa kiểm chứng live · Not yet verified live:**
- **VI —** v2 **từ đầu tới cuối**: server có chấp nhận chữ ký/tham số, token v1 có dùng được trên v2, phản hồi đăng nhập v2 có cùng dạng v1 không. · **EN —** v2 **end-to-end**: whether the server accepts the signature/params, whether v1 tokens work on v2, whether the v2 login reply matches v1's shape.
- **VI —** `CheckOpenFeedBack` / `CheckUpdateProfile` trong một **đợt feedback đang mở thật** / khi FAP **thật sự** yêu cầu cập nhật hồ sơ. · **EN —** `CheckOpenFeedBack` / `CheckUpdateProfile` during a **real open round** / a **real** profile-update request.
- **VI —** Link hoá đơn `dng.fpt.edu.vn` với tài khoản **campus khác Đà Nẵng** (app hiện nút cho mọi campus, nhưng chưa mở thử). · **EN —** The `dng.fpt.edu.vn` invoice link for **non-Da Nang campuses** (the app shows it for every campus, untested).
- **VI —** `w_APP_ID` có **ổn định** qua thời gian (khoá của cảnh báo đơn từ). · **EN —** Whether `w_APP_ID` is **stable** over time (the application-alert key).

> 🧭 **VI —** Không có bước deploy thủ công bắt buộc: v2 mặc định tắt; `applications_state.json` tự ghi mốc (im lặng) ở lượt `fap notify notifications` đầu tiên. Bật v2 thì theo [21](21-api-v2.md) §5 (`FAP_V2_KEY` + `FAP_API_VERSION=v2` + `fap refresh` + restart service).
> 🧭 **EN —** No mandatory manual deploy step: v2 is off by default and `applications_state.json` baselines itself (silently) on the first `fap notify notifications` round. To opt into v2 follow [21](21-api-v2.md) §5 (`FAP_V2_KEY` + `FAP_API_VERSION=v2` + `fap refresh` + restart services).

---

> ⚠️ **VI —** Dự án KHÔNG chính thức, chỉ dùng cho dữ liệu của chính bạn. Đọc [../SECURITY.md](../SECURITY.md).
> **EN —** Unofficial project, your own data only. Read [../SECURITY.md](../SECURITY.md).
