#!/usr/bin/env bash
# Decode a QR (SVG or PNG) the hard ways and require EXACTLY the expected text
# every time: large, card-size, tiny, greyscale, and a rotated + blurred + noisy
# low-quality JPEG (a phone photo of a print). Needs rsvg-convert (for SVG),
# ImageMagick (magick) and zbarimg.
#
#   verify_qr.sh flyer-qr.svg https://go.example.com/flyer
set -euo pipefail

src=${1:?usage: verify_qr.sh <qr.svg|qr.png> <expected text>}
want=${2:?usage: verify_qr.sh <qr.svg|qr.png> <expected text>}
for tool in magick zbarimg; do command -v "$tool" >/dev/null || { echo "missing: $tool" >&2; exit 2; }; done

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

if [[ $src == *.svg ]]; then
  command -v rsvg-convert >/dev/null || { echo "missing: rsvg-convert" >&2; exit 2; }
  rsvg-convert -w 2048 -h 2048 "$src" -o "$work/base.png"
else
  cp "$src" "$work/base.png"
fi

magick "$work/base.png" -resize 600x600 "$work/600.png"
magick "$work/base.png" -resize 300x300 "$work/300.png"
magick "$work/base.png" -resize 150x150 "$work/150.png"
magick "$work/base.png" -colorspace Gray "$work/grey.png"
magick "$work/base.png" -resize 300x300 -background white -rotate 12 -blur 0x1.2 \
  -attenuate 0.4 +noise Gaussian -quality 40 "$work/photo.jpg"

fail=0
for f in base.png 600.png 300.png 150.png grey.png photo.jpg; do
  got=$(zbarimg -q --raw "$work/$f" 2>/dev/null || true)
  if [[ $got == "$want" ]]; then
    echo "ok    $f"
  else
    echo "FAIL  $f -> ${got:-<nothing decoded>}"
    fail=1
  fi
done
exit $fail
