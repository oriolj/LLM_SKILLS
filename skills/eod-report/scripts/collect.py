#!/usr/bin/env python3
"""Collect one day of git activity across every local repo, grouped by project.

Deterministic half of the eod-report skill: it finds the repos with commits
(or uncommitted edits) in the window, maps each repo to its project through
hq docs/projects.md, flags the paths a maintainer or a business owner must
hear about, and prints JSON (default) or a short text overview. The agent
writes the prose; this script never sends anything.

    collect.py                         # today, local time
    collect.py --date yesterday --fetch
    collect.py --date 2026-10-02 --project EnaCast --format text
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
DEFAULT_ROOTS = [HOME / "git"]
DEFAULT_HQ = HOME / "Syncthing" / "Syncthing-mobile-docs" / "hq"
DEFAULT_LEDGER = DEFAULT_HQ / "oriolj" / "eod-reports" / "sent.jsonl"
SKIP_DIRS = {"node_modules", ".venv", "venv", "dist", "build", ".next", "archived", "vendor"}
MAX_DEPTH = 4

GIT_ENV = {
    **os.environ,
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_SSH_COMMAND": "ssh -o BatchMode=yes -o ConnectTimeout=10",
    "LC_ALL": "C",
}

# Path flags: what the reader must hear about even when the commit subject is quiet.
# Order matters only for display. Patterns match the repo-relative path.
FLAGS: list[tuple[str, re.Pattern[str]]] = [
    # hq areas about Oriol's private life, not project work: never summarized in a report.
    ("private_life", re.compile(r"^oriolj/(finances|recordings|crm|homebox)/")),
    ("secrets", re.compile(r"(^|/)secrets/|\.enc$|(^|/)\.env($|\.)(?!example)")),
    ("migrations", re.compile(r"(^|/)migrations/\d|(^|/)migrations?/.*\.(sql|py|go)$|(^|/)alembic/versions/")),
    ("deploy_config", re.compile(
        r"(^|/)(Dockerfile[^/]*|docker-compose[^/]*\.ya?ml|compose[^/]*\.ya?ml|Makefile|Procfile|"
        r"wrangler\.(toml|jsonc?)|vercel\.json|netlify\.toml|fly\.toml|crontab)$|(^|/)\.github/workflows/|"
        r"(^|/)(ansible|playbooks|roles)/")),
    ("dependencies", re.compile(
        r"(^|/)(pyproject\.toml|uv\.lock|requirements[^/]*\.txt|package\.json|pnpm-lock\.yaml|"
        r"package-lock\.json|yarn\.lock|bun\.lockb?|go\.mod|go\.sum|Cargo\.(toml|lock)|Gemfile(\.lock)?|"
        r"composer\.(json|lock)|build\.gradle(\.kts)?|libs\.versions\.toml|Podfile(\.lock)?)$")),
    ("env_settings", re.compile(r"(^|/)[^/]*\.env\.example$|(^|/)\.env\.example$|(^|/)settings/[^/]+\.py$|(^|/)settings\.py$")),
    ("user_todo", re.compile(r"(^|/)USER_TODO\.md$")),
    ("qa_pending", re.compile(r"(^|/)QA_PENDING\.md$")),
    ("deploy_docs", re.compile(r"(^|/)DEPLOY\.md$|(^|/)docs/09-deploy-and-ops\.md$|(^|/)[^/]*deploy[^/]*\.md$", re.I)),
    ("agent_rules", re.compile(r"(^|/)(CLAUDE|AGENTS)\.md$|(^|/)SKILL\.md$|(^|/)\.claude/")),
    ("i18n", re.compile(r"(^|/)(locale|locales|i18n|translations|messages)/|\.po$")),
    ("pricing_billing", re.compile(r"pricing|billing|stripe|revenuecat|subscription|invoice|checkout", re.I)),
    ("legal", re.compile(r"privacy|privacitat|privacidad|terms|legal|cookies|aviso|gdpr|rgpd", re.I)),
    ("release_notes", re.compile(r"CHANGELOG|release[-_ ]?notes|changelog", re.I)),
    ("tests", re.compile(r"(^|/)tests?/|(^|/)test_[^/]+\.py$|_test\.(py|go)$|\.(test|spec)\.[jt]sx?$|(^|/)e2e/")),
]

TODO_FILES = ("USER_TODO.md", "QA_PENDING.md")


def git(repo: Path, *args: str, timeout: int = 60) -> tuple[int, str, str]:
    try:
        p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                           env=GIT_ENV, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {timeout}s"


def find_repos(roots: list[Path], hq: Path) -> list[Path]:
    """Every dir holding a .git (dir or file), up to MAX_DEPTH, never crossing mounts."""
    found: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        root_dev = root.stat().st_dev

        def walk(d: Path, depth: int) -> None:
            if (d / ".git").exists():
                found.append(d)
            if depth >= MAX_DEPTH:
                return
            try:
                children = sorted(c for c in d.iterdir() if c.is_dir() and not c.is_symlink())
            except OSError:
                return
            for c in children:
                if c.name in SKIP_DIRS or c.name.startswith("."):
                    continue
                try:
                    if c.stat().st_dev != root_dev:
                        continue
                except OSError:
                    continue
                walk(c, depth + 1)

        walk(root, 0)
    if (hq / ".git").exists():
        found.append(hq)
    # A stray .git (an empty dir, a dead worktree pointer) is not a repo.
    return [d for d in found if git(d, "rev-parse", "--git-dir", timeout=10)[0] == 0]


def window(date_arg: str) -> tuple[dt.datetime, dt.datetime]:
    today = dt.datetime.now().astimezone().date()
    if date_arg == "today":
        day = today
    elif date_arg == "yesterday":
        day = today - dt.timedelta(days=1)
    else:
        day = dt.date.fromisoformat(date_arg)
    tz = dt.datetime.now().astimezone().tzinfo
    start = dt.datetime.combine(day, dt.time.min, tzinfo=tz)
    return start, start + dt.timedelta(days=1)


def norm_remote(url: str) -> str:
    """git@github.com:Org/Repo.git / https://github.com/Org/Repo -> github.com/org/repo"""
    url = url.strip()
    m = re.match(r"^(?:\w+://)?(?:[^@/]+@)?([^/:]+)[:/](.+?)(?:\.git)?/?$", url)
    if not m:
        return url.lower()
    return f"{m.group(1)}/{m.group(2)}".lower()


