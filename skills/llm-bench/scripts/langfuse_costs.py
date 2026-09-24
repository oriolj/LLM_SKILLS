#!/usr/bin/env python3
"""Read-only LLM spend and volume report from Langfuse, per generation name x model.

Answers "what does each LLM feature cost, how often does it run, and did a change
move it?" without the UI. Stdlib only (runs anywhere python3 exists).

  langfuse_costs.py --env backend/.envs/.local/.django --since 30d
  langfuse_costs.py --env .env --since 2026-09-17 --until 2026-09-24
  langfuse_costs.py --env .env --since 14d --split 2026-09-24T07:45Z   # before vs after a deploy
  langfuse_costs.py --env .env --since 7d --by user                   # spend per tenant (userId)
  langfuse_costs.py --env .env --since 7d --name gpt-podcast-analysis --daily

Credentials: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_BASE_URL (or LANGFUSE_HOST; default
https://cloud.langfuse.com like the SDKs),
from the environment or an env file (`KEY=value` or `KEY = "value"`, one per line).

Cost column = Langfuse's cost for the observation: the cost the app sent
(`cost_details={"total": ...}`) or, when it sent none, Langfuse's own price-table
estimate. "with cost" counts observations that have any cost at all; a feature with
0 there is invisible to cost dashboards (fix the instrumentation, not the report).
Per-month figures scale the window's daily mean to 30 days: a bulk backfill inside
the window inflates them, so read --daily before trusting a month.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"


def load_env(path: str | None) -> dict[str, str]:
    env = dict(os.environ)
    if path:
        for line in open(path, encoding="utf-8"):
            m = re.match(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*['\"]?([^'\"\n#]*)", line)
            if m:
                env.setdefault(m[1], m[2].strip())
    return env


def parse_when(value: str, now: dt.datetime) -> dt.datetime:
    m = re.fullmatch(r"(\d+)([hd])", value)
    if m:
        delta = dt.timedelta(hours=int(m[1])) if m[2] == "h" else dt.timedelta(days=int(m[1]))
        return now - delta
    value = value.replace("Z", "+00:00")
    parsed = dt.datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


def iso(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


class Client:
    def __init__(self, host: str, public: str, secret: str):
        self.host = host.rstrip("/")
        self.auth = "Basic " + base64.b64encode(f"{public}:{secret}".encode()).decode()

    def get(self, path: str, params: dict) -> dict:
        url = f"{self.host}{path}?{urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})}"
        for attempt in range(5):
            req = urllib.request.Request(url, headers={"Authorization": self.auth, "User-Agent": UA})
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503, 504) and attempt < 4:
                    time.sleep(2 ** attempt * 2)
                    continue
                raise SystemExit(f"Langfuse {e.code} on {path}: {e.read()[:300]!r}")
        raise SystemExit("unreachable")

    def generations(self, since: dt.datetime, until: dt.datetime, name: str | None):
        """v2 (cursor) when the server has it, else v1 (pages)."""
        params = {"type": "GENERATION", "fromStartTime": iso(since), "toStartTime": iso(until), "name": name,
                  "limit": 1000, "fields": "core,basic,model,usage"}
        try:
            cursor = None
            while True:
                page = self.get("/api/public/v2/observations", {**params, "cursor": cursor})
                yield from page.get("data", [])
                cursor = (page.get("meta") or {}).get("cursor")
                if not cursor or not page.get("data"):
                    return
        except SystemExit as e:
            if "404" not in str(e):
                raise
        params.pop("fields")
        params["limit"] = 100
        n = 1
        while True:
            page = self.get("/api/public/observations", {**params, "page": n})
            yield from page.get("data", [])
            if n >= (page.get("meta") or {}).get("totalPages", 0):
                return
            n += 1


def cost_of(o: dict) -> float | None:
    for key in ("totalCost", "calculatedTotalCost"):
        if o.get(key) is not None:
            return float(o[key])
    total = (o.get("costDetails") or {}).get("total")
    return float(total) if total is not None else None


def tokens_of(o: dict) -> tuple[int, int]:
    u = o.get("usageDetails") or {}
    inp = u.get("input", o.get("inputUsage") or o.get("promptTokens") or 0) or 0
    out = u.get("output", o.get("outputUsage") or o.get("completionTokens") or 0) or 0
    return int(inp), int(out)


def summarise(rows: list[dict], days: float, key) -> list[dict]:
    groups: dict[tuple, dict] = defaultdict(lambda: {"n": 0, "with_cost": 0, "cost": 0.0, "in": 0, "out": 0})
    for o in rows:
        g = groups[key(o)]
        g["n"] += 1
        c = cost_of(o)
        if c is not None:
            g["with_cost"] += 1
            g["cost"] += c
        i, out = tokens_of(o)
        g["in"] += i
        g["out"] += out
    table = []
    for k, g in groups.items():
        table.append({"key": k, **g, "per_call": g["cost"] / g["with_cost"] if g["with_cost"] else None,
                      "month": g["cost"] / days * 30 if days else None, "calls_month": g["n"] / days * 30})
    return sorted(table, key=lambda r: -r["cost"])


def money(v: float | None) -> str:
    if v is None:
        return "–"
    return f"${v:,.2f}" if abs(v) >= 0.1 else f"${v:.5f}"


def print_table(title: str, table: list[dict], days: float, headers: list[str]) -> None:
    print(f"\n## {title} ({days:.1f} days)\n")
    print("| " + " | ".join(headers + ["calls", "with cost", "mean in tok", "mean out tok", "$/call", "total $",
                                       "calls/30d", "$/30d"]) + " |")
    print("|" + "---|" * (len(headers) + 8))
    for r in table:
        keys = r["key"] if isinstance(r["key"], tuple) else (r["key"],)
        print("| " + " | ".join(str(k or "–") for k in keys) +
              f" | {r['n']} | {r['with_cost']} | {r['in'] // max(r['n'], 1):,} | {r['out'] // max(r['n'], 1):,} | "
              f"{money(r['per_call'])} | {money(r['cost'])} | {r['calls_month']:,.0f} | {money(r['month'])} |")
    total = sum(r["cost"] for r in table)
    print(f"\nTotal {money(total)} over {sum(r['n'] for r in table):,} generations "
          f"(≈ {money(total / days * 30 if days else None)} per 30 days).")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env", help="env file with the LANGFUSE_* keys")
    ap.add_argument("--since", default="30d", help="30d, 12h or an ISO date/time (UTC if no zone)")
    ap.add_argument("--until", default=None, help="ISO date/time; default now")
    ap.add_argument("--split", default=None, help="ISO time (a deploy): report before and after separately")
    ap.add_argument("--name", default=None, help="only this generation name")
    ap.add_argument("--by", choices=["name", "user", "name-user"], default="name")
    ap.add_argument("--daily", action="store_true", help="also print calls and cost per UTC day")
    ap.add_argument("--json", help="write the raw per-group numbers to this file")
    args = ap.parse_args()

    env = load_env(args.env)
    # Same default as the Langfuse SDKs: projects that never set a host
    # (Panotxa's env has only the two keys) are on the EU cloud.
    host = env.get("LANGFUSE_BASE_URL") or env.get("LANGFUSE_HOST") or "https://cloud.langfuse.com"
    if not (env.get("LANGFUSE_PUBLIC_KEY") and env.get("LANGFUSE_SECRET_KEY")):
        sys.exit("LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY not found (env or --env file)")
    now = dt.datetime.now(dt.timezone.utc)
    since, until = parse_when(args.since, now), parse_when(args.until, now) if args.until else now
    client = Client(host, env["LANGFUSE_PUBLIC_KEY"], env["LANGFUSE_SECRET_KEY"])
    rows = list(client.generations(since, until, args.name))
    print(f"# Langfuse generations {iso(since)} → {iso(until)}: {len(rows):,} fetched from {host}")

    keyfn = {"name": lambda o: (o.get("name"), o.get("model")),
             "user": lambda o: (o.get("userId") or "(no user)",),
             "name-user": lambda o: (o.get("name"), o.get("userId") or "(no user)")}[args.by]
    headers = {"name": ["name", "model"], "user": ["userId"], "name-user": ["name", "userId"]}[args.by]
    out = {}
    windows = [("all", since, until, rows)]
    if args.split:
        cut = parse_when(args.split, now)
        start = lambda o: parse_when(o["startTime"], now)  # noqa: E731
        windows = [("before " + iso(cut), since, cut, [o for o in rows if start(o) < cut]),
                   ("after " + iso(cut), cut, until, [o for o in rows if start(o) >= cut])]
    for title, a, b, subset in windows:
        days = (b - a).total_seconds() / 86400
        table = summarise(subset, days, keyfn)
        print_table(title, table, days, headers)
        out[title] = [{**r, "key": list(r["key"])} for r in table]
    if args.by == "user" or args.by == "name-user":
        missing = sum(1 for o in rows if not o.get("userId"))
        if missing:
            print(f"\n{missing:,} generations have no userId (only visible via the v2 API; v1 servers show none).")
    if args.daily:
        per_day: dict[str, dict] = defaultdict(lambda: {"n": 0, "cost": 0.0})
        for o in rows:
            d = per_day[o["startTime"][:10]]
            d["n"] += 1
            d["cost"] += cost_of(o) or 0.0
        print("\n## Per UTC day\n\n| day | calls | $ |\n|---|---|---|")
        for day in sorted(per_day):
            print(f"| {day} | {per_day[day]['n']:,} | {money(per_day[day]['cost'])} |")
    if args.json:
        with open(args.json, "w") as f:
            json.dump(out, f, indent=1, default=str)


if __name__ == "__main__":
    main()
