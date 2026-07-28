# GhostJoin

A minimal Minecraft (Java Edition) protocol client written in pure Python
(standard library only: `socket`, `struct`, `hashlib`, `zlib`) — connects to
a server, walks through the full Handshake → Login → Configuration → Play
flow, and keeps the connection alive by responding to Keep Alive packets.

## Purpose

This repo was built to **test the anti-bot system of a Minecraft server you
own, or a server whose owner has explicitly authorized this kind of
testing**. It simulates a client connection at the protocol level (no
rendering, physics, or in-game interaction logic) — useful for checking
whether a server's anti-bot system can detect and block this kind of "bare"
connection.

During development, this script was actually blocked by a real server right
at the last step of the Configuration state (the server just kept looping
Keep Alive packets and never sent Finish Configuration) — a real-world
example of an anti-bot system flagging a "suspicious" connection and leaving
it in limbo instead of rejecting it outright. Documented here as a reference
for your own testing.

## Limitations

- **Only works with offline-mode servers** (`online-mode=false`). Servers
  with Mojang/Microsoft authentication enabled require an Encryption Request
  + valid session token, which is outside the scope of this script.
- Minecraft Protocol packet IDs change fairly often between versions. The
  IDs in this script are based on protocol ~773–776 (close to version 26.1.2
  at the time of writing). Set `DEBUG = True` in the file to print every
  received packet ID and cross-check it against
  [minecraft.wiki/w/Java_Edition_protocol/Packets](https://minecraft.wiki/w/Java_Edition_protocol/Packets)
  if your server runs a different version.
- No render/physics/interaction logic — the client just "stands still" once
  in the Play state. If you need to simulate movement/actions for deeper
  testing, you'll need to extend it yourself.

## Usage

```bash
python ghostjoin.py <host> <port> <username> [protocol_version]
```

Example:

```bash
python ghostjoin.py 127.0.0.1 25565 TestBot 775
```

## Responsible use

- Only run this against your own server, or a server whose owner has
  **explicitly agreed** to this kind of testing.
- Do not use it to spin up large numbers of fake connections to overload a
  server (DoS), manipulate publicly displayed player counts, or bypass
  protections you don't have permission to bypass.
- If a server's anti-bot system successfully blocks this script — that's the
  intended test outcome, not a bug to be "patched around" at all costs.

## License

See the [LICENSE](./LICENSE) file. Free to use, copy, modify, and
redistribute; the software is provided "as is" — the authors take no
responsibility for any consequences arising from its use or misuse.
