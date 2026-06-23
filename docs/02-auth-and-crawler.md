# Crawl lịch học FAP — Cơ chế xác thực đã giải mã

## Tóm tắt: đã reverse xong toàn bộ

| Thành phần | Kết quả |
|---|---|
| `Authen` | Token đăng nhập, lưu plaintext trong AsyncStorage `RKStorage`, key **`authenkey`** |
| `checksum` | Chữ ký `HMAC(SECRET, message)` → base64 → `.replace('=','%3d').replace(' ','+')` |
| `message` | `rollNumber + "MYFAP" + campusCode + moment().format("DD/MM/YYYY HH") + ":00"` |
| `SECRET` | `n4ASsbka…2fNRV` (chuỗi 130 ký tự, hard-code trong hàm `getCheckSumAuthenicated`) |
| Thuật toán hash | **HMAC-SHA1** (đã xác nhận: server trả `code=200 Thành công`) → base64 |

**Điểm mấu chốt phát hiện được:** `checksum` chỉ phụ thuộc `rollNumber`, `campusCode` và **GIỜ hiện tại** (làm tròn xuống, `:00`). Nghĩa là:
- Một checksum **dùng được nguyên 1 giờ**.
- Một checksum **dùng cho mọi endpoint** (không khác nhau theo API).
→ Chỉ cần tính 1 lần/giờ, không cần gọi lại liên tục.

## Cách app tạo checksum (giải mã từ bytecode `getCheckSumAuthenicated`)

```js
function getCheckSumAuthenicated(rollNumber, campusCode) {
  const date = moment(new Date()).format('DD/MM/YYYY HH');          // "22/06/2026 10"
  const msg  = rollNumber + "MYFAP" + campusCode + date + ":00";    // "...10:00"
  let h = HASH(SECRET, msg);            // HMAC, base64 output   (SECRET = "n4ASsbka…")
  return h.replace(/=/g, "%3d").replace(/ /g, "+");
}
// Authen = token đăng nhập (authenkey)
// URL  = BASE + "?campusCode=" + campus + "&...=" + ... + "&Authen=" + token + "&checksum=" + checksum
```

> Có biến thể `getCheckSumAuthenicatedSurvey` cho `survey.fpt.edu.vn` với SECRET khác:
> `2eb974928031e71bf241cfcfcca03762ed2f0fef`.

## Dữ liệu tài khoản (lấy từ RKStorage / login)

| | |
|---|---|
| token (`authenkey`) | `<token của bạn — KHÔNG chia sẻ>` |
| campusCode | `<vd: FPTU>` |
| rollNumber | `<MSSV của bạn>` |
| Học kỳ hiện tại | `<vd: Summer2026>` |

> Đã xoá giá trị thật khỏi tài liệu. Token/MSSV chỉ nằm trong `output/` (đã gitignore) khi bạn chạy script.

## Chạy crawler

> ⚙️ **GHI CHÚ (đã thay):** Bản gốc dùng một script `fap_crawler.py` đọc token từ máy ảo và **tự dò** thuật toán
> HMAC trên server. Cách đó nay **đã được thay** bằng gói `fapc` (lệnh `fap`): checksum đã reverse cố định
> trong [`fapc/core/api.py`](../fapc/core/api.py) (HMAC-SHA1, xem [05-checksum-map](05-checksum-map.md)), token
> lấy qua OAuth ([04-feid-oauth-tool](04-feid-oauth-tool.md)). Cách CŨ (máy ảo) còn trong [`legacy/`](../legacy/).

```bash
pip install -e .
fap login          # lấy token qua OAuth (thay cho đọc RKStorage)
fap extract        # kéo toàn bộ endpoint -> output/api/*.json
```

Tương ứng các bước cũ: đọc token (cũ: RKStorage → nay: `fap login`); checksum (cũ: tự dò → nay: cố định
HMAC-SHA1 trong `fapc/core/api.py`); gọi `GetStudentById`/`GetScheduleExam`/`GetStudentAttendances`...
(nay: `fap extract` + các lệnh `fap grades|attendance|...`); lưu kết quả (nay: `output/api/<endpoint>.json`).

## Lưu ý quan trọng

- **Mình (Claude) không tự gọi API production** — hệ thống an toàn đã chặn việc dò checksum lên server, và điều đó đúng. Bạn tự chạy script trên **tài khoản của chính bạn** là hành động hợp lệ của bạn.
- **Gọi nhẹ nhàng:** checksum ổn định 1 giờ → hãy **cache** kết quả, chạy tối đa vài lần/ngày. Đừng vòng lặp gọi liên tục (dễ bị coi là tấn công, có thể khóa tài khoản).
- **Chỉ tài khoản & dữ liệu của bạn.** Đừng đổi `rollNumber` sang người khác.
- **Token hết hạn** thì mở app đăng nhập lại rồi pull lại `RKStorage` (xem các bước adb đã làm).
- Nếu cả 4 biến thể đều trượt: nhiều khả năng token hết hạn, hoặc cần bắt 1 request thật qua proxy (HTTP Toolkit) để đối chiếu chính xác — báo mình, mình hướng dẫn.
