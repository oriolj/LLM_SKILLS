#!/usr/bin/env python3
"""Branded QR code as SVG: rounded modules, rounded finder eyes, a logo in the
centre, error correction H. Pure SVG output (print-ready); render PNGs with
rsvg-convert and check them with verify_qr.sh.

    python3 -m venv /tmp/qrvenv && /tmp/qrvenv/bin/pip install segno
    /tmp/qrvenv/bin/python branded_qr.py https://go.example.com/flyer \\
        --logo brand/logo.svg --ink '#1B4C36' --out flyer-qr.svg
    rsvg-convert -w 2048 -h 2048 flyer-qr.svg -o flyer-qr.png
    ./verify_qr.sh flyer-qr.svg https://go.example.com/flyer

The logo is embedded, never redrawn: an SVG is inlined as a nested <svg>, a
PNG/JPEG as a data: URI. Defaults are the ones that decoded at 150 px and as a
blurred, rotated, noisy JPEG (Panotxa talk card, 2026-10-26).
"""

from __future__ import annotations

import argparse
import base64
import mimetypes
import re
from pathlib import Path

import segno


def logo_element(path: Path, x: float, size: float) -> str:
    if path.suffix.lower() == ".svg":
        svg = path.read_text()
        match = re.search(r'viewBox="([^"]+)"', svg)
        if not match:
            raise SystemExit(f"{path}: the logo SVG needs a viewBox")
        body = svg[svg.index(">", svg.index("<svg")) + 1 : svg.rindex("</svg>")]
        return (
            f'<svg x="{x:.3f}" y="{x:.3f}" width="{size:.3f}" height="{size:.3f}" '
            f'viewBox="{match.group(1)}">\n{body.strip()}\n</svg>'
        )
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    data = base64.b64encode(path.read_bytes()).decode()
    return (
        f'<image x="{x:.3f}" y="{x:.3f}" width="{size:.3f}" height="{size:.3f}" '
        f'href="data:{mime};base64,{data}" preserveAspectRatio="xMidYMid meet"/>'
    )


def build(args: argparse.Namespace) -> str:
    qr = segno.make(args.url, error="h", micro=False, boost_error=False)
    matrix = [list(row) for row in qr.matrix]
    n = len(matrix)
    m = args.margin
    size = n + 2 * m
    finders = [(0, 0), (n - 7, 0), (0, n - 7)]

    def in_finder(x: int, y: int) -> bool:
        return any(fx <= x < fx + 7 and fy <= y < fy + 7 for fx, fy in finders)

    logo_w = n * args.logo_share if args.logo else 0.0
    lo = (n - logo_w) / 2 - args.logo_clear
    hi = (n + logo_w) / 2 + args.logo_clear

    def under_logo(x: int, y: int) -> bool:
        return bool(args.logo) and x + 1 > lo and x < hi and y + 1 > lo and y < hi

    pad = (1 - args.dot) / 2
    shapes = []
    for fx, fy in finders:
        ox, oy = fx + m, fy + m
        # A 7x7 rounded ring (outer minus a 5x5 hole), then the 3x3 pupil:
        # scanners find the code by these, so they stay solid squares, only rounded.
        shapes.append(
            f'<path fill-rule="evenodd" d="'
            f"M{ox + 2},{oy} h3 a2,2 0 0 1 2,2 v3 a2,2 0 0 1 -2,2 h-3 a2,2 0 0 1 -2,-2 v-3 a2,2 0 0 1 2,-2 z "
            f"M{ox + 2.3},{oy + 1} h2.4 a1.3,1.3 0 0 1 1.3,1.3 v2.4 a1.3,1.3 0 0 1 -1.3,1.3 h-2.4 "
            f'a1.3,1.3 0 0 1 -1.3,-1.3 v-2.4 a1.3,1.3 0 0 1 1.3,-1.3 z"/>'
        )
        shapes.append(f'<rect x="{ox + 2}" y="{oy + 2}" width="3" height="3" rx="0.9"/>')
    for y, row in enumerate(matrix):
        for x, dark in enumerate(row):
            if dark and not in_finder(x, y) and not under_logo(x, y):
                shapes.append(
                    f'<rect x="{x + m + pad:.3f}" y="{y + m + pad:.3f}" '
                    f'width="{args.dot}" height="{args.dot}" rx="{args.radius}"/>'
                )

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
        f'width="{size * 10}" height="{size * 10}" role="img" aria-label="QR: {args.url}">',
        f'<rect width="{size}" height="{size}" fill="{args.paper}"/>',
        f'<g fill="{args.ink}">',
        *shapes,
        "</g>",
    ]
    if args.logo:
        parts.append(logo_element(Path(args.logo), m + (n - logo_w) / 2, logo_w))
    parts.append("</svg>")
    print(f"{args.out}: version {qr.version}, {n}x{n} modules, error {qr.error}")
    return "\n".join(parts) + "\n"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("url", help="what the QR holds: the short link, never the long target")
    p.add_argument("--out", required=True, help="output .svg")
    p.add_argument("--logo", help="logo file (.svg preferred; .png/.jpg embedded)")
    p.add_argument("--ink", default="#000000", help="module colour, dark (default black)")
    p.add_argument("--paper", default="#FFFFFF", help="background, light (default white)")
    p.add_argument("--logo-share", type=float, default=0.22, help="logo width / symbol width (max ~0.25)")
    p.add_argument("--logo-clear", type=float, default=1.0, help="empty modules around the logo")
    p.add_argument("--dot", type=float, default=0.88, help="module size, 1 = touching")
    p.add_argument("--radius", type=float, default=0.30, help="module corner radius (0.44 = circle)")
    p.add_argument("--margin", type=int, default=4, help="quiet zone in modules (4 is the standard)")
    args = p.parse_args()
    if args.logo_share > 0.25:
        raise SystemExit("--logo-share above 0.25 eats too much of error correction H's 30 %")
    if args.margin < 4:
        raise SystemExit("--margin below 4 modules breaks scanners next to other print")
    Path(args.out).write_text(build(args))


if __name__ == "__main__":
    main()
