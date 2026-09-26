#!/usr/bin/env python3
"""wa.py — agent CLI for a local WAHA (WhatsApp HTTP API) instance.

Stdlib only. Reads the key from $WAHA_API_KEY or ~/.config/waha/env and the
base URL from $WAHA_URL (default http://localhost:3010).

  wa.py status                         session state + linked account
  wa.py qr [--out FILE]                save the pairing QR (PNG)
  wa.py find QUERY                     contacts + groups matching a name/number
  wa.py chats [--limit N]              recent chats, newest first
  wa.py read CHAT [--limit N]          last messages of a chat (oldest first)
  wa.py send TO TEXT|@file [--persona petra] [--yes]
                                       dry run unless --yes; TEXT must name the persona
  wa.py media CHAT MSG_ID [--out DIR]  download a message's attachment
  wa.py transcribe CHAT [--id MSG_ID | --last N]
                                       voice notes -> text via oj-transcribe (local whisper)

CHAT / TO accept a chat id (…@c.us, …@g.us, …@lid) or a bare phone number in
international format without '+' (34600111222), resolved through check-exists.
"""
import argparse, base64, json, os, re, shutil, subprocess, sys, time, unicodedata
import urllib.error, urllib.parse, urllib.request
from pathlib import Path

URL = os.environ.get("WAHA_URL", "http://localhost:3010").rstrip("/")
SESSION = os.environ.get("WAHA_SESSION", "default")
DATA = Path.home() / ".local/share/waha"
SENT_LOG = DATA / "sent.jsonl"
PERSONAS = {"petra": "Petra", "emma": "Emma", "blake": "Blake"}


def api_key():
    k = os.environ.get("WAHA_API_KEY")
    if k:
        return k
    env = Path.home() / ".config/waha/env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("WAHA_API_KEY="):
                return line.split("=", 1)[1].strip()
    sys.exit("no WAHA_API_KEY (env var or ~/.config/waha/env)")


def call(method, path, params=None, body=None, raw=False, accept="application/json"):
    url = URL + path + ("?" + urllib.parse.urlencode(params, doseq=True) if params else "")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "X-Api-Key": api_key(), "Accept": accept, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            out = r.read()
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} {method} {path}: {e.read().decode(errors='replace')[:500]}")
    if raw:
        return out
    return json.loads(out) if out else None


def fold(s):
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def resolve(chat):
    if "@" in chat:
        return chat
    phone = re.sub(r"\D", "", chat)
    r = call("GET", "/api/contacts/check-exists", {"phone": phone, "session": SESSION})
    if not r.get("numberExists"):
        sys.exit(f"{phone} is not on WhatsApp")
    return r["chatId"]


def cmd_status(a):
    s = call("GET", f"/api/sessions/{SESSION}")
    print(f"session {s['name']}: {s['status']}  engine={s.get('engine', {}).get('engine')}")
    if s.get("me"):
        print(f"linked account: {s['me'].get('pushName')} {s['me'].get('id')}")
    print("server:", json.dumps(call("GET", "/api/server/version")))


def cmd_qr(a):
    png = call("GET", f"/api/{SESSION}/auth/qr", {"format": "image"}, raw=True, accept="image/png")
    out = Path(a.out or DATA / "qr.png")
    out.write_bytes(png)
    print(f"QR -> {out}  (phone: WhatsApp > Linked devices > Link a device; expires in ~60 s)")


def cmd_find(a):
    q = fold(a.query)
    digits = re.sub(r"\D", "", a.query)
    for c in call("GET", "/api/contacts/all", {"session": SESSION}) or []:
        names = " ".join(filter(None, [c.get("name"), c.get("pushname"), c.get("shortName")]))
        if q in fold(names) or (digits and digits in (c.get("number") or c.get("id", ""))):
            print(f"{c.get('id'):32} {names}  {'[mine]' if c.get('isMyContact') else ''}")
    for g in call("GET", f"/api/{SESSION}/groups") or []:
        name = g.get("name") or g.get("subject") or (g.get("groupMetadata") or {}).get("subject") or ""
        gid = g.get("id") if isinstance(g.get("id"), str) else (g.get("id") or {}).get("_serialized", "")
        if q in fold(name):
            print(f"{gid:32} [group] {name}")


def cmd_chats(a):
    for c in call("GET", f"/api/{SESSION}/chats/overview", {"limit": a.limit}):
        last = c.get("lastMessage") or {}
        ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(last.get("timestamp", 0))) if last else ""
        print(f"{ts:16} {c['id']:32} {c.get('name') or ''}  | {(last.get('body') or '')[:60]!r}")


def messages(chat, limit, media=False):
    return call("GET", f"/api/{SESSION}/chats/{urllib.parse.quote(chat)}/messages",
                {"limit": limit, "sortOrder": "desc", "downloadMedia": str(media).lower()})


