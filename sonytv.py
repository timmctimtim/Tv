#!/usr/bin/env python3
"""
sonytv - control a Sony Bravia TV over your local network.

Uses Sony's documented IP Control interfaces:
  * REST/JSON API  (http://<tv-ip>/sony/<service>)   - state + actions
  * IRCC-IP        (http://<tv-ip>/sony/IRCC)         - "remote button" presses

Authentication is via a Pre-Shared Key (PSK) that you set on the TV under
  Settings -> Network -> Home network setup -> IP control -> Authentication
  (set to "Normal and Pre-Shared Key", then set the key).

No third-party packages required - standard library only.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

TIMEOUT = 5


class TVError(Exception):
    pass


def _tv_ip(args):
    ip = args.ip or os.environ.get("SONY_TV_IP")
    if not ip:
        raise TVError("No TV IP. Pass --ip or set SONY_TV_IP.")
    return ip


def _psk(args):
    return args.psk or os.environ.get("SONY_TV_PSK", "")


def _post(ip, psk, service, method, params=None, version="1.0"):
    """Call a REST/JSON-RPC method on the TV."""
    url = f"http://{ip}/sony/{service}"
    body = json.dumps(
        {"method": method, "params": params or [], "id": 1, "version": version}
    ).encode()
    headers = {"Content-Type": "application/json"}
    if psk:
        headers["X-Auth-PSK"] = psk
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise TVError(f"HTTP {e.code} from {url}: {e.read().decode(errors='replace')}")
    except urllib.error.URLError as e:
        raise TVError(f"Cannot reach TV at {ip}: {e.reason}")
    if "error" in data:
        raise TVError(f"TV error on {service}.{method}: {data['error']}")
    return data.get("result", data.get("results"))


def _ircc(ip, psk, code):
    """Send an IRCC-IP (remote button) command via SOAP."""
    url = f"http://{ip}/sony/IRCC"
    envelope = (
        '<?xml version="1.0"?>'
        '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
        's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
        "<s:Body>"
        '<u:X_SendIRCC xmlns:u="urn:schemas-sony-com:service:IRCC:1">'
        f"<IRCCCode>{code}</IRCCCode>"
        "</u:X_SendIRCC></s:Body></s:Envelope>"
    ).encode()
    headers = {
        "Content-Type": 'text/xml; charset="utf-8"',
        "SOAPACTION": '"urn:schemas-sony-com:service:IRCC:1#X_SendIRCC"',
    }
    if psk:
        headers["X-Auth-PSK"] = psk
    req = urllib.request.Request(url, data=envelope, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        raise TVError(f"HTTP {e.code} sending IRCC: {e.read().decode(errors='replace')}")
    except urllib.error.URLError as e:
        raise TVError(f"Cannot reach TV at {ip}: {e.reason}")


def remote_codes(ip, psk):
    """Map of remote-button name -> IRCC code, read from the TV itself."""
    res = _post(ip, psk, "system", "getRemoteControllerInfo")
    # res is [meta, [ {name, value}, ... ]]
    buttons = res[1] if isinstance(res, list) and len(res) > 1 else res
    return {b["name"]: b["value"] for b in buttons}


# ---- command handlers -------------------------------------------------------

def cmd_info(args):
    ip, psk = _tv_ip(args), _psk(args)
    out = {}
    out["system"] = _post(ip, psk, "system", "getSystemInformation")[0]
    try:
        out["power"] = _post(ip, psk, "system", "getPowerStatus")[0]
    except TVError:
        pass
    print(json.dumps(out, indent=2))


def cmd_power(args):
    ip, psk = _tv_ip(args), _psk(args)
    on = args.state == "on"
    _post(ip, psk, "system", "setPowerStatus", [{"status": on}])
    print(f"Power {'on' if on else 'off'}")


def cmd_volume(args):
    ip, psk = _tv_ip(args), _psk(args)
    # Relative (+5 / -5) or absolute (50)
    val = args.level
    _post(ip, psk, "audio", "setAudioVolume",
          [{"target": "speaker", "volume": val}], version="1.0")
    print(f"Volume set to {val}")


def cmd_mute(args):
    ip, psk = _tv_ip(args), _psk(args)
    status = args.state == "on"
    _post(ip, psk, "audio", "setAudioMute", [{"status": status}])
    print(f"Mute {'on' if status else 'off'}")


def cmd_inputs(args):
    ip, psk = _tv_ip(args), _psk(args)
    res = _post(ip, psk, "avContent", "getCurrentExternalInputsStatus", version="1.1")
    rows = res[0] if res else []
    for r in rows:
        label = r.get("label") or r.get("title") or ""
        print(f"{r.get('uri','?'):40} {r.get('title',''):12} {label}")


def cmd_set_input(args):
    ip, psk = _tv_ip(args), _psk(args)
    _post(ip, psk, "avContent", "setPlayContent", [{"uri": args.uri}])
    print(f"Switched to {args.uri}")


def cmd_apps(args):
    ip, psk = _tv_ip(args), _psk(args)
    res = _post(ip, psk, "appControl", "getApplicationList")
    for a in (res[0] if res else []):
        print(f"{a.get('uri','?'):60} {a.get('title','')}")


def cmd_launch(args):
    ip, psk = _tv_ip(args), _psk(args)
    _post(ip, psk, "appControl", "setActiveApp", [{"uri": args.uri}])
    print(f"Launched {args.uri}")


def cmd_keys(args):
    ip, psk = _tv_ip(args), _psk(args)
    for name in sorted(remote_codes(ip, psk)):
        print(name)


def cmd_key(args):
    ip, psk = _tv_ip(args), _psk(args)
    codes = remote_codes(ip, psk)
    sent = []
    for name in args.names:
        if name not in codes:
            raise TVError(f"Unknown key '{name}'. Run 'sonytv keys' to list them.")
        _ircc(ip, psk, codes[name])
        sent.append(name)
    print("Sent: " + " ".join(sent))


def build_parser():
    p = argparse.ArgumentParser(prog="sonytv", description="Control a Sony Bravia TV.")
    p.add_argument("--ip", help="TV IP address (or set SONY_TV_IP)")
    p.add_argument("--psk", help="Pre-Shared Key (or set SONY_TV_PSK)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("info", help="Show system + power info").set_defaults(func=cmd_info)

    sp = sub.add_parser("power", help="Turn TV on/off")
    sp.add_argument("state", choices=["on", "off"])
    sp.set_defaults(func=cmd_power)

    sp = sub.add_parser("volume", help="Set volume (0-100, or +5 / -5)")
    sp.add_argument("level")
    sp.set_defaults(func=cmd_volume)

    sp = sub.add_parser("mute", help="Mute on/off")
    sp.add_argument("state", choices=["on", "off"])
    sp.set_defaults(func=cmd_mute)

    sub.add_parser("inputs", help="List external inputs (HDMI etc.)").set_defaults(func=cmd_inputs)

    sp = sub.add_parser("set-input", help="Switch to an input URI (see 'inputs')")
    sp.add_argument("uri")
    sp.set_defaults(func=cmd_set_input)

    sub.add_parser("apps", help="List installed apps").set_defaults(func=cmd_apps)

    sp = sub.add_parser("launch", help="Launch an app URI (see 'apps')")
    sp.add_argument("uri")
    sp.set_defaults(func=cmd_launch)

    sub.add_parser("keys", help="List available remote-button names").set_defaults(func=cmd_keys)

    sp = sub.add_parser("key", help="Send one or more remote buttons")
    sp.add_argument("names", nargs="+", help="e.g. VolumeUp Home Up Up Confirm")
    sp.set_defaults(func=cmd_key)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except TVError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
