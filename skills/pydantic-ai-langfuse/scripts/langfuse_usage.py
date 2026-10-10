#!/usr/bin/env python3
"""Read-only Langfuse USAGE report: how many billable events a project sends, and
how many of them are not LLM calls.

Answers "who used the quota?" after an "ingestion suspended" / usage-threshold
mail, and "is something other than LLM calls going to Langfuse?" before one.
Stdlib only.

  langfuse_usage.py --env backend/.envs/.local/.django --since 2026-09-27
  langfuse_usage.py --env .env --since 14d --scopes 2026-10-08   # one day by OTel scope

Credentials: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_BASE_URL (or
LANGFUSE_HOST; default https://cloud.langfuse.com), from the environment or an
env file (`KEY=value` or `KEY = "value"`; the FIRST occurrence of each key wins,
so point it at one project's file, not at a multi-resource export).

Billable events ("units") = traces + observations + scores. The org's usage page
and the suspension mail count every project of the organization together; the
script prints the organization of the key so a second project is not missed.

"no model" = observations with no model name: wrapper spans from @observe on a
non-generation function are normal and few (about one per trace). Dozens per
trace means infrastructure spans (DB, Redis, HTTP, Celery) are being exported:
run --scopes on a busy day to see which instrumentation they come from.

Reading still works while ingestion is suspended.
"""
from __future__ import annotations

import argparse
import base64
import collections
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"


def load_env(path: str | None) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k.startswith("LANGFUSE_")}
    if path:
        found: dict[str, str] = {}
        for line in open(path, encoding="utf-8", errors="replace"):
            m = re.match(r"\s*(?:export\s+)?(LANGFUSE_[A-Z_]+)\s*=\s*(.*)", line)
            if m and m.group(1) not in found:
                found[m.group(1)] = m.group(2).strip().strip("\"'")
        env.update(found)
    return env


class Api:
    def __init__(self, env: dict[str, str]):
        try:
            pk, sk = env["LANGFUSE_PUBLIC_KEY"], env["LANGFUSE_SECRET_KEY"]
        except KeyError as e:
            sys.exit(f"missing {e.args[0]} (environment or --env file)")
        self.base = (env.get("LANGFUSE_BASE_URL") or env.get("LANGFUSE_HOST") or "https://cloud.langfuse.com").rstrip("/")
        self.auth = base64.b64encode(f"{pk}:{sk}".encode()).decode()

    def get(self, path: str) -> dict:
        req = urllib.request.Request(self.base + path, headers={"Authorization": f"Basic {self.auth}", "User-Agent": UA})
        for _ in range(8):
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e:
                if e.code != 429:
                    sys.exit(f"{e.code} on {path.split('?')[0]}: {e.read()[:200].decode('utf-8', 'replace')}")
                time.sleep(15)  # the list endpoints allow a handful of calls per minute
        sys.exit(f"still rate limited on {path.split('?')[0]}")


def parse_since(value: str) -> dt.datetime:
    now = dt.datetime.now(dt.timezone.utc)
    if m := re.fullmatch(r"(\d+)d", value):
        return (now - dt.timedelta(days=int(m.group(1)))).replace(hour=0, minute=0, second=0, microsecond=0)
    return dt.datetime.fromisoformat(value).replace(tzinfo=dt.timezone.utc)


