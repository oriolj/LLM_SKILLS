#!/usr/bin/env node
// Render concept illustrations from one HTML file to transparent WebP, plus a
// contact sheet for review. The HTML shows one scene per `?s=<name>` inside a
// `#stage` element sized to the scene, and exposes `window.ready` (a promise
// that resolves once fonts and images are loaded).
//
// Usage:
//   node render-illustrations.mjs --html illustrations.html \
//     --scenes hero:1600x1000,sheet:1200x900 --out ./out \
//     [--require /path/to/any/package.json]   # a project whose node_modules has playwright (or playwright-core)
//     [--chromium /usr/bin/chromium] [--fonts "Lexend,Roboto,Material Icons"]
//     [--icon-font "Material Icons"]           # default: the --fonts entry containing Icons/Symbols
//     [--query lang=ca]                        # extra query string appended to ?s=<scene>
//     [--lang ca]                              # shorthand for --query lang=ca
//     [--min-text 20]                          # smallest text allowed, in CSS px at 1x
//
// The page is opened with goto('file://...'), never setContent: a setContent
// page cannot load file:// fonts and silently falls back.
//
// Writes <out>/<scene>.webp at the exact size, <out>/<scene>@2x.png and
// <out>/contact-sheet.png (every scene over white). Automated checks, printed
// per scene: every listed font family has a loaded face (a missing one means
// the text rendered in a fallback), no element's text overflows its box, and
// a list of text smaller than --min-text (a decision, not always an error:
// a phone's clock may be small on purpose). A missing icon font is FATAL
// (exit 1): icons would render as ligature text such as "CHEVRON_RIGHT".
// Box shadows that reach the stage edge are reported (they get clipped into
// hard rectangles). It cannot judge composition: look at the contact sheet.
import { createRequire } from 'module';
import { execFileSync } from 'child_process';
import fs from 'fs';
import path from 'path';

const arg = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const html = path.resolve(arg('html'));
const out = path.resolve(arg('out', 'out'));
const scenes = arg('scenes').split(',').map(s => { const [n, wh] = s.split(':'); const [w, h] = wh.split('x').map(Number); return { n, w, h }; });
const req = createRequire(path.resolve(arg('require', 'package.json')));
let chromium;
try { ({ chromium } = req('playwright')); } catch { ({ chromium } = req('playwright-core')); }
const fonts = arg('fonts', '').split(',').map(s => s.trim()).filter(Boolean);
const iconFont = arg('icon-font', fonts.find(f => /icons|symbols/i.test(f)) || '');
const query = arg('query', '') || (arg('lang') ? 'lang=' + arg('lang') : '');
const minText = Number(arg('min-text', 0));
fs.mkdirSync(out, { recursive: true });

