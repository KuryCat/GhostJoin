# mc-afk-bot-tester

Một Minecraft (Java Edition) protocol client tối giản viết bằng Python thuần
(chỉ dùng thư viện chuẩn: `socket`, `struct`, `hashlib`, `zlib`) — kết nối vào
server, đi hết luồng Handshake → Login → Configuration → Play, và giữ kết nối
sống bằng cách phản hồi Keep Alive.

## Mục đích

Repo này được viết ra để **kiểm thử hệ thống chống bot (anti-bot) của một
server Minecraft do chính bạn quản lý, hoặc server mà bạn đã được chủ sở hữu
cho phép rõ ràng**. Nó mô phỏng một kết nối client ở mức protocol (không có
logic render, vật lý, hay tương tác trong game) — hữu ích để kiểm tra xem hệ
thống chống bot của server có phát hiện và chặn được các kết nối "trần"
kiểu này hay không.

Trong quá trình phát triển, script này từng bị một server thật chặn đúng ở
bước cuối của Configuration state (server chỉ lặp lại Keep Alive, không bao
giờ gửi Finish Configuration) — đây là ví dụ thực tế của việc một hệ thống
anti-bot phát hiện và giữ kết nối "nghi ngờ" ở trạng thái lấp lửng thay vì từ
chối thẳng. Ghi lại ở đây để làm tài liệu tham khảo khi bạn kiểm thử.

## Giới hạn

- **Chỉ hoạt động với server offline-mode** (`online-mode=false`). Server bật
  xác thực Mojang/Microsoft cần Encryption Request + session token hợp lệ,
  không nằm trong phạm vi script này.
- Packet ID trong Minecraft Protocol thay đổi khá thường xuyên giữa các bản.
  ID trong script này lấy theo protocol ~773–776 (gần bản 26.1.2 tại thời
  điểm viết). Bật `DEBUG = True` trong file để in ra mọi packet ID nhận được
  và tự đối chiếu tại
  [minecraft.wiki/w/Java_Edition_protocol/Packets](https://minecraft.wiki/w/Java_Edition_protocol/Packets)
  nếu server bạn dùng bản khác.
- Không có logic render/vật lý/tương tác — client chỉ "đứng yên" ở Play
  state. Nếu bạn cần mô phỏng hành vi di chuyển/hành động để kiểm thử kỹ hơn,
  cần tự bổ sung thêm.

## Cách dùng

```bash
python mc_afk_bot.py <host> <port> <username> [protocol_version]
```

Ví dụ:

```bash
python mc_afk_bot.py 127.0.0.1 25565 TestBot 775
```

## Lưu ý sử dụng có trách nhiệm

- Chỉ chạy trên server của bạn, hoặc server mà chủ sở hữu **đã đồng ý rõ
  ràng** cho việc kiểm thử này.
- Không dùng để tạo số lượng lớn kết nối giả nhằm gây quá tải server (DoS),
  thao túng số liệu người chơi hiển thị công khai, hay né tránh các biện
  pháp bảo vệ mà bạn không có quyền vượt qua.
- Nếu hệ thống chống bot của server chặn được script này — đó là kết quả
  kiểm thử mong muốn, không phải lỗi cần "vá" để vượt qua bằng mọi giá.

## Giấy phép

Xem file [LICENSE](./LICENSE). Được phép tự do sử dụng, sao chép, chỉnh sửa,
phân phối lại; phần mềm được cung cấp "nguyên trạng", tác giả không chịu
trách nhiệm cho bất kỳ hậu quả nào phát sinh từ việc sử dụng hoặc lạm dụng.
