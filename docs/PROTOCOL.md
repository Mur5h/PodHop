# AAP / MagicPairing Protocol Notes

Reverse-engineered 2026-10-31 from live captures: Raspberry Pi Zero 2 W
(BlueZ L2CAP), PacketLogger HCI captures on macOS 27.2, and BLE advertisement
decoding. Builds on OpenPods, furiousMAC/continuity, LibrePods, tylie's
AAP-Protocol-Defintion, and the TU Darmstadt MagicPairing paper
(arXiv:2005.07255).

## Transport

- Classic Bluetooth L2CAP, **PSM 0x1001**. Both sides can listen; Apple hosts
  run a server here and the AirPods connect to the host they pick.
- SDP service UUID: `74ec2172-0bad-4d01-8f77-997b2be0722a`
- Frame: `[msg_type][0x00][service_id][body]`
  - `0x00` connect → body: major(2) minor(2) features
  - `0x01` connect_response → status(2) major(2) minor(2)
  - `0x04` command → cmd(2, LE) + body
- Handshake (mandatory, sent first):
  `00 00 04 00 01 00 02 00 00 00 00 00 00 00 00 00`
  → response `01 00 04 00 00 00 01 00 03 00 ...` (status 0000 = ok)

## Command map (service 0x04)

| cmd | direction | meaning |
|-----|-----------|---------|
| 0x01 | host→AP | connection state (0x08 = active) |
| 0x04 | AP→host | battery (n, [component level status]×n; L=04 R=02 case=08) |
| 0x06 | AP→host | state change notification |
| 0x08 | AP→host | ? (seen right after 0x2E) |
| 0x09 | both | sub-feature state (subs: 0x06, 0x0d, 0x1a, 0x32, 0x34, 0x3c, 0x3d) |
| 0x0C | AP→host | host address echo (`[addr6][01][02]`) |
| 0x0D | host→AP | trigger state dump |
| 0x0E | AP→host | connected-host address echo |
| 0x0F | host→AP | enable notifications (payload `ffffffff`) |
| 0x17 | both | version/capability blobs (HID report descriptors embedded) |
| 0x1B | host→AP | time sync (ISO-8601 string, e.g. `2026-10-31T17:41:56-04:00`) |
| 0x1D | AP→host | device metadata (name, model A30XX, "Apple Inc.", serials) |
| 0x23 | AP→host | extended config |
| 0x24 | host→AP | session flags |
| 0x29 | host→AP | feature mask (`00 ffffffffffffff`) |
| 0x2B | AP→host | **host table dump**: `[00000000][addr6][type+flags][4B LE ts]` per host |
| 0x2D | host→AP | get known hosts → response cmd 0x2E |
| 0x2E | AP→host | known hosts: `[count][0x02][04 <addr5?>][00][01 <addr6>][NN]` (NN increments) |
| 0x30 | host→AP | request magic cloud keys (payload `0500`) |
| 0x31 | AP→host | magic cloud keys: `02 0100 1000 <key16> 0400 1000 <key16>` |
| 0x44 | host→AP | timing/state with timestamp |
| 0x4F | both | metadata query TLVs (serial, firmware "3.36.32", MTIC, names) |
| 0x53 | AP→host | large encrypted/structured state blob |
| 0x54 | host→AP | notification subscription list |
| 0x55 | AP→host | ? (1 0100 19) |
| 0x63 | both | ? |

Response opcode = request opcode + 1 (0x2D→0x2E, 0x30→0x31). Sending
response-direction opcodes (0x31, 0x3B, 0x3D, 0x3F) to the AirPods wedges
the channel briefly.

### Host table entry types (cmd 0x2B)

Apple hosts that run AAP sessions accumulate type-`0b` entries; simple
paired hosts get `0a`/`02`/`03`. The AirPods maintain per-host timestamps.

## Magic cloud keys

Request: `04 00 04 00 30 00 05 00` → response contains two 16-byte keys
(verified stable across re-pairings; accKey is per-AirPods, not per-link):

```
040004003100020100 1000 <keyA 16B> 0400 1000 <keyB 16B = accKey>
```

The accKey decrypts the **unencrypted-header proximity advertisements**
(0x07 messages, AES-ECB on the trailing 16 bytes). Verified: phone and Mac
broadcast near-identical plaintexts for the same AirPods.

**Not observed on the wire during normal connections**: the raw keys are
never sent host↔AirPods after initial distribution; the cloud-keys exchange
fires at pairing/key-rotation time.

## BLE proximity advertisements (type 0x07)

```
07 19 01 <model:2> <status> <battL:4b><battR:4b> <charge+case> <lid> <color> <suffix> <encrypted 16B>
```

Current firmware **rotates the encrypted section every few seconds**
(anti-tracking). The static, replayable-era format documented by furiousMAC
in 2020 is gone on 9A348 firmware.

## Undocumented advertisement types observed

- **0x0A** — appears only around switch events. Two TLV variants:
  `0a 04 13ecda65` / `0a 01 80` followed by `16 08 <8B>`. The 3-byte values
  inside are per-connection derived (not reproducible from the static
  accKey — tested ECB/CMAC/HMAC families).
- **0x12** (`1202 <2B>` and wrappers carrying nested `0711 06 <16B>`),
  **0x16**, **0x18** (`1202`-family), **0x22** — unknown, widely broadcast.

## Switching flow (observed)

1. AirPods keep one classic link; they **initiate** the AAP connection to
   the host they choose (hosts listen on 0x1001).
2. Hosts can also **page** the AirPods: a raw L2CAP connect on 0x1001 from a
   paired host takes the AirPods off the current host (verified: Pi took
   them from a MacBook mid-session). The AAP handshake must complete and a
   channel must stay open, or the link drops.
3. Apple devices send the connect-sequence: 0x0D, 0x29, 0x54, 0x01(08),
   0x24, 0x1B(time), 0x0F, 0x4F metadata reads, 0x44, 0x2D, 0x09 substates.
4. No magic-pairing material crosses the wire during normal operation.

## Security observations

- The AAP channel requires an authenticated (paired) link; unauthenticated
  L2CAP connects are refused. Key extraction requires the user's pairing
  gesture (pairing mode) — tested and confirmed.
- The raw accKey never appears on any HCI capture during normal use.
