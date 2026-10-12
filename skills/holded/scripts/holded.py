#!/usr/bin/env python3
"""Read-only client for the Holded API v2, plus an offline reader of its OpenAPI spec.

GET only: this script cannot write to Holded. It never prints the token.

    holded.py --scope smartupsoft usage
    holded.py --scope smartupsoft accounts [--json]
    holded.py --scope smartupsoft movements <account-id> --from 2026-07-01 --to 2026-09-30 [--status pending]
    holded.py --scope smartupsoft get /api/v2/purchases start_date=2026-07-01 end_date=2026-09-30 [--all]
        (without --all: the {items, cursor, has_more} envelope of one page; with --all: a bare list of every item)
    holded.py spec                      # tags with their endpoint counts (no token, no quota)
    holded.py spec --tag "Banking accounts"
    holded.py spec --path /api/v2/payments [--method post]

The token is read from HOLDED_API_TOKEN, or from the secrets file of the scope:
<hq>/homelab/secrets/holded-<scope>.env, key HOLDED_<SCOPE>_API_TOKEN (parsed as data, never sourced).
Every call counts against the Holded account's monthly quota: run `usage` before a batch.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal
from pathlib import Path

BASE = "https://api.holded.com"
SPEC_URL = "https://api.holded.com/openapi/api2.json"
SPEC_CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "holded" / "api2.json"
HQ = Path(os.environ.get("HQ_DIR", Path.home() / "Syncthing/Syncthing-mobile-docs/hq"))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"


def money(value) -> Decimal | None:
    """Holded money strings: documents use a comma ("62,87"), bank movements a dot ("-62.87")."""
    if value in (None, ""):
        return None
    text = str(value).strip()
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    return Decimal(text)


def load_token(scope: str | None) -> str:
    token = os.environ.get("HOLDED_API_TOKEN")
    if token:
        return token.strip()
    if not scope:
        sys.exit("error: pass --scope <name> or set HOLDED_API_TOKEN")
    path = HQ / "homelab" / "secrets" / f"holded-{scope}.env"
    key = f"HOLDED_{scope.upper().replace('-', '_')}_API_TOKEN="
    if not path.exists():
        sys.exit(f"error: {path} not found (not decrypted on this machine, or no v2 token for this scope)")
    for line in path.read_text().splitlines():
        if line.startswith(key):
            return line.split("=", 1)[1].strip().strip("'\"")
    sys.exit(f"error: {key[:-1]} not in {path}")


class Holded:
    def __init__(self, token: str):
        self._token = token
        self.calls = 0

    def get(self, path: str, **params):
        """One GET. Returns (status, parsed body). Waits and retries once on 429 when Retry-After is short."""
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None}, doseq=True)
        url = BASE + path + ("?" + query if query else "")
        for attempt in (1, 2):
            req = urllib.request.Request(url, headers={
                "Authorization": "Bearer " + self._token, "Accept": "application/json", "User-Agent": UA})
            self.calls += 1
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return resp.status, json.loads(resp.read() or b"null")
            except urllib.error.HTTPError as err:
                body = err.read().decode("utf8", "replace").replace(self._token, "<token>")
                wait = err.headers.get("Retry-After", "")
                window = err.headers.get("X-RateLimit-Window", "")
                if err.code == 429 and attempt == 1 and window != "month" and wait.isdigit() and int(wait) <= 90:
                    time.sleep(int(wait) + 1)
                    continue
                try:
                    return err.code, json.loads(body)
                except ValueError:
                    return err.code, body[:500]
        return None, None

    def items(self, path: str, max_pages: int = 50, **params) -> list:
        """Every item of a cursor-paginated list. Stops on an error and reports it on stderr."""
        out, cursor = [], None
        for _ in range(max_pages):
            status, body = self.get(path, cursor=cursor, **params)
            if status != 200 or not isinstance(body, dict):
                print(f"error: {path} answered {status}: {body}", file=sys.stderr)
                break
            out += body.get("items", [])
            cursor = body.get("cursor")
            if not body.get("has_more") or not cursor:
                break
            time.sleep(0.6)
        return out


def load_spec(refresh: bool = False) -> dict:
    if refresh or not SPEC_CACHE.exists() or time.time() - SPEC_CACHE.stat().st_mtime > 7 * 86400:
        SPEC_CACHE.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(SPEC_URL, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=120) as resp:
            SPEC_CACHE.write_bytes(resp.read())
    return json.loads(SPEC_CACHE.read_text())


METHODS = ("get", "post", "put", "patch", "delete")


def _scopes(op: dict) -> str:
    return ", ".join(s for sec in op.get("security") or [] for scopes in sec.values() for s in scopes)


def _deref(spec: dict, node, depth: int = 0):
    if isinstance(node, dict):
        if "$ref" in node:
            parts = node["$ref"].lstrip("#/").split("/")
            target = spec
            for part in parts:
                target = target[part]
            return _deref(spec, target, depth + 1) if depth < 8 else {}
        return {k: _deref(spec, v, depth) for k, v in node.items() if k not in ("example", "examples")}
    if isinstance(node, list):
        return [_deref(spec, v, depth) for v in node]
    return node


def _schema_lines(schema: dict, indent: int = 1, depth: int = 4) -> list[str]:
    pad, lines = "  " * indent, []
    if not isinstance(schema, dict):
        return lines
    for comb in ("oneOf", "anyOf", "allOf"):
        if comb in schema:
            for alt in schema[comb]:
                lines += _schema_lines(alt, indent, depth)
            return lines
    if "items" in schema:
        return [pad + "array of:"] + _schema_lines(schema["items"], indent + 1, depth)
    required = set(schema.get("required") or [])
    for name, prop in (schema.get("properties") or {}).items():
        if not isinstance(prop, dict):
            continue
        kind = prop.get("type") or "object"
        enum = f" enum={prop['enum']}" if "enum" in prop else ""
        desc = (prop.get("description") or "").replace("\n", " ")[:140]
        lines.append(f"{pad}- {name}{'*' if name in required else ''}: {kind}{enum} {desc}".rstrip())
        if indent < depth and (prop.get("properties") or prop.get("items")):
            lines += _schema_lines(prop, indent + 1, depth)
    return lines


def cmd_spec(args) -> None:
    spec = load_spec(args.refresh)
    paths = spec["paths"]
    if args.path:
        ops = paths.get(args.path)
        if not ops:
            sys.exit(f"error: no such path; try: holded.py spec --grep {args.path.rsplit('/', 1)[-1]}")
        for method in METHODS:
            if method not in ops or (args.method and method != args.method):
                continue
            op = _deref(spec, ops[method])
            print(f"{method.upper()} {args.path}  [{_scopes(op)}]\n  {op.get('summary')}")
            print("  " + (op.get("description") or "").replace("\n", "\n  ")[:1800])
            for prm in op.get("parameters", []):
                sch = prm.get("schema", {})
                enum = sch.get("enum") or (sch.get("items") or {}).get("enum")
                print(f"  {prm.get('in')}: {prm.get('name')}{'*' if prm.get('required') else ''}"
                      f"{' enum=' + str(enum) if enum else ''}  {(prm.get('description') or '')[:120]}")
            body = (op.get("requestBody") or {}).get("content", {}).get("application/json", {}).get("schema")
            if body:
                print("  request body:")
                print("\n".join(_schema_lines(body, 2)))
            for code, resp in (op.get("responses") or {}).items():
                print(f"  → {code} {(resp.get('description') or '')[:100]}")
                schema = (resp.get("content") or {}).get("application/json", {}).get("schema")
                if schema and code.startswith("2"):
                    print("\n".join(_schema_lines(schema, 2)[:80]))
        return
    rows = []
    for path, ops in sorted(paths.items()):
        for method in METHODS:
            op = ops.get(method)
            if isinstance(op, dict):
                rows.append((path, method, op))
    if args.tag or args.grep:
        for path, method, op in rows:
            if args.tag and args.tag.lower() not in [t.lower() for t in op.get("tags") or []]:
                continue
            if args.grep and args.grep.lower() not in (path + " " + (op.get("summary") or "")).lower():
                continue
            print(f"{method.upper():6} {path}  [{_scopes(op)}]  {op.get('summary')}")
        return
    counts: dict[str, int] = {}
    for _, _, op in rows:
        for tag in op.get("tags") or ["(none)"]:
            counts[tag] = counts.get(tag, 0) + 1
    print(f"{len(paths)} paths, {len(rows)} operations (cache: {SPEC_CACHE})")
    for tag, n in sorted(counts.items()):
        print(f"  {n:3}  {tag}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scope", help="secrets file suffix, e.g. smartupsoft")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("usage")
    ac = sub.add_parser("accounts")
    ac.add_argument("--json", action="store_true")
    mv = sub.add_parser("movements")
    mv.add_argument("account_id")
    mv.add_argument("--from", dest="start")
    mv.add_argument("--to", dest="end")
    mv.add_argument("--status", action="append", help="pending | reconciled | partial | forced_reconciled")
    mv.add_argument("--json", action="store_true")
    gt = sub.add_parser("get")
    gt.add_argument("path")
    gt.add_argument("params", nargs="*", help="key=value query parameters")
    gt.add_argument("--all", action="store_true", help="follow the cursor to the last page")
    sp = sub.add_parser("spec")
    sp.add_argument("--tag")
    sp.add_argument("--path")
    sp.add_argument("--method")
    sp.add_argument("--grep")
    sp.add_argument("--refresh", action="store_true")
    args = ap.parse_args()

    if args.cmd == "spec":
        return cmd_spec(args)

    api = Holded(load_token(args.scope))
    if args.cmd == "usage":
        status, body = api.get("/api/v2/usage")
        print(json.dumps(body, indent=1) if status == 200 else f"{status}: {body}")
    elif args.cmd == "accounts":
        accounts = api.items("/api/v2/treasury/accounts")
        if args.json:
            json.dump(accounts, sys.stdout, indent=1)
        for acc in [] if args.json else accounts:
            print(f"{acc['id']}  {acc.get('type'):8} archived={acc.get('archived')!s:5} "
                  f"pending={acc.get('transactions_pending_to_reconcile')!s:4} synced={str(acc.get('synced_at'))[:10]} "
                  f"balance={acc.get('balance')} {acc.get('currency')}  {acc.get('name')} ({acc.get('institution_name')})")
    elif args.cmd == "movements":
        rows = api.items(f"/api/v2/treasury/accounts/{args.account_id}/bank-movements", limit=200,
                         start_date=args.start, end_date=args.end, status=args.status)
        if args.json:
            json.dump(rows, sys.stdout, indent=1)
        else:
            for row in rows:
                print(f"{row['value_date'][:10]}  {money(row['amount']):>10}  {row['status']:17} {row['id']}  {row['description'][:70]}")
            print(f"{len(rows)} movements", file=sys.stderr)
    elif args.cmd == "get":
        params = dict(p.split("=", 1) for p in args.params)
        if args.all:
            json.dump(api.items(args.path, **params), sys.stdout, indent=1)
        else:
            status, body = api.get(args.path, **params)
            print(json.dumps(body, indent=1) if status == 200 else f"{status}: {body}")
    print(f"({api.calls} API call{'s' if api.calls != 1 else ''})", file=sys.stderr)


if __name__ == "__main__":
    main()
