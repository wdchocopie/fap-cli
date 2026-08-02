# 18 · Việc đang làm dở · Work in progress

> **VI —** Kế hoạch đã chốt nhưng CHƯA code. Mở file này ra là làm tiếp được ngay, không cần điều tra lại.
> **EN —** Agreed but NOT yet implemented. Pick up from here without re-investigating.

**Chốt ngày:** 2026-08-02 · **Nền:** commit `3c42ca9` · **Trạng thái:** 169/169 test offline PASS

Mọi số liệu dưới đây là **đo thật** (render offline bằng chính code hiện tại), không phải ước lượng. Đã qua 1 vòng agent kiểm chứng chéo — các chỗ phân tích ban đầu nói sai đã được sửa và ghi chú ở [§5](#5-sự-thật-đã-kiểm-chứng--verified-facts).

---

## 0. Bốn quyết định đã chốt · The four decisions

| # | Việc | Quyết định |
|---|---|---|
| 1 | Hiển thị thông báo điểm mới | **Nhóm theo loại + gộp dòng LAB** (phương án B+A2) |
| 2 | 2 bug thật vừa phát hiện | **Sửa cả hai** |
| 3 | 1 session chạy 2 nơi | **Viết tài liệu + thêm cờ `FAP_TOKEN_READONLY`** |
| 4 | Nhiều account | **Hướng "bạn bè tự login"** — mỗi người tự `fap login`, dữ liệu chỉ về kênh của chính họ |

**Thứ tự làm:** §1 → §2 → §3 → §4. §1 không dính gì tới phần còn lại nên làm trước được ngay.

---

## 1. Gộp dòng LAB cho thông báo điểm mới · Compact grade alert

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

## 2. Hai bug thật · Two real bugs

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

## 3. Một session dùng cả PC lẫn VPS · Shared session

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

## 4. Nhiều account · Multi-profile

**Hướng đã chốt:** mỗi người bạn **tự chạy `fap login` của họ**, dữ liệu chỉ chảy về kênh của **chính họ**. Không nhận hộ mật khẩu/token của người khác.

**Thiết kế:** `FAP_PROFILE=alice` → `output/profiles/alice/*.json`; mỗi profile 1 process/systemd unit. Không đặt biến ⇒ đường dẫn resolve **y hệt hiện tại** ⇒ VPS đang chạy không cần migrate, không phải login lại.

Thêm `fapc/core/paths.py` (~25 dòng): `profile()` / `out_dir()` / `out(*parts)`. Viết lại ~11 hằng đường dẫn để gọi `paths.out(...)` nhưng **GIỮ NGUYÊN TÊN hằng ở module level** — `tests/integration_offline.py:63` và `tests/test_logic.py:564` gán thẳng `aw.STATE` / `gw.STATE` / `notify._SEEN_NOTIF`; biến chúng thành hàm là **hỏng cả 2 bộ test**.

### 🚧 Ba cửa ải phải xử lý TRƯỚC khi ship

| | Vấn đề | Bắt buộc |
|---|---|---|
| 🔴 | **Rò chat id của chủ máy.** `fapc/__init__.py:7-18` và `fapc/config.py:12-21` là **HAI** loader `.env` độc lập, cả hai `setdefault`. Chặn danh sách khóa ở loader thứ nhất là **vô ích** vì loader thứ hai bơm lại `TELEGRAM_CHAT` của chủ máy ngay sau đó (`config.py:19` chạy trước `config.py:29`) ⇒ **điểm của bạn bè bắn vào chat của bạn**. | Sửa **cả hai** loader, hoặc gộp làm một |
| 🔴 | **Google Calendar phá dữ liệu.** `iCalUID` không chứa mã sinh viên (`gcal.py:98`), `_list_fapc_events` lọc bằng mỗi `fapc=1` (`gcal.py:119`), `_prune_plan` xóa mọi event fapc không có trong lần fetch hiện tại (`gcal.py:127-130`) ⇒ `calendar-prune` chạy dưới profile A **xóa sạch cả kỳ của profile B**. Guard 30% (`gcal.py:138-141`) không cứu được vì tỉ lệ tính lại mỗi lần; `--force` bỏ qua luôn. | Fix UID+tag **cùng PR**, hoặc **chặn hẳn** gcal khi có profile |
| 🔴 | **`output/api/` đè nhau.** `fap extract` ghi tên file cố định (`extract.py:20-21`) — học phí, hồ sơ, CCCD của người này đè lên người kia. Ngoài ra `gradewatch._save_state`, `attendwatch`, `notify._save_seen` **không** chmod 0600 (khác `auth._save`/`gcal._save`). | Tách theo profile + chmod 0600 |

### ⚠️ Ràng buộc chéo với §3
Doctrine §3 là "chỉ MỘT nơi được refresh". Nếu một người bạn cũng copy `token.json` về laptop của họ thì profile đó có **hai** nơi refresh → đua rotation, và lần này **người bạn đó không tự sửa được**. ⇒ Doctrine §3 phải thành **chính sách onboarding từng profile**, viết thành tài liệu.

### ⚠️ Bug (b) ở §2 là điều kiện tiên quyết
3 tiến trình/profile × N profile = **3N** lần refresh đồng thời sau mỗi `update.sh`. Trong cùng 1 profile, 3 tiến trình vẫn dùng chung 1 `oauth_tokens.json` và 1 tên tmp cố định. **Phải sửa §2(b) trước khi làm §4.**

### Câu hỏi còn mở
- Các profile có **cùng campus** không? (quyết định `subjects_catalog.json` dùng chung được hay phải tách — `GetSubjets` chỉ nhận `campusCode`, dữ liệu công khai theo campus)
- Google Calendar: dùng chung 1 tài khoản Google hay mỗi người một?
- `/update` có nên cho mọi profile gọi không? (hiện bất kỳ owner nào cũng `git pull` + restart trên **checkout dùng chung**) → đề xuất thêm `FAP_ALLOW_UPDATE=1` chỉ có trong unit của chủ máy
- **Đồng ý (không phải kỹ thuật):** refresh_token của mỗi người bạn sẽ nằm trên VPS **của bạn**, scope `openid email profile offline_access`. Mỗi người phải biết và đồng ý rõ ràng.

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

> ⚠️ **VI —** Dự án KHÔNG chính thức, chỉ dùng cho dữ liệu của chính bạn. Đọc [../SECURITY.md](../SECURITY.md).
> **EN —** Unofficial project, your own data only. Read [../SECURITY.md](../SECURITY.md).