def z(t: dt.datetime) -> str:  # the API rejects +00:00
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def report(api: Api, since: dt.datetime) -> None:
    for p in api.get("/api/public/projects")["data"]:
        org = p.get("organization") or {}
        print(f"project: {p['name']} ({p['id']})   organization: {org.get('name')} ({org.get('id')})")
    rows, page = [], 1
    while True:
        d = api.get(f"/api/public/metrics/daily?fromTimestamp={z(since)}&limit=50&page={page}")
        rows += d["data"]
        if page >= d["meta"]["totalPages"]:
            break
        page += 1
    scores = api.get(f"/api/public/v2/scores?limit=1&fromTimestamp={z(since)}")["meta"]["totalItems"]
    print(f"\n{'date':10s} {'traces':>7s} {'observ.':>8s} {'no model':>9s} {'obs/trace':>9s} {'cost $':>8s}")
    t_sum = o_sum = n_sum = 0
    for r in sorted(rows, key=lambda r: r["date"]):
        no_model = sum(u.get("countObservations", 0) for u in r.get("usage", []) if not u.get("model"))
        t, o = r["countTraces"], r["countObservations"]
        t_sum, o_sum, n_sum = t_sum + t, o_sum + o, n_sum + no_model
        print(f"{r['date']:10s} {t:7d} {o:8d} {no_model:9d} {(o / t if t else 0):9.1f} {r.get('totalCost') or 0:8.2f}")
    # The window, not the rows: the API returns no row for a day without events.
    days = max((dt.datetime.now(dt.timezone.utc) - since).total_seconds() / 86400, 1)
    units = t_sum + o_sum + scores
    print(f"\nsince {z(since)}: {t_sum} traces + {o_sum} observations + {scores} scores = {units} billable events")
    print(f"per day over {days:.1f} days: {units / days:,.0f}   per 30 days at this rate: {units / days * 30:,.0f}")
    if rows and (active := len(rows)) < days * 0.8:
        # A project that only started (or only runs some days) is under-projected by the line above.
        print(f"events on {active} of those days: {units / active:,.0f} per active day, "
              f"{units / active * 30:,.0f} per 30 days if every day were one")
    if o_sum:
        per_trace = o_sum / max(t_sum, 1)
        print(f"observations without a model: {n_sum} ({n_sum / o_sum:.0%}); observations per trace: {per_trace:.1f}")
        if per_trace > 5 and n_sum / o_sum > 0.5:
            print("-> more than 5 spans per trace and most of them not LLM calls: run --scopes <busy day>")


def scope_name(metadata: dict) -> str:
    # SDK v3 spans carry {"scope": {"name": ...}}; v4 spans carry the flat key "scope.name".
    nested = metadata.get("scope")
    return (nested.get("name") if isinstance(nested, dict) else None) or metadata.get("scope.name") or "?"


def scopes(api: Api, day: str) -> None:
    by_scope: collections.Counter[str] = collections.Counter()
    names: collections.Counter[tuple[str, str]] = collections.Counter()
    cursor = None
    while True:
        q = f"/api/public/v2/observations?limit=1000&fromStartTime={day}T00:00:00Z&toStartTime={day}T23:59:59.999Z&fields=core,basic,metadata"
        if cursor:
            q += "&cursor=" + urllib.parse.quote(cursor)
        d = api.get(q)
        for o in d["data"]:
            if o["id"].startswith("t-"):
                continue  # the trace itself, listed as a row; not an observation
            scope = scope_name(o.get("metadata") or {})
            by_scope[scope] += 1
            names[(scope.rsplit(".", 1)[-1], (o.get("name") or "")[:50])] += 1
        cursor = (d.get("meta") or {}).get("cursor")
        if not cursor or not d["data"]:
            break
    n = max(by_scope.total(), 1)
    print(f"\n{day}: {by_scope.total()} observations by instrumentation scope")
    for scope, count in by_scope.most_common():
        print(f"  {count:7d}  {count / n:5.0%}  {scope}")
    print("top span names:")
    for (scope, name), count in names.most_common(15):
        print(f"  {count:7d}  {scope}: {name}")
    print("LLM spans are `langfuse-sdk` and the GenAI instrumentations (pydantic-ai, openai, ...); "
          "`opentelemetry.instrumentation.*` are infrastructure and belong in Tempo.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env", help="env file with LANGFUSE_* keys (default: the environment)")
    ap.add_argument("--since", default="30d", help="start: Nd or YYYY-MM-DD (UTC); use the billing period start")
    ap.add_argument("--scopes", metavar="YYYY-MM-DD", help="also break one day down by OTel instrumentation scope")
    args = ap.parse_args()
    api = Api(load_env(args.env))
    report(api, parse_since(args.since))
    if args.scopes:
        scopes(api, args.scopes)


if __name__ == "__main__":
    main()
