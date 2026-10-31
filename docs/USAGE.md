# Using podhop — the practical guide

This is the "how do I actually live with this" document. Command flags are in
the README; this is about what to do and what to expect.

## The mental model

AirPods hold **one** Bluetooth connection at a time. Whoever holds it, owns
the audio:

- **podhop pulls them to Linux.** When you start using your Linux machine
  (or run `podhop switch` manually), the AirPods leave whatever they're on
  and come to you.
- **Your iPhone/Mac takes them back natively.** Start using your iPhone and
  Apple's own auto-switching grabs them from Linux — you don't need podhop
  for the trip back (as long as *Settings → Bluetooth → AirPods → Connect to
  This iPhone* is set to **Automatically**).

So the daily loop is: use Linux → they're on Linux. Pick up the phone →
they're on the phone. That's the whole experience.

## Before you start (one time)

1. **A Linux machine with Bluetooth** (BlueZ 5.50+) and your AirPods
   **paired to it**. Pairing is the normal flow:

   ```
   bluetoothctl scan on        # find your AirPods' address
   bluetoothctl pair XX:XX:XX:XX:XX:XX
   bluetoothctl trust XX:XX:XX:XX:XX:XX
   ```

   When pairing, the AirPods must be in **pairing mode**: put them in the
   case, open the lid, press and hold the button on the back until the light
   flashes **white**.

2. **Save your AirPods** so you don't type the address again:

   ```
   sudo python3 podhop.py discover
   ```

3. That's it. Nothing to install, no accounts, no cloud.

## The physical rules (read this once, save yourself the confusion)

- **The case lid must be open, or the buds must be in your ears.** Closed
  case = the AirPods are asleep and will ignore connection attempts from
  *any* device — Apple's included. This is the #1 reason a switch silently
  fails.
- **They must be in range** of the Linux machine's Bluetooth — same room is
  a safe bet.
- **One owner at a time.** If they're currently on your iPhone, a switch
  takes them from the iPhone; the iPhone will notice and let go.

## Daily use

**Bring them to Linux:**

```
sudo python3 podhop.py switch
```

Works when they're in your ears, sitting in the open case next to you, or on
another Apple device. You'll see the handshake complete and the link move.

**Let them go:**

```
sudo python3 podhop.py release
```

…or just pick up your iPhone — Apple's auto-switch handles it.

**Check what's happening:**

```
sudo python3 podhop.py status
```

## What a working switch looks like

```
[*] paging AA:BB:CC:DD:EE:FF on L2CAP PSM 0x1001 (AAP takeover)...
[+] AAP handshake OK: 01000400000001000300...
[+] host table received (323B) — session is live
[+] switch complete — holding AAP channel open
```

Then (on a machine with audio) Bluetooth audio routes normally — play
something and it comes out of the AirPods.

## Optional: the keys

```
sudo python3 podhop.py keys
```

Asks your AirPods for their "magic cloud keys" (the shared secret Apple
devices use to recognize each other). You'll need this for the upcoming
presence/ear-detection features. Treat the output as a secret — it
identifies *your* AirPods' cluster. Extraction works only over your own
paired link and never touches Apple's servers.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `Host is down` / nothing happens | Case is **closed**, or they're out of range. Open the lid or wear them. |
| `Failed to connect` on a fresh boot | Run `bluetoothctl connect <addr>` once, or re-run `switch` — some adapters need a nudge. |
| Permission errors | Use `sudo`, or give the binary `CAP_NET_RAW` (`setcap 'cap_net_raw+ep' $(which python3)`). |
| They connect then drop immediately | Something else grabbed them back — an Apple device with audio active wins. Stop the audio there, switch again. |
| Switch works but no audio | Your BlueZ needs an audio backend (PipeWire/PulseAudio with bluez plugins). `podhop` moves the link; your distro's audio stack handles sound. |
| `Pairing failed: InProgress` | A previous pairing attempt wedged. `sudo systemctl restart bluetooth` and retry once. |

## What we're still working on

Fully automatic switching (no manual command) via watching your audio
server, battery/ear-detection overlays, and the AirPods-initiated flow — see
the README roadmap. If you get podhop working on a new adapter, AirPods
model, or distro, open an Issue with your setup — that's the data that makes
v1.0 trustworthy for everyone.
