"""
mc_afk_bot.py
-------------
Script kết nối vào server Minecraft (chế độ OFFLINE / cracked, không cần đăng nhập Mojang)
và giữ kết nối sống để server hiển thị người chơi đã vào.

Hỗ trợ đầy đủ luồng hiện đại: Handshake -> Login -> Configuration -> Play
(Mojang thêm Configuration state bắt buộc từ bản 1.20.2 trở đi).

LƯU Ý QUAN TRỌNG:
- Chỉ hoạt động với server OFFLINE-MODE (online-mode=false). Server bật xác thực
  Mojang/Microsoft cần Encryption Request + session token hợp lệ, không nằm trong
  phạm vi script này.
- Packet ID trong Minecraft Protocol đổi khá thường xuyên giữa các bản (kể cả các
  thư viện lớn như mineflayer cũng chưa theo kịp bản rất mới). ID trong script này
  lấy theo bảng protocol ~773-776 (gần nhất với 775 / bản 26.1.2 tại thời điểm viết).
  Nếu vẫn lỗi, bật DEBUG=True bên dưới để in ra mọi packet ID nhận được và tự đối
  chiếu với https://minecraft.wiki/w/Java_Edition_protocol/Packets

Cách dùng:
    python mc_afk_bot.py <host> <port> <username> [protocol_version]
"""

import hashlib
import socket
import struct
import sys
import zlib

DEBUG = True  # In ra mọi packet ID nhận được để dễ dò lỗi


# ---------- UUID offline-mode ----------

def offline_uuid_bytes(username: str) -> bytes:
    data = ("OfflinePlayer:" + username).encode("utf-8")
    digest = bytearray(hashlib.md5(data).digest())
    digest[6] = (digest[6] & 0x0F) | 0x30
    digest[8] = (digest[8] & 0x3F) | 0x80
    return bytes(digest)


# ---------- Đóng gói / giải mã VarInt, String ----------

def pack_varint(value: int) -> bytes:
    out = b""
    value &= 0xFFFFFFFF
    while True:
        temp = value & 0x7F
        value >>= 7
        if value != 0:
            temp |= 0x80
        out += struct.pack("B", temp)
        if value == 0:
            break
    return out


def pack_string(s: str) -> bytes:
    data = s.encode("utf-8")
    return pack_varint(len(data)) + data


def pack_ushort(value: int) -> bytes:
    return struct.pack(">H", value)


def pack_bool(value: bool) -> bytes:
    return b"\x01" if value else b"\x00"


def varint_from_bytes(data: bytes, offset: int):
    num = 0
    shift = 0
    while True:
        byte = data[offset]
        offset += 1
        num |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            break
        shift += 7
    return num, offset


# ---------- Đọc socket ----------

def read_n_bytes(sock: socket.socket, n: int) -> bytes:
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("Server đã đóng kết nối.")
        data += chunk
    return data


def read_varint_sock(sock: socket.socket) -> int:
    num = 0
    shift = 0
    while True:
        byte = read_n_bytes(sock, 1)[0]
        num |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            break
        shift += 7
    return num


# ---------- Lớp quản lý kết nối (có hỗ trợ nén) ----------

class MCConnection:
    def __init__(self, sock: socket.socket):
        self.sock = sock
        self.compression_threshold = -1  # -1 = chưa bật nén

    def send_packet(self, packet_id: int, payload: bytes):
        body = pack_varint(packet_id) + payload

        if self.compression_threshold >= 0:
            if len(body) >= self.compression_threshold:
                compressed = zlib.compress(body)
                packet_data = pack_varint(len(body)) + compressed
            else:
                packet_data = pack_varint(0) + body
            self.sock.sendall(pack_varint(len(packet_data)) + packet_data)
        else:
            self.sock.sendall(pack_varint(len(body)) + body)

    def read_packet(self):
        length = read_varint_sock(self.sock)
        raw = read_n_bytes(self.sock, length)

        if self.compression_threshold >= 0:
            data_length, offset = varint_from_bytes(raw, 0)
            body = raw[offset:]
            if data_length != 0:
                body = zlib.decompress(body)
        else:
            body = raw

        packet_id, offset = varint_from_bytes(body, 0)
        return packet_id, body[offset:]


# ---------- Logic chính ----------

