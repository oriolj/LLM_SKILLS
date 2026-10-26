---
name: branded-qr-codes
description: Make nice, branded QR codes that still scan — rounded modules and finder eyes in the brand colour, the product's logo in the centre, an SVG for print and a PNG for screens — and prove they scan before anything is printed. Use when someone asks for "a nice QR", "a QR with our logo", "a rounded / styled / branded QR", a QR for a card, flyer, poster, packaging, slide or sticker, or when reviewing a QR a designer made. Ships scripts/branded_qr.py (segno → pure SVG, logo embedded, never redrawn) and scripts/verify_qr.sh (decodes at 2048/600/300/150 px, greyscale and as a degraded phone-photo JPEG, and requires the exact text every time).
---

# Branded QR codes

A QR code is a printed URL with no undo: once the cards are printed, whatever it
encodes is permanent. So the order is always: **decide what it encodes, style it
inside the limits below, prove it scans, then print a proof and scan that with
real phones.** Learned on Panotxa's talk cards (2026-10-26).

## What the QR encodes

- **A short link you control, never the long target.** A short link (Kutt, any
  redirector of yours) counts each scan and can be re-pointed after printing; the
  long URL with UTM tags can do neither, and makes a denser, harder code. The
  short link carries the UTM tags on its target, not in the QR.
- **No personal data, codes or tokens in it** — anyone can read a QR. A promo
  code is printed as text next to the QR (an app-store install drops every query
  parameter anyway, so the code could not survive the trip).
- Shorter text = fewer modules = bigger modules at the same print size. A
  40-character https URL at error correction H is version 5 (37 × 37).

## The limits that keep it scanning

| Rule | Why |
|---|---|
| **Error correction H** (30 %) whenever there is a logo | the logo covers modules; H rebuilds them. Never "boost" past what you need: a higher version only shrinks the modules |
| **Logo ≤ 22–25 % of the symbol's width** (≈ 5–6 % of the area) with **one module of empty space** around it, and no modules drawn under it | a bigger logo eats the 30 %; modules peeking from under a logo read as noise |
| **Never touch the three finder squares or the quiet zone**: the finders may be rounded, not replaced by icons or circles of another size; **4 modules of margin** on every side | scanners locate the code by the finders and the empty margin; most "pretty QR" failures are here |
| **Dark modules on a light background**, contrast of plain text or better; no inverted (light-on-dark) codes, no gradients across the modules | many phone scanners and older libraries only read dark-on-light |
| **Paint the background**: an explicit paper rectangle in the SVG | a transparent QR placed on a coloured or dark artwork stops decoding. The verify script's greyscale pass catches it: Panotxa's plain `qrencode` SVG (transparent) failed there, the branded one (white rect) passed |
| **Rounded modules at ~0.88 of the cell, radius ~0.3**; circles (radius 0.44) work too, but don't shrink below ~0.8 | the gaps make it pretty; too small and blur at print size merges or drops modules |
| **Print size ≥ 2 cm**, and roughly 10 cm per metre of scanning distance (slides, posters) | the 150 px test is about a 2.5 cm print |

Brand: take the ink colour from the brand's own tokens (the logo tile's colour
reads best), and **embed the real logo file** — the script inlines an SVG as a
nested `<svg>` or a PNG as a `data:` URI. Never redraw or re-trace a logo.

## Make it

```bash
python3 -m venv /tmp/qrvenv && /tmp/qrvenv/bin/pip install segno   # throwaway venv
/tmp/qrvenv/bin/python scripts/branded_qr.py https://go.example.com/flyer-gym \
    --logo brand/logo/logo.svg --ink '#1B4C36' --out flyer-gym-qr.svg
rsvg-convert -w 2048 -h 2048 flyer-gym-qr.svg -o flyer-gym-qr.png       # screens, slides
scripts/verify_qr.sh flyer-gym-qr.svg https://go.example.com/flyer-gym
```

Options: `--paper` (default white), `--logo-share` (default 0.22, refused above
0.25), `--logo-clear` (modules around the logo, default 1), `--dot`, `--radius`,
`--margin` (refused below 4). Output is deterministic: the same inputs give a
byte-identical SVG (checked against the Panotxa card).

Deliver both: the **SVG to the printer** (vector, scales without blur) and a
**2048 px PNG** for screens. Keep the generator command or a small script next
to the files in the project repo, so the code can be remade, and record the
sha256 of what was handed over.

## Prove it scans

`scripts/verify_qr.sh <qr.svg|png> <expected text>` decodes with `zbarimg` at
2048, 600, 300 and 150 px, in greyscale, and as a 300 px JPEG rotated 12°,
blurred, noisy, quality 40, and requires **exactly** the expected text every
time (a decoder that returns something else is a fail, not a pass). Needs
`rsvg-convert`, ImageMagick (`magick`) and `zbarimg`.

Then, still before the print run:

- **Look at it yourself** (open the PNG): logo centred, clear space visible,
  finders intact.
- **A printed proof at the real size, scanned with an iPhone camera and an
  Android camera** (and, if the audience will use it, from inside Instagram's or
  WhatsApp's in-app scanner). No script replaces this.
- Test scans hit the short link: they count as visits. Note them where the
  link's stats are read, so they are not reported as real scans.
- If the short link is new, make sure its database is backed up before the same-day
  print run.

## Reviewing a designer's QR

Run `verify_qr.sh` on their file first, then check the table: finders intact,
margin ≥ 4 modules, logo share, dark-on-light, a painted background, and that it
encodes the short link (decode it and compare), not a long URL or a generic
generator's tracking redirect (free "QR generator" sites often encode their own
redirect, which they can switch off or monetise later).
