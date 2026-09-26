#!/usr/bin/env node
// Render concept illustrations from one HTML file to transparent WebP, plus a
// contact sheet for review. The HTML shows one scene per `?s=<name>` inside a
// `#stage` element sized to the scene, and exposes `window.ready` (a promise
// that resolves once fonts and images are loaded).
//
// Usage:
//   node render-illustrations.mjs --html illustrations.html \
//     --scenes hero:1600x1000,sheet:1200x900 --out ./out \
//     [--require /path/to/any/package.json]   # a project whose node_modules has playwright
//     [--chromium /usr/bin/chromium] [--fonts "Lexend,Roboto,Material Icons"]
//     [--min-text 20]                          # smallest text allowed, in CSS px at 1x
//
// Writes <out>/<scene>.webp at the exact size, <out>/<scene>@2x.png and
// <out>/contact-sheet.png (every scene over white). Automated checks, printed
// per scene: every listed font family has a loaded face (a missing one means
// the text rendered in a fallback), no element's text overflows its box, and
// a list of text smaller than --min-text (a decision, not always an error:
// a phone's clock may be small on purpose). It cannot judge composition:
// look at the contact sheet.
import { createRequire } from 'module';
import { execFileSync } from 'child_process';
import fs from 'fs';
import path from 'path';

const arg = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const html = path.resolve(arg('html'));
const out = path.resolve(arg('out', 'out'));
const scenes = arg('scenes').split(',').map(s => { const [n, wh] = s.split(':'); const [w, h] = wh.split('x').map(Number); return { n, w, h }; });
const req = createRequire(path.resolve(arg('require', 'package.json')));
const { chromium } = req('playwright');
const fonts = arg('fonts', '').split(',').map(s => s.trim()).filter(Boolean);
const minText = Number(arg('min-text', 0));
fs.mkdirSync(out, { recursive: true });

const b = await chromium.launch({ executablePath: arg('chromium', '/usr/bin/chromium') });
const p = await b.newPage({ viewport: { width: Math.max(...scenes.map(s => s.w)), height: Math.max(...scenes.map(s => s.h)) }, deviceScaleFactor: 2 });
let problems = 0;
for (const s of scenes) {
  await p.goto('file://' + html + '?s=' + s.n);
  await p.evaluate(() => window.ready);
  await p.waitForTimeout(200);
  const report = await p.evaluate(({ fonts, minText }) => {
    const loaded = new Set([...document.fonts].filter(f => f.status === 'loaded').map(f => f.family.replace(/["']/g, '')));
    const missing = fonts.filter(f => !loaded.has(f));
    const stage = document.getElementById('stage');
    const overflow = [], tiny = [];
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
    return { missing, overflow, tiny: [...new Set(tiny)], size: [Math.round(sr.width), Math.round(sr.height)] };
  }, { fonts, minText });
  const bad = report.missing.length + report.overflow.length + report.tiny.length + (report.size[0] !== s.w || report.size[1] !== s.h ? 1 : 0);
  problems += bad;
  console.log(`${s.n}: stage ${report.size.join('x')} (want ${s.w}x${s.h})` +
    (report.missing.length ? ` | FONTS NOT LOADED: ${report.missing.join(', ')}` : '') +
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