def connect_and_join(host: str, port: int, username: str, protocol_version: int):
    raw_sock = socket.create_connection((host, port), timeout=10)
    conn = MCConnection(raw_sock)
    print(f"[+] Đã kết nối TCP tới {host}:{port}")

    # 1. Handshake -> next_state = 2 (login)
    handshake_payload = (
        pack_varint(protocol_version)
        + pack_string(host)
        + pack_ushort(port)
        + pack_varint(2)
    )
    conn.send_packet(0x00, handshake_payload)

    # 2. Login Start (= "hello" serverbound, id 0x00): name + UUID (16 byte thô)
    player_uuid = offline_uuid_bytes(username)
    conn.send_packet(0x00, pack_string(username) + player_uuid)
    print(f"[+] Đã gửi Login Start: {username} (UUID: {player_uuid.hex()})")

    # ---- Login state loop ----
    state = "login"
    while state == "login":
        packet_id, payload = conn.read_packet()
        if DEBUG:
            print(f"[debug] (login) packet_id=0x{packet_id:02X} len={len(payload)}")

        if packet_id == 0x00:
            reason = payload[1:].decode("utf-8", errors="replace") if payload else ""
            print(f"[-] Bị từ chối: {reason}")
            return
        elif packet_id == 0x01:
            print("[-] Server yêu cầu Encryption Request -> server đang bật online-mode "
                  "(cần xác thực Mojang/Microsoft), script này không hỗ trợ trường hợp đó.")
            return
        elif packet_id == 0x02:
            print("[+] Login Success nhận được.")
            conn.send_packet(0x03, b"")  # Login Acknowledged
            state = "configuration"
        elif packet_id == 0x03:
            threshold, _ = varint_from_bytes(payload, 0)
            conn.compression_threshold = threshold
            print(f"[+] Bật nén, threshold={threshold}")
        elif packet_id == 0x04:
            message_id, offset = varint_from_bytes(payload, 0)
            response = pack_varint(message_id) + b"\x00"
            conn.send_packet(0x02, response)
        else:
            pass

    # ---- Configuration state loop ----
    print("[+] Đang ở Configuration state...")

    # Client thật luôn TỰ gửi Client Information ngay khi vào Configuration,
    # không đợi server hỏi - thiếu bước này server sẽ đứng im chỉ gửi Keep Alive.
    client_info_payload = (
        pack_string("en_US")           # locale
        + struct.pack("b", 10)         # view distance
        + pack_varint(0)               # chat mode: enabled
        + pack_bool(True)              # chat colors
        + struct.pack("B", 0x7F)       # displayed skin parts: tất cả
        + pack_varint(1)               # main hand: phải
        + pack_bool(False)             # enable text filtering
        + pack_bool(True)              # allow server listings
        + pack_varint(0)               # particle status: all
    )
    conn.send_packet(0x00, client_info_payload)
    print("[+] Đã gửi Client Information.")

    # Client thật luôn tự gửi Plugin Message channel "minecraft:brand" để giới thiệu
    # tên client. Nhiều server (đặc biệt có plugin/anti-bot) chờ gói này mới cho qua
    # Configuration - thiếu bước này server có thể "treo" ở Keep Alive vô thời hạn.
    brand_payload = pack_string("minecraft:brand") + pack_string("vanilla")
    conn.send_packet(0x02, brand_payload)
    print("[+] Đã gửi Plugin Message (minecraft:brand).")

    state = "configuration"
    while state == "configuration":
        packet_id, payload = conn.read_packet()
        if DEBUG:
            print(f"[debug] (config) packet_id=0x{packet_id:02X} len={len(payload)}")

        if packet_id == 0x02:
            print("[-] Bị ngắt kết nối trong Configuration state.")
            return
        elif packet_id == 0x03:
            conn.send_packet(0x03, b"")  # Acknowledge Finish Configuration
            print("[+] Configuration hoàn tất, chuyển sang Play state.")
            state = "play"
        elif packet_id == 0x04:
            conn.send_packet(0x04, payload)  # Keep Alive echo
        elif packet_id == 0x0E:
            conn.send_packet(0x07, pack_varint(0))  # Known Packs rỗng
        else:
            pass

    # ---- Play state ----
    print("[+] Đã vào Play state. Giữ kết nối để duy trì trạng thái online...")
    raw_sock.settimeout(30)

    while True:
        try:
            packet_id, payload = conn.read_packet()
            if DEBUG:
                print(f"[debug] (play) packet_id=0x{packet_id:02X} len={len(payload)}")

            if packet_id == 0x2C and len(payload) == 8:
                conn.send_packet(0x1A, payload)
                print("[i] Đã phản hồi Keep Alive.")

        except socket.timeout:
            print("[i] Không có gói tin mới, vẫn giữ kết nối...")
            continue
        except (ConnectionError, OSError) as e:
            print(f"[-] Mất kết nối: {e}")
            break


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Cách dùng: python mc_afk_bot.py <host> <port> <username> [protocol_version]")
        sys.exit(1)

    host_arg = sys.argv[1]
    port_arg = int(sys.argv[2])
    username_arg = sys.argv[3]
    protocol_arg = int(sys.argv[4]) if len(sys.argv) > 4 else 775

    connect_and_join(host_arg, port_arg, username_arg, protocol_arg)