def cmd_read(a):
    for m in reversed(messages(resolve(a.chat), a.limit)):
        ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(m.get("timestamp", 0)))
        who = "me" if m.get("fromMe") else (m.get("_data", {}).get("notifyName") or m.get("from"))
        kind = f" [{(m.get('media') or {}).get('mimetype') or m.get('type') or 'media'}]" if m.get("hasMedia") else ""
        print(f"{ts} {who}:{kind} {m.get('body') or ''}   ({m['id']})")


def cmd_send(a):
    chat = resolve(a.to)
    text = Path(a.text[1:]).read_text() if a.text.startswith("@") else a.text
    persona = PERSONAS[a.persona]
    if persona.lower() not in text.lower():
        sys.exit(f"refused: the message must identify the sender as {persona} "
                 f"(e.g. start with '{persona}, l'assistent de l'Oriol: …')")
    print(f"TO   {chat}\nTEXT {text}")
    if not a.yes:
        print("(dry run — add --yes to send)")
        return
    call("POST", "/api/startTyping", body={"chatId": chat, "session": SESSION})
    time.sleep(min(2 + len(text) / 40, 6))
    call("POST", "/api/stopTyping", body={"chatId": chat, "session": SESSION})
    r = call("POST", "/api/sendText", body={"chatId": chat, "text": text, "session": SESSION})
    mid = r.get("id") if isinstance(r.get("id"), str) else (r.get("id") or {}).get("_serialized") or r.get("key", {}).get("id")
    DATA.mkdir(parents=True, exist_ok=True)
    with SENT_LOG.open("a") as f:
        f.write(json.dumps({"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "chatId": chat,
                            "persona": persona, "text": text, "messageId": mid}, ensure_ascii=False) + "\n")
    print(f"sent, message id {mid}  (logged to {SENT_LOG})")


def download(m, outdir):
    media = m.get("media") or {}
    if not media.get("url"):
        sys.exit(f"message {m['id']} has no downloadable media ({media.get('error') or 'none'})")
    # the url carries WAHA_BASE_URL; fetch it through our own URL instead
    path = urllib.parse.urlparse(media["url"]).path
    blob = call("GET", path, raw=True, accept="*/*")
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / (media.get("filename") or Path(path).name)
    out.write_bytes(blob)
    return out


def find_msg(chat, mid, limit=200):
    for m in messages(chat, limit, media=True):
        if m["id"] == mid or m["id"].endswith(mid):
            return m
    sys.exit(f"message {mid} not in the last {limit} messages of {chat}")


def cmd_media(a):
    print(download(find_msg(resolve(a.chat), a.msg_id), Path(a.out or DATA / "downloads")))


def cmd_transcribe(a):
    chat = resolve(a.chat)
    if a.id:
        picked = [find_msg(chat, a.id)]
    else:
        voice = [m for m in messages(chat, 100, media=True)
                 if m.get("hasMedia") and ((m.get("media") or {}).get("mimetype") or "").startswith("audio")]
        picked = list(reversed(voice[: a.last]))
    if not picked:
        sys.exit("no voice notes found")
    tool = shutil.which("oj-transcribe") or sys.exit("oj-transcribe not on PATH")
    for m in picked:
        f = download(m, DATA / "downloads")
        ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(m.get("timestamp", 0)))
        print(f"\n=== {ts} {'me' if m.get('fromMe') else m.get('from')} ({m['id']})")
        subprocess.run([tool, "--stdout", str(f)], check=False)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)
    sp.add_parser("status").set_defaults(f=cmd_status)
    s = sp.add_parser("qr"); s.add_argument("--out"); s.set_defaults(f=cmd_qr)
    s = sp.add_parser("find"); s.add_argument("query"); s.set_defaults(f=cmd_find)
    s = sp.add_parser("chats"); s.add_argument("--limit", type=int, default=20); s.set_defaults(f=cmd_chats)
    s = sp.add_parser("read"); s.add_argument("chat"); s.add_argument("--limit", type=int, default=20); s.set_defaults(f=cmd_read)
    s = sp.add_parser("send"); s.add_argument("to"); s.add_argument("text")
    s.add_argument("--persona", choices=PERSONAS, default="petra"); s.add_argument("--yes", action="store_true")
    s.set_defaults(f=cmd_send)
    s = sp.add_parser("media"); s.add_argument("chat"); s.add_argument("msg_id"); s.add_argument("--out"); s.set_defaults(f=cmd_media)
    s = sp.add_parser("transcribe"); s.add_argument("chat"); s.add_argument("--id"); s.add_argument("--last", type=int, default=1)
    s.set_defaults(f=cmd_transcribe)
    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
