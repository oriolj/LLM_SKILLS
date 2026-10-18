#!/usr/bin/env python3
"""Synchronize self-contained bot protocol/template copies; --check never writes."""
import argparse
from pathlib import Path
import sys


def synchronize(root: Path, check: bool = True) -> int:
    root = root.resolve()
    different = []
    copies = []
    # Preflight both pairs before any write. A symlinked ancestor is as unsafe
    # as a symlink at the leaf, even when it resolves elsewhere inside root.
    for relative in ("references/protocol.md", "templates/ticket.md"):
        source = root / "skills/development-tickets" / relative
        target = root / "bots/development-ticket-triage" / relative
        for path in (source, target):
            if not path.resolve().is_relative_to(root):
                raise ValueError(f"Refusing path outside repository: {path}")
            current = path
            while current != root:
                if current.is_symlink():
                    raise ValueError(f"Refusing symlink path or ancestor: {current}")
                current = current.parent
        expected = source.read_bytes()
        if not target.exists() or target.read_bytes() != expected:
            different.append(relative)
            copies.append((target, expected))
    if not check:
        for target, expected in copies:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(expected)
    if different and check:
        print("Generated bot copies diverge: " + ", ".join(different), file=sys.stderr)
        return 1
    print("Protocol/template copies match." if check else "Protocol/template copies synchronized.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report drift without modifying files")
    args = parser.parse_args()
    try:
        return synchronize(Path(__file__).resolve().parents[1], check=args.check)
    except (OSError, ValueError) as error:
        print(f"Cannot synchronize protocol: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
