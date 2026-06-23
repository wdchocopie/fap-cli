# Đăng nhập FAP qua FE Identity (OAuth) — không cần máy ảo

Gói `fapc` (lệnh `fap`) cho phép **bất kỳ sinh viên FPT** (khóa 19+, đăng nhập Google
@fpt.edu.vn) lấy token FAP **bằng chính tài khoản của mình**, hoàn toàn qua HTTP — không cần
emulator, không cần root, không lưu mật khẩu.

## Cài & dùng

```bash
pip install -e .         # chạy từ thư mục gốc repo → tạo lệnh `fap`

fap login        # đăng nhập lần đầu (mở link, login Google 1 lần)
fap refresh      # làm mới token tự động (headless, dùng refresh_token)
fap whoami       # xem token đã lưu

# sau đó dùng dữ liệu:
fap extract      # kéo toàn bộ dữ liệu (tự dùng output/token.json)
fap ics          # xuất lịch .ics
```

Khi `login`: công cụ mở trình duyệt → bạn đăng nhập Google @fpt.edu.vn → xong. Token lưu vào
`output/token.json` (token FAP) và `output/oauth_tokens.json` (có `refresh_token`).
Từ lần sau, `refresh` chạy **không cần thao tác tay** (đến khi refresh_token hết hạn).

## Cách hoạt động (đã reverse từ app)

```
FE Identity (IdentityServer):  https://feid.fpt.edu.vn
client_id:                     fap-mobile-front-end   (public client, PKCE, không secret)
redirect:                      io.identityserver.demo:/oauthredirect

1) OAuth login (1 trong 2):
   • Device flow:  POST /connect/deviceauthorization → bạn mở link + login → poll /connect/token
   • Fallback PKCE: mở /connect/authorize → login → copy URL redirect → đổi /connect/token
   → access_token (JWT) + refresh_token (+ id_token)

2) Đổi sang token FAP:
   POST https://api.fpt.edu.vn/fap/api/MyFAP/AuthenticationByFeId?campusCode=&checksum=
   body: { "token": access_token }
   checksum = base64(HMAC_SHA1(SECRET, PREFIX + campusCode + "DD/MM/YYYY HH:00"))
              .replace('=','%3d').replace(' ','+')      // hàm getCheckSumLogin
   → token FAP (authenkey)
```

## Nếu token FAP bị từ chối (đổi SCOPE)

`AuthenticationByFeId` cần access token có scope/audience phù hợp. Mặc định công cụ xin
`openid email profile offline_access`. Nếu server FAP trả lỗi token, mở `fapc/core/auth.py` sửa biến
`SCOPE`, thử thêm: `fsp-mobile-front-end` hoặc `identity-service` (các scope FE Identity hỗ trợ).

## ⚠️ Lưu ý khi public cho người khác

- **Mỗi người chỉ truy cập dữ liệu của chính mình** (đăng nhập Google của họ) — đây là thiết kế an toàn.
- Công cụ nhúng **SECRET checksum + client_id** trích từ APK công khai (ai cũng giải nén được).
  Khi public, hãy ghi rõ đây là **dự án không chính thức**, dùng cho mục đích cá nhân/học tập.
- **Tôn trọng hạ tầng trường:** không quét hàng loạt, không vòng lặp dồn dập, cache kết quả.
  FAP/FE Identity là hệ thống thật — gây tải bất thường có thể bị chặn hoặc vi phạm quy định.
- Trường có thể **đổi secret/client bất kỳ lúc nào** → công cụ sẽ hỏng; cần cập nhật lại.
- Không thêm tính năng truy cập dữ liệu người khác (đổi MSSV), giả mạo, hay né tránh xác thực.
