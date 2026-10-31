#!/usr/bin/env python3
"""podhop — AirPods quick-switching for Linux.

Commands:
  discover            find paired AirPods and save them to ~/.config/podhop.json
  switch [addr]       pull the AirPods to this machine (AAP takeover, holds link)
  release [addr]      drop the link and let other devices take them back
  keys [addr]         extract the magic cloud keys (accKey) over the AAP channel
  status [addr]       show pairing/link state

Requires: BlueZ, AirPods already paired to this machine (bluetoothctl pair).
L2CAP operations may need root (sudo) or CAP_NET_RAW depending on BlueZ.
"""
import json
import os
import socket
import sys
import time

PSM = 0x1001
HANDSHAKE = bytes.fromhex("00000400010002000000000000000000")
REQ_MAGIC_KEYS = bytes.fromhex("0400040030000500")
CONFIG = os.path.expanduser("~/.config/podhop.json")


def load_addr(arg):
    if arg:
        return arg.upper()
    if os.path.exists(CONFIG):
        cfg = json.load(open(CONFIG))
        if cfg.get("addr"):
            return cfg["addr"]
    print("no address given and none saved — run: podhop discover")
    sys.exit(1)


def save_addr(addr, name=""):
    os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
    json.dump({"addr": addr, "name": name}, open(CONFIG, "w"))
    print(f"saved {addr} ({name}) to {CONFIG}")


def l2cap_session(addr):
    """Open the AAP channel, do the handshake, return the socket."""
    s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
    s.settimeout(12)
    s.connect((addr, PSM))
    s.sendall(HANDSHAKE)
    time.sleep(0.4)
    resp = s.recv(64)
    if not resp or resp[0] != 0x01:
        s.close()
        raise RuntimeError(f"AAP handshake failed: {resp.hex() if resp else 'no response'}")
    return s, resp


def btctl_devices():
    import subprocess
    out = subprocess.run(["bluetoothctl", "devices"], capture_output=True, text=True).stdout
    devs = []
    for line in out.splitlines():
        parts = line.split(maxsplit=2)
        if len(parts) >= 3:
            devs.append((parts[1], parts[2]))
    return devs


def cmd_discover():
    print("paired devices (from bluetoothctl):")
    for addr, name in btctl_devices():
        mark = "  <-- AirPods?" if "airpods" in name.lower() or "beats" in name.lower() else ""
        print(f"  {addr}  {name}{mark}")
    choice = input("enter address to save (blank to skip): ").strip()
    if choice:
        name = next((n for a, n in btctl_devices() if a.upper() == choice.upper()), "")
        save_addr(choice.upper(), name)


def cmd_switch(addr):
    print(f"[*] paging {addr} on L2CAP PSM 0x{PSM:04X} (AAP takeover)...")
    s, resp = l2cap_session(addr)
    print(f"[+] AAP handshake OK: {resp.hex()}")
    hold = int(os.environ.get("PODHOP_HOLD", "300"))
    print(f"[+] link is on this host — holding session for {hold}s (Ctrl+C to release early)")
    try:
        end = time.time() + hold
        while time.time() < end:
            s.settimeout(1.0)
            try:
                d = s.recv(1024)
                if not d:
                    print("[!] channel closed by AirPods")
                    break
            except socket.timeout:
                pass
    except KeyboardInterrupt:
        pass
    finally:
        s.close()
    print("[+] done — the ACL drops when the last channel closes (or A2DP takes over on audio hosts)")


def cmd_release(addr):
    import subprocess
    print(f"[*] releasing {addr}...")
    try:
        s, _ = l2cap_session(addr)
        s.close()
    except OSError:
        pass
    subprocess.run(["bluetoothctl", "disconnect", addr], capture_output=True)
    print("[+] released — other devices can take them now")


def cmd_keys(addr):
    print(f"[*] requesting magic cloud keys from {addr}...")
    s, resp = l2cap_session(addr)
    time.sleep(0.5)
    s.sendall(REQ_MAGIC_KEYS)
    s.settimeout(5)
    try:
        d = s.recv(1024)
        print(f"[*] response ({len(d)}B): {d.hex()}")
        if len(d) >= 8 and d[4:6] == b"\x31\x00":
            body = d[6:]
            i = body.find(b"\x10\x00")
            while i >= 0 and i + 2 + 16 <= len(body):
                print(f"  key: {body[i+2:i+18].hex()}")
                i = body.find(b"\x10\x00", i + 2)
            print("NOTE: treat these as secrets — they identify your AirPods' cluster.")
    except socket.timeout:
        print("[!] no response")
    s.close()


def cmd_status(addr):
    import subprocess
    out = subprocess.run(["bluetoothctl", "info", addr], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if any(k in line for k in ("Paired", "Trusted", "Connected", "Name:", "Battery")):
            print(line.strip())


COMMANDS = {"discover": cmd_discover, "switch": cmd_switch,
            "release": cmd_release, "keys": cmd_keys, "status": cmd_status}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(1)
    c = sys.argv[1]
    addr = sys.argv[2] if len(sys.argv) > 2 else None
    if c != "discover" and not addr:
        addr = load_addr(None)
    COMMANDS[c](addr)
