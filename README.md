# sonytv

A small, dependency-free command-line tool to control your own **Sony Bravia TV**
over your home/office network, using Sony's documented IP Control interfaces
(the same ones Sony's own apps and home-automation integrations use).

No "hacking" required and nothing unofficial — you just turn on IP Control on the
TV and talk to it over HTTP.

## 1. Turn on IP Control on the TV

On the TV:

1. **Settings → Network → Home network → IP control** (wording varies by model/year).
2. Set **Authentication** to **Normal and Pre-Shared Key**.
3. Set a **Pre-Shared Key** (PSK) — any string you choose, e.g. `0000`.
4. Enable **Simple IP Control** if your model lists it separately.
5. Note the TV's IP address under **Settings → Network → Network status**.

(Older models use a PIN-pairing flow instead of a PSK. If yours has no PSK
option, tell me and I'll add PIN pairing.)

## 2. Point the tool at your TV

```bash
export SONY_TV_IP=192.168.1.50      # your TV's IP
export SONY_TV_PSK=0000             # the key you set
```

...or pass `--ip` / `--psk` on each command.

## 3. Use it

```bash
python3 sonytv.py info                 # system + power status
python3 sonytv.py power on             # or: power off
python3 sonytv.py volume 25            # absolute; or relative: volume +5
python3 sonytv.py mute on
python3 sonytv.py inputs               # list HDMI / external inputs
python3 sonytv.py set-input "extInput:hdmi?port=2"
python3 sonytv.py apps                 # list installed apps
python3 sonytv.py launch "<app-uri-from-apps>"
python3 sonytv.py keys                 # list every remote button the TV supports
python3 sonytv.py key Home Up Up Confirm   # send a sequence of remote presses
```

### Handy

Make it a shortcut:

```bash
chmod +x sonytv.py
alias tv='python3 /home/user/Tv/sonytv.py'
tv power on && tv set-input "extInput:hdmi?port=1"
```

## Notes

- Works over the local network only (the TV and your computer on the same LAN).
- `keys` / `key` read the exact IRCC codes from the TV itself, so they match your model.
- If a command returns an auth error, re-check the PSK and that IP Control is enabled.