def parse_projects(hq: Path) -> tuple[dict[str, dict], dict[str, dict]]:
    """Map normalized remote and local dir hints -> {project, family, scope} from projects.md rows."""
    by_remote: dict[str, dict] = {}
    by_local: dict[str, dict] = {}
    path = hq / "docs" / "projects.md"
    if not path.exists():
        return by_remote, by_local
    scope = family = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            scope, family = line[3:].strip(), None
            continue
        if line.startswith("### "):
            head = line[4:].strip()
            # "EnaCast — the radio platform" is a product family (one mail);
            # "Other Enantena" is a bucket of unrelated projects (one mail each).
            family = head.split(" — ")[0].strip() if " — " in head else None
            continue
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = line.split("|")
        if len(cells) < 3:
            continue
        name_m = re.search(r"\*\*([^*]+)\*\*", cells[1])
        if not name_m or cells[1].strip().startswith("~~"):
            continue
        info = {"project": name_m.group(1).strip(), "family": family, "scope": scope}
        # Repos linked in the last ("Code / docs") column are the project's own;
        # a link elsewhere in the row is usually a reference (PixelPals cites LLM_SKILLS).
        code_cell = next((c for c in reversed(cells) if c.strip()), "")
        if re.search(r"(github|gitlab)\.com|~/git/|GitHub |GitLab ", code_cell):
            line = code_cell
        for host, slug in re.findall(r"(github\.com|gitlab\.com)[/:]([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)", line):
            slug = re.sub(r"\.git$", "", slug.rstrip(".)"))
            claim(by_remote, f"{host}/{slug}".lower(), info)
        for local in re.findall(r"~/git/([A-Za-z0-9_./-]+)", line):
            claim(by_local, local.strip("/.`)").lower(), info)
        # "GitLab `smartupsoft/bikecrm-backend`, `bikecrm-frontend`": bare names after
        # an org/repo belong to the same org.
        for m in re.finditer(r"(GitHub|GitLab) `?([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)`?((?:,? (?:and )?`[A-Za-z0-9_.-]+`)*)", line):
            host, org = m.group(1).lower(), m.group(2)
            for repo in [m.group(3), *re.findall(r"`([A-Za-z0-9_.-]+)`", m.group(4) or "")]:
                claim(by_remote, f"{host}.com/{org}/{repo}".lower(), info)
    return by_remote, by_local


