#!/usr/bin/env python3
"""Persist a research agent's output to disk.

Each growth-research agent returns one message with two artefacts:
a markdown document and a JSON array, separated by fenced code blocks.
This helper parses that message, cleans HTML entities (which agents
occasionally emit even though JSON has no HTML escape syntax), validates
the JSON, and writes both files into the workdir.

Usage from inside a workdir:

    # pipe an agent's transcript via stdin
    python3 scripts/persist_agent_output.py influencers < /tmp/agent.txt

    # or pass a file path
    python3 scripts/persist_agent_output.py influencers --from /tmp/agent.txt

    # or pass the text inline (handy when copy-pasting)
    python3 scripts/persist_agent_output.py influencers --text "$(pbpaste)"

Writes:
    research/<topic>/<topic>.md
    research/<topic>/<topic>.json

Exit code 0 on success, non-zero on parse/validation failure (so it can be
chained into shell pipelines).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Common HTML entities that agents emit by mistake — JSON has no HTML escapes,
# so these end up literally in the spreadsheet cells if not cleaned.
HTML_ENTITY_MAP = {
    "&amp;": "&",
    "&lt;": "<",
    "&gt;": ">",
    "&quot;": '"',
    "&apos;": "'",
    "&#39;": "'",
    "&nbsp;": " ",
    "&mdash;": "—",
    "&ndash;": "–",
    "&hellip;": "…",
}


def clean_entities(text: str) -> str:
    for entity, char in HTML_ENTITY_MAP.items():
        text = text.replace(entity, char)
    return text


def extract_blocks(transcript: str) -> tuple[str, str]:
    """Split the agent transcript into (markdown, json) strings.

    Strategy:
      1. Find the first ```json ... ``` fenced block — that's the JSON.
      2. Everything BEFORE that block is the markdown region.
      3. In the markdown region, prefer an explicit ```markdown ... ``` fence
         if present, otherwise take everything from the first H1/H2 onward.
    """
    json_match = re.search(r"```json\s*\n(.*?)\n```", transcript, re.DOTALL)
    if not json_match:
        raise SystemExit(
            "error: no ```json fenced block found in input.\n"
            "Hint: the agent must wrap the JSON in a ```json ... ``` block."
        )
    json_content = json_match.group(1)
    before_json = transcript[: json_match.start()]

    md_match = re.search(r"```markdown\s*\n(.*?)\n```", before_json, re.DOTALL)
    if md_match:
        markdown_content = md_match.group(1)
    else:
        # No explicit markdown fence — strip any prefatory chatter before the
        # first heading and use the rest as the markdown body.
        heading_match = re.search(r"^(#{1,3} .+)$", before_json, re.MULTILINE)
        markdown_content = before_json[heading_match.start():] if heading_match else before_json
        markdown_content = markdown_content.strip()

    if not markdown_content.strip():
        raise SystemExit("error: could not locate a markdown body before the JSON block.")

    return markdown_content, json_content


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "topic",
        help="topic name (e.g. subreddits, magazines, conferences, partners, influencers, competitor_intel, regulatory)",
    )
    src = parser.add_mutually_exclusive_group()
    src.add_argument("--from", dest="source", help="path to a file containing the agent's transcript")
    src.add_argument("--text", help="agent transcript inline (e.g. from pbpaste / xclip)")
    parser.add_argument(
        "--workdir",
        default=".",
        help="research repo root (default: current working directory)",
    )
    args = parser.parse_args()

    if args.text is not None:
        transcript = args.text
    elif args.source:
        transcript = Path(args.source).read_text(encoding="utf-8")
    else:
        transcript = sys.stdin.read()

    markdown_raw, json_raw = extract_blocks(transcript)
    markdown_clean = clean_entities(markdown_raw)
    json_clean = clean_entities(json_raw)

    try:
        rows = json.loads(json_clean)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"error: JSON did not parse: {exc}\n"
            f"First 200 chars after entity cleanup:\n{json_clean[:200]}"
        )
    if not isinstance(rows, list):
        raise SystemExit("error: JSON top-level must be an array.")

    out_dir = Path(args.workdir).resolve() / "research" / args.topic
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f"{args.topic}.md"
    json_path = out_dir / f"{args.topic}.json"

    md_path.write_text(markdown_clean.rstrip() + "\n", encoding="utf-8")
    json_path.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    rel = out_dir.relative_to(Path(args.workdir).resolve())
    print(f"{args.topic}: {len(rows)} rows → {rel}/{args.topic}.{{md,json}}")


if __name__ == "__main__":
    main()