const b = await chromium.launch({ executablePath: arg('chromium', '/usr/bin/chromium') });
const p = await b.newPage({ viewport: { width: Math.max(...scenes.map(s => s.w)), height: Math.max(...scenes.map(s => s.h)) }, deviceScaleFactor: 2 });
let problems = 0, fatal = 0;
for (const s of scenes) {
  await p.goto('file://' + html + '?s=' + s.n + (query ? '&' + query.replace(/^[?&]/, '') : ''));
  await p.evaluate(() => window.ready);
  await p.waitForTimeout(200);
  const report = await p.evaluate(({ fonts, minText, iconFont }) => {
    const loaded = new Set([...document.fonts].filter(f => f.status === 'loaded').map(f => f.family.replace(/["']/g, '')));
    const missing = fonts.filter(f => !loaded.has(f));
    const iconMissing = !!iconFont && !loaded.has(iconFont);
    const stage = document.getElementById('stage');
    const sr0 = stage.getBoundingClientRect();
    const overflow = [], tiny = [], clipped = [];
    for (const el of stage.querySelectorAll('*')) {
      const sh = getComputedStyle(el).boxShadow;
      if (!sh || sh === 'none') continue;
      // Each outer shadow layer "color Xpx Ypx Bpx Spx": count the visibly dark
      // part as spread + half the blur, shifted by the offset.
      const r = el.getBoundingClientRect();
      if (!r.width || !r.height) continue;   // element of another (hidden) scene
      let hit = false;
      for (const layer of sh.split(/,(?![^(]*\))/)) {
        if (/inset/.test(layer)) continue;
        const [x = 0, y = 0, b = 0, sp = 0] = (layer.match(/-?\d+(\.\d+)?px/g) || []).map(parseFloat);
        const e = sp + b / 2;
        if (r.left + x - e < sr0.left || r.right + x + e > sr0.right || r.top + y - e < sr0.top || r.bottom + y + e > sr0.bottom) hit = true;
      }
      if (hit)
        clipped.push((el.className || el.tagName).toString().slice(0, 30));
    }
    for (const el of stage.querySelectorAll('*')) {
      const r = el.getBoundingClientRect();
      if (!r.width || getComputedStyle(el).visibility === 'hidden') continue;
      const own = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
      if (!own) continue;
      if (el.scrollWidth > el.clientWidth + 1 && getComputedStyle(el).overflow !== 'visible') overflow.push(el.textContent.trim().slice(0, 40));
      const fs = parseFloat(getComputedStyle(el).fontSize);
      if (minText && fs < minText && !el.closest('.mi')) tiny.push(`${fs}px: ${el.textContent.trim().slice(0, 30)}`);
    }
    const sr = stage.getBoundingClientRect();
    return { missing, iconMissing, overflow, clipped: [...new Set(clipped)], tiny: [...new Set(tiny)], size: [Math.round(sr.width), Math.round(sr.height)] };
  }, { fonts, minText, iconFont });
  const bad = report.missing.length + report.overflow.length + report.tiny.length + report.clipped.length + (report.size[0] !== s.w || report.size[1] !== s.h ? 1 : 0);
  problems += bad;
  if (report.iconMissing) fatal++;
  console.log(`${s.n}: stage ${report.size.join('x')} (want ${s.w}x${s.h})` +
    (report.iconMissing ? ` | ICON FONT "${iconFont}" NOT LOADED (icons render as text)` : '') +
    (report.missing.length ? ` | FONTS NOT LOADED: ${report.missing.join(', ')}` : '') +
    (report.clipped.length ? ` | SHADOW REACHES STAGE EDGE: ${report.clipped.join(' / ')}` : '') +
    (report.overflow.length ? ` | OVERFLOW: ${report.overflow.join(' / ')}` : '') +
    (report.tiny.length ? ` | TEXT < ${minText}px: ${report.tiny.join(' / ')}` : '') + (bad ? '' : ' | ok'));
  const png = path.join(out, `${s.n}@2x.png`);
  await p.locator('#stage').screenshot({ path: png, omitBackground: true });
  execFileSync('ffmpeg', ['-loglevel', 'error', '-y', '-i', png, '-vf', `scale=${s.w}:${s.h}:flags=lanczos,format=rgba`,
    '-c:v', 'libwebp', '-pix_fmt', 'yuva420p', '-quality', '88', path.join(out, `${s.n}.webp`)]);
}
await b.close();

// Contact sheet: every scene scaled to 800 px wide, stacked on white.
const inputs = scenes.flatMap(s => ['-i', path.join(out, `${s.n}.webp`)]);
const H = scenes.reduce((a, s) => a + Math.round(800 * s.h / s.w) + 20, 20);
let fc = `color=white:s=840x${H}[bg];`, last = 'bg', y = 20;
scenes.forEach((s, i) => { const h = Math.round(800 * s.h / s.w); fc += `[${i}]scale=800:${h}[s${i}];[${last}][s${i}]overlay=20:${y}[o${i}];`; last = `o${i}`; y += h + 20; });
execFileSync('ffmpeg', ['-loglevel', 'error', '-y', ...inputs, '-filter_complex', fc.replace(/;$/, ''), '-map', `[${last}]`, '-frames:v', '1', path.join(out, 'contact-sheet.png')]);
console.log(`${problems ? problems + ' automated problem(s)' : 'automated checks passed'}; now look at ${path.join(out, 'contact-sheet.png')}`);
if (fatal) { console.error(`FATAL: icon font "${iconFont}" missing in ${fatal} scene(s); the images show ligature names, not icons.`); process.exit(1); }