def squash(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def claim(table: dict, key: str, info: dict) -> None:
    """Several rows can link one repo; the row named like the repo wins, else the first."""
    current = table.get(key)
    if current is None or (squash(info["project"]) == squash(key.rsplit("/", 1)[-1])
                           and squash(current["project"]) != squash(key.rsplit("/", 1)[-1])):
        table[key] = info


def classify(path: str) -> list[str]:
    return [name for name, rx in FLAGS if rx.search(path)]


def todo_changes(repo: Path, since: str, until: str, refs: list[str]) -> dict[str, dict[str, list[str]]]:
    """Lines added/removed in USER_TODO.md / QA_PENDING.md (any depth) in the window."""
    out: dict[str, dict[str, list[str]]] = {}
    for name in TODO_FILES:
        rc, diff, _ = git(repo, "log", *refs, f"--since={since}", f"--until={until}", "-p",
                          "--no-merges", "--format=", "--", f":(glob)**/{name}")
        if rc != 0 or not diff.strip():
            continue
        added = [l[1:].rstrip() for l in diff.splitlines()
                 if l.startswith("+") and not l.startswith("+++") and l[1:].strip()]
        removed = [l[1:].rstrip() for l in diff.splitlines()
                   if l.startswith("-") and not l.startswith("---") and l[1:].strip()]
        # A line both added and removed in the window was rewritten or done the same day.
        out[name] = {"added": [l for l in added if l not in removed],
                     "removed": [l for l in removed if l not in added]}
    return out


def collect_repo(repo: Path, start: dt.datetime, end: dt.datetime, do_fetch: bool,
                 reported: set[str], by_remote: dict, by_local: dict, hq: Path) -> dict | None:
    info: dict = {"path": str(repo).replace(str(HOME), "~", 1), "errors": []}
    if do_fetch:
        rc, _, err = git(repo, "fetch", "--all", "--prune", "--quiet", timeout=45)
        msgs = [l.strip() for l in err.splitlines() if l.strip()]
        key = next((l for l in msgs if re.match(r"(fatal|error|ERROR)", l)), msgs[0] if msgs else str(rc))
        info["fetch"] = "ok" if rc == 0 else f"failed: {key[:200]}"

    rc, remote, _ = git(repo, "remote", "get-url", "origin")
    info["remote"] = remote.strip() if rc == 0 else None
    rc, remotes, _ = git(repo, "remote")
    has_remote = rc == 0 and bool(remotes.split())
    rc, common, _ = git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    info["common_dir"] = common.strip() if rc == 0 else str(repo / ".git")
    rc, branch, _ = git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    info["branch"] = branch.strip()
    rc, head, _ = git(repo, "rev-parse", "--short", "HEAD")
    info["head"] = head.strip() if rc == 0 else None

    rc, counts, _ = git(repo, "rev-list", "--left-right", "--count", "@{u}...HEAD")
    if rc == 0 and counts.split():
        behind, ahead = counts.split()
        info["upstream"] = {"ahead": int(ahead), "behind": int(behind)}
    else:
        info["upstream"] = None  # no upstream branch: nothing is pushed anywhere

    since, until = start.isoformat(), end.isoformat()
    # Local branches + remote-tracking branches: commits pushed from other
    # machines show up here after --fetch; stash refs are deliberately excluded.
    refs = ["--branches", "--remotes", "HEAD"]
    sep_c, sep_f = "\x1e", "\x1f"
    fmt = sep_c + sep_f.join(["%H", "%h", "%an", "%ae", "%aI", "%cI", "%P", "%s", "%b"]) + sep_f
    rc, log, err = git(repo, "log", *refs, f"--since={since}", f"--until={until}",
                       f"--format={fmt}", "--name-status", "--date-order")
    if rc != 0:
        info["errors"].append(f"git log: {err.strip()[:200]}")
        log = ""

    rc, local_only, _ = git(repo, "log", "--branches", "--not", "--remotes", "--format=%H")
    unpushed = set(local_only.split()) if rc == 0 else set()

    commits = []
    for chunk in log.split(sep_c)[1:]:
        parts = chunk.split(sep_f)
        if len(parts) < 10:
            continue
        full, short, an, ae, adate, cdate, parents, subject, body, files_blob = parts[:10]
        files = []
        for fl in files_blob.strip().splitlines():
            bits = fl.split("\t")
            if len(bits) >= 2:
                files.append({"status": bits[0][0], "path": bits[-1]})
        commits.append({
            "hash": short, "full": full, "author": an, "email": ae, "date": adate,
            "committed": cdate, "merge": len(parents.split()) > 1,
            "subject": subject, "body": body.strip()[:1500],
            # None = the repo has no remote at all (hq): "unpushed" means nothing there.
            "files": files, "pushed": (full not in unpushed) if has_remote else None,
            "already_reported": full in reported,
        })

    # Uncommitted edits made in the window (a dirty tree from last month is not news).
    rc, porcelain, _ = git(repo, "status", "--porcelain", "--untracked-files=normal")
    dirty_today = []
    if rc == 0:
        for l in porcelain.splitlines():
            rel = l[3:].split(" -> ")[-1].strip('"')
            p = repo / rel
            # A deleted file has no mtime: its directory's mtime dates the deletion.
            target = p if p.exists() else next((d for d in p.parents if d.exists()), repo)
            try:
                mt = dt.datetime.fromtimestamp(target.stat().st_mtime).astimezone()
            except OSError:
                continue
            if start <= mt < end:
                dirty_today.append({"code": l[:2].strip(), "path": rel})
    info["dirty_total"] = len(porcelain.splitlines()) if rc == 0 else None

    if not commits and not dirty_today:
        # Keep a failed fetch visible: that repo's only activity today may be a
        # push from another machine we could not see.
        if info.get("fetch", "ok") != "ok":
            return {"idle": True, "path": info["path"], "fetch": info["fetch"]}
        return None

    new = [c for c in commits if not c["already_reported"]]
    flags: dict[str, list[str]] = {}
    for c in new:
        for f in c["files"]:
            for name in classify(f["path"]):
                lst = flags.setdefault(name, [])
                if f["path"] not in lst:
                    lst.append(f["path"])
    for d in dirty_today:
        for name in classify(d["path"]):
            flags.setdefault(name, [])
            if d["path"] not in flags[name]:
                flags[name].append(d["path"])

    shortstat = {"files": 0, "insertions": 0, "deletions": 0}
    hashes = [c["full"] for c in new if not c["merge"]]
    if hashes:
        rc, st, _ = git(repo, "show", "--format=", "--shortstat", *hashes)
        for line in st.splitlines():
            for key, rx in (("files", r"(\d+) files? changed"), ("insertions", r"(\d+) insertion"),
                            ("deletions", r"(\d+) deletion")):
                m = re.search(rx, line)
                if m:
                    shortstat[key] += int(m.group(1))

    mapped = by_remote.get(norm_remote(info["remote"])) if info["remote"] else None
    if mapped is None:
        rel = str(repo.relative_to(HOME / "git")).lower() if repo.is_relative_to(HOME / "git") else ""
        mapped = by_local.get(rel)
    if repo == hq:
        mapped = {"project": "hq", "family": None, "scope": "Shared / infrastructure"}

    info.update({
        "repo": repo.name,
        "project": mapped["project"] if mapped else None,
        "family": mapped["family"] if mapped else None,
        "scope": mapped["scope"] if mapped else None,
        "in_projects_md": mapped is not None,
        "mapped_by": "projects.md" if mapped is not None else None,
        "commits": commits,
        "new_commits": len(new),
        "authors": sorted({c["author"] for c in new}),
        "has_remote": has_remote,
        "unpushed_in_window": sum(1 for c in new if c["pushed"] is False),
        "dirty_today": dirty_today,
        "flags": flags,
        "todo_changes": todo_changes(repo, since, until, refs),
        "shortstat": shortstat,
        "make_targets": make_targets(repo),
    })
    return info


def make_targets(repo: Path) -> list[str]:
    """The observability/deploy targets the agent may run read-only to verify 'live'."""
    mk = repo / "Makefile"
    if not mk.exists():
        return []
    try:
        text = mk.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    wanted = ("prod-status", "deploy-status", "version", "logs-prod-errors", "error-traces")
    return [t for t in wanted if re.search(rf"^{re.escape(t)}\s*:", text, re.M)]


def load_reported(ledger: Path) -> set[str]:
    out: set[str] = set()
    if not ledger.exists():
        return out
    for line in ledger.read_text(encoding="utf-8").splitlines():
        try:
            out.update(json.loads(line).get("commits", []))
        except json.JSONDecodeError:
            continue
    return out


def merge_worktrees(repos: list[dict]) -> list[dict]:
    """Worktrees share one object store, so they would list the same commits twice:
    keep one entry per git common dir, the others become its `worktrees`."""
    by_common: dict[str, dict] = {}
    for r in repos:
        primary = by_common.get(r["common_dir"])
        if primary is None:
            r["worktrees"] = []
            by_common[r["common_dir"]] = r
            continue
        primary["worktrees"].append({k: r[k] for k in ("path", "branch", "head", "upstream", "dirty_today")})
        for name, paths in r["flags"].items():
            if name in ("user_todo", "qa_pending") or not r["dirty_today"]:
                continue
            for p in paths:
                if p not in primary["flags"].setdefault(name, []):
                    primary["flags"][name].append(p)
    return list(by_common.values())


def map_by_prefix(repos: list[dict]) -> None:
    """A repo missing from projects.md joins a mapped sibling in the same owner dir
    whose name shares its first word (bikecrm-frontend -> bikecrm-backend's BikeCRM).
    `in_projects_md` stays False: the missing row is still a finding."""
    def stem(r: dict) -> tuple[str, str]:
        p = Path(r["path"])
        return str(p.parent), re.split(r"[-_.]", p.name.lower())[0]
    mapped = {stem(r): r for r in repos if r["in_projects_md"] and r["project"] != "hq"}
    for r in repos:
        if r["in_projects_md"]:
            continue
        sib = mapped.get(stem(r))
        if sib:
            r.update(project=sib["project"], family=sib["family"], scope=sib["scope"],
                     mapped_by=f"name prefix of {Path(sib['path']).name}")


def group(repos: list[dict]) -> list[dict]:
    """One mail per project; a product family (### X — ...) is one project with a section per repo."""
    mails: dict[str, dict] = {}
    for r in repos:
        key = r["family"] or r["project"] or f"(unmapped) {r['repo']}"
        m = mails.setdefault(key, {"mail": key, "scope": r["scope"], "repos": []})
        m["repos"].append(r)
    return sorted(mails.values(), key=lambda m: -sum(r["new_commits"] for r in m["repos"]))


def text_overview(result: dict) -> str:
    lines = [f"window {result['window']['start']} -> {result['window']['end']} "
             f"({result['repos_scanned']} repos scanned, fetch={'yes' if result['fetched'] else 'no'})"]
    for m in result["mails"]:
        total = sum(r["new_commits"] for r in m["repos"])
        lines.append(f"\n== {m['mail']}  [{m['scope']}]  {total} new commits")
        for r in m["repos"]:
            up = r["upstream"]
            up_s = "no upstream" if up is None else f"ahead {up['ahead']} behind {up['behind']}"
            lines.append(f"  - {r['path']} ({r['project'] or '?'}{'' if r['in_projects_md'] else ', NOT IN projects.md'}) {r['branch']}@{r['head']} "
                         f"{up_s}; new {r['new_commits']}, unpushed {r['unpushed_in_window']}, "
                         f"dirty today {len(r['dirty_today'])}; authors {', '.join(r['authors']) or '-'}")
            for w in r["worktrees"]:
                wup = w["upstream"]
                wup_s = "no upstream" if wup is None else f"ahead {wup['ahead']} behind {wup['behind']}"
                lines.append(f"      worktree {w['path']} {w['branch']}@{w['head']} {wup_s}, "
                             f"dirty today {len(w['dirty_today'])}")
            if r["flags"]:
                lines.append("      flags: " + ", ".join(f"{k}({len(v)})" for k, v in r["flags"].items()))
            for name, ch in r["todo_changes"].items():
                lines.append(f"      {name}: +{len(ch['added'])} -{len(ch['removed'])}")
            for c in r["commits"]:
                mark = "R" if c["already_reported"] else ("U" if c["pushed"] is False else " ")
                lines.append(f"      {mark} {c['hash']} {c['date'][11:16]} {c['author']}: {c['subject']}")
    if result.get("already_reported_mails"):
        lines.append("\nalready reported, nothing new: " + ", ".join(result["already_reported_mails"]))
    if result["fetch_failures"]:
        lines.append("\nfetch failures: " + "; ".join(result["fetch_failures"]))
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", default="today", help="today | yesterday | YYYY-MM-DD (local calendar day)")
    ap.add_argument("--fetch", action="store_true", help="git fetch every repo first (sees other machines' pushes)")
    ap.add_argument("--root", action="append", type=Path, help="repo root to scan (repeatable; default ~/git)")
    ap.add_argument("--hq", type=Path, default=DEFAULT_HQ)
    ap.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER,
                    help="sent.jsonl of previous reports; their commits are marked already_reported")
    ap.add_argument("--project", action="append", default=[],
                    help="keep only mails whose name, project or repo contains this (case-insensitive)")
    ap.add_argument("--format", choices=("json", "text"), default="json")
    ap.add_argument("--out", type=Path, help="write the output here instead of stdout")
    ap.add_argument("--from-json", type=Path,
                    help="print the text overview of a saved JSON run (no second scan or fetch)")
    a = ap.parse_args()

    if a.from_json:
        print(text_overview(json.loads(a.from_json.read_text(encoding="utf-8"))))
        return 0

    start, end = window(a.date)
    roots = a.root or DEFAULT_ROOTS
    by_remote, by_local = parse_projects(a.hq)
    reported = load_reported(a.ledger)
    repos = find_repos(roots, a.hq)

    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(lambda r: collect_repo(r, start, end, a.fetch, reported, by_remote, by_local, a.hq),
                              repos))
    active = merge_worktrees([r for r in results if r and not r.get("idle")])
    map_by_prefix(active)
    mails = group(active)
    # A mail whose commits were all sent already, with no new uncommitted work, is not sent again.
    done = [m["mail"] for m in mails if not any(r["new_commits"] or r["dirty_today"] for r in m["repos"])]
    mails = [m for m in mails if m["mail"] not in done]
    if a.project:
        needles = [p.lower() for p in a.project]
        mails = [m for m in mails if any(
            n in (m["mail"] or "").lower() or any(n in (r["project"] or "").lower() or n in r["repo"].lower()
                                                   for r in m["repos"]) for n in needles)]

    fetch_failures = []
    if a.fetch:
        for res in results:
            if res and res.get("fetch", "ok") != "ok":
                fetch_failures.append(f"{res['path']}: {res['fetch']}")

    result = {
        "window": {"start": start.isoformat(), "end": end.isoformat(), "date": start.date().isoformat()},
        "host": os.uname().nodename,
        "repos_scanned": len(repos),
        "hq_git": (a.hq / ".git").exists(),
        "fetched": a.fetch,
        "fetch_failures": fetch_failures,
        "unmapped_repos": [r["path"] for r in active if not r["in_projects_md"]],
        "already_reported_mails": done,
        "mails": mails,
    }
    out = json.dumps(result, indent=1, ensure_ascii=False) if a.format == "json" else text_overview(result)
    if a.out:
        a.out.write_text(out + "\n", encoding="utf-8")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
