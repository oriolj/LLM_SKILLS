#!/usr/bin/env python3
"""Raw UniFi API client for agents — one call per invocation, JSON out.

    unifi_api.py METHOD LAYER PATH [JSON_BODY] [--site default] [--env FILE]

LAYER selects the prefix behind the UniFi OS proxy:
    os           https://<console>/api/<path>
    integration  https://<console>/proxy/network/integration/v1/<path>
    classic      https://<console>/proxy/network/api/s/<site>/<path>
    v2           https://<console>/proxy/network/v2/api/site/<site>/<path>

Credentials: UNIFI_URL and UNIFI_API_KEY from the environment, else from
--env FILE (default: hq's homelab/secrets/unifi.env). The key is sent as
X-API-KEY and never printed. Self-signed certificate: verification off.

Examples:
    unifi_api.py GET os system                       # console facts, works unauthenticated
    unifi_api.py GET integration sites
    unifi_api.py GET classic rest/networkconf
    unifi_api.py GET classic rest/user | jq '.[] | select(.use_fixedip)'
    unifi_api.py PUT classic rest/user/<_id> '{"use_fixedip":true,"fixed_ip":"192.168.7.229","network_id":"<id>"}'
    unifi_api.py POST v2 static-dns '{"record_type":"A","key":"hass.localdomain","value":"192.168.7.105","enabled":true}'
"""
from __future__ import annotations
import argparse, json, os, sys, urllib.request, ssl

DEFAULT_ENV = os.path.expanduser("~/Syncthing/Syncthing-mobile-docs/hq/homelab/secrets/unifi.env")


def load_env(path: str) -> dict:
    out = {}
    try:
        for line in open(path):
            if "=" in line and not line.startswith("#"):
                k, v = line.rstrip("\n").split("=", 1)
                out[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("method", choices=["GET", "POST", "PUT", "PATCH", "DELETE"])
    ap.add_argument("layer", choices=["os", "integration", "classic", "v2"])
    ap.add_argument("path")
    ap.add_argument("body", nargs="?", help="JSON body")
    ap.add_argument("--site", default="default")
    ap.add_argument("--env", default=DEFAULT_ENV)
    a = ap.parse_args()

    env = {**load_env(a.env), **{k: v for k, v in os.environ.items() if k.startswith("UNIFI_")}}
    base = env.get("UNIFI_URL", "").rstrip("/")
    key = env.get("UNIFI_API_KEY", "")
    if not base:
        sys.exit("UNIFI_URL missing (env or --env file)")
    prefix = {
        "os": f"{base}/api/",
        "integration": f"{base}/proxy/network/integration/v1/",
        "classic": f"{base}/proxy/network/api/s/{a.site}/",
        "v2": f"{base}/proxy/network/v2/api/site/{a.site}/",
    }[a.layer]
    url = prefix + a.path.lstrip("/")

    data = a.body.encode() if a.body else None
    req = urllib.request.Request(url, data=data, method=a.method)
    req.add_header("Accept", "application/json")
    if data:
        req.add_header("Content-Type", "application/json")
    if key:
        req.add_header("X-API-KEY", key)
    ctx = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
            raw = r.read()
            status = r.status
    except urllib.error.HTTPError as e:
        raw = e.read()
        status = e.code
    text = raw.decode(errors="replace")
    try:
        obj = json.loads(text)
        # classic responses wrap the payload in {"meta":{"rc":"ok"},"data":[...]}
        if isinstance(obj, dict) and "meta" in obj and "data" in obj:
            if obj["meta"].get("rc") != "ok":
                print(json.dumps(obj["meta"]), file=sys.stderr)
            obj = obj["data"]
        print(json.dumps(obj, indent=1))
    except json.JSONDecodeError:
        print(text[:2000])
    if status >= 400:
        print(f"HTTP {status}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
