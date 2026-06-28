#!/usr/bin/env python3
"""Assemble the whole growth-research repo into one polished, indexed PDF.

Run from the workdir root (after the markdown slices + GROWTH_RESEARCH.md exist):

    python3 scripts/build_pdf.py                # -> <Product>-Growth-Research.pdf
    python3 scripts/build_pdf.py out.pdf        # explicit output path

What it produces:
  - a branded cover page,
  - a clickable Table of Contents with real page numbers (dotted leaders),
  - one chapter per slice, each starting on a new page, numbered,
  - portrait pages for narrative chapters, landscape for table-heavy ones,
  - styled tables with repeating headers, a running footer with page numbers.

Source of truth stays the markdown; this is a derived deliverable — re-run anytime.

OPTIONAL LANGUAGE / I18N
------------------------
Drop a `pdf.config.json` in the workdir root to localize the chrome WITHOUT editing
this script — used to ship the same deck in another language (e.g. a Spanish edition
built from translated markdown). All keys are optional; anything omitted falls back to
the English default. See references/translating-the-deck.md for the full workflow.

    {
      "product": "GuitarGiro Subscriptions",
      "output": "GuitarGiro-Investigacion-de-Crecimiento-ES.pdf",
      "chapter_titles": {                      // override the auto/clean titles per topic
        "__exec__": "Resumen ejecutivo y plan de acción",
        "pricing": "Precios y empaquetado",
        "competitor_intel": "Inteligencia competitiva"
      },
      "layouts": { "competitor_intel": "portrait" },   // override portrait/landscape
      "strings": {
        "kicker": "Investigación de Go-to-Market",
        "subtitle": "Informe de investigación de crecimiento — …",
        "contents": "Contenido",
        "chapter": "Capítulo",
        "footer_suffix": "— Investigación de crecimiento",
        "slices_word": "áreas de investigación",
        "rows_word": "filas",
        "generated": "Generado el",
        "edition_note": "Edición en español (España)",
        "date_template": "{day} de {month} de {year}",
        "months": ["enero","febrero","marzo","abril","mayo","junio","julio",
                   "agosto","septiembre","octubre","noviembre","diciembre"]
      }
    }

Dependencies: weasyprint + markdown. They are heavier than openpyxl (need pango/
cairo). If they aren't importable, install into a throwaway venv:

    python3 -m venv /tmp/pdfvenv && /tmp/pdfvenv/bin/pip install weasyprint markdown
    /tmp/pdfvenv/bin/python scripts/build_pdf.py
"""
from __future__ import annotations
import sys, re, html, json, datetime
from pathlib import Path

try:
    import markdown
    from weasyprint import HTML
except ModuleNotFoundError as e:
    sys.exit(
        f"missing dependency: {e.name}\n"
        "Install into a venv, then re-run with that venv's python:\n"
        "  python3 -m venv /tmp/pdfvenv && /tmp/pdfvenv/bin/pip install weasyprint markdown\n"
        "  /tmp/pdfvenv/bin/python scripts/build_pdf.py"
    )

ROOT = Path.cwd()

# Preferred chapter order + clean (English) title + page layout. Topics not listed here
# but present on disk are appended (landscape, title-cased). "portrait" suits prose-heavy
# chapters; "landscape" gives wide tables room. Titles/layouts are overridable via
# pdf.config.json (chapter_titles / layouts) for other-language editions.
TOPIC_META = {
    "pricing":          ("Pricing & Packaging Strategy", "portrait"),
    "competitor_intel": ("Competitor Intelligence",       "landscape"),
    "partners":         ("Partner & Channel Ecosystem",   "landscape"),
    "subreddits":       ("Subreddits",                     "landscape"),
    "magazines":        ("Magazines & Trade Press",        "landscape"),
    "conferences":      ("Conferences & Events",           "landscape"),
    "influencers":      ("Influencers & KOLs",             "landscape"),
    "regulatory":       ("Regulatory Tailwinds",           "portrait"),
}
ORDER = ["pricing", "competitor_intel", "partners", "subreddits",
         "magazines", "conferences", "influencers", "regulatory"]

# English defaults for every localizable string (overridden by pdf.config.json "strings").
DEFAULT_STRINGS = {
    "kicker": "Go-to-Market Research",
    "subtitle": ("Growth research deck — where to advertise, who to partner with, "
                 "who moves opinion, what the competition looks like, which regulations "
                 "open windows, and what to charge."),
    "contents": "Contents",
    "chapter": "Chapter",
    "exec_title": "Executive Summary & Playbook",
    "footer_suffix": "— Growth Research",
    "slices_word": "research slices",
    "rows_word": "rows",
    "generated": "Generated",
    "edition_note": "",
    "date_template": "{day} {month} {year}",
    "months": None,   # None -> use %B English month name
}


def first_h1(text: str) -> str | None:
    for line in text.splitlines():
        if line.lstrip().startswith("# "):
            return line.lstrip()[2:].strip()
    return None


def slugify(s: str, n: int) -> str:
    return f"ch{n}-" + re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:50]


def build_chapter(title, md_text, layout, idx, conv, chapter_word):
    """Render one markdown file into a chapter <section> and a TOC entry."""
    lines = md_text.splitlines()
    if lines and lines[0].lstrip().startswith("# "):   # drop the file's own H1
        lines = lines[1:]
    conv.reset()
    body = conv.convert("\n".join(lines))
    cid = slugify(title, idx)
    secs: list[tuple[str, str]] = []

    def add_id(m, _c=[0]):
        t = html.unescape(re.sub("<.*?>", "", m.group(1))).strip()
        sid = f"{cid}-s{_c[0]}"; _c[0] += 1
        secs.append((t, sid))
        return f'<h2 id="{sid}">{m.group(1)}</h2>'

    body = re.sub(r"<h2>(.*?)</h2>", add_id, body, flags=re.DOTALL)
    section = (
        f'<section class="chapter {layout}" id="{cid}">'
        f'<div class="chnum">{html.escape(chapter_word)} {idx}</div>'
        f'<h1>{html.escape(title)}</h1>{body}</section>'
    )
    return section, (idx, title, cid, secs)


def main() -> None:
    out_arg = Path(sys.argv[1]) if len(sys.argv) > 1 else None

    # optional i18n config
    cfg = {}
    cfg_path = ROOT / "pdf.config.json"
    if cfg_path.exists():
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    S = {**DEFAULT_STRINGS, **cfg.get("strings", {})}
    title_over = cfg.get("chapter_titles", {})
    layout_over = cfg.get("layouts", {})

    # derive product name: config > GROWTH_RESEARCH.md H1 > workdir name
    summary_path = ROOT / "GROWTH_RESEARCH.md"
    product = cfg.get("product") or ROOT.name.replace("-", " ").title()
    if not cfg.get("product") and summary_path.exists():
        h = first_h1(summary_path.read_text(encoding="utf-8"))
        if h:
            product = re.split(r"\s+[—-]\s+", h)[0].strip()

    out = out_arg or (ROOT / cfg.get("output", re.sub(r"[^A-Za-z0-9]+", "-", product).strip("-") + "-Growth-Research.pdf"))

    # assemble chapter list: exec summary first, then slices in ORDER, then extras
    chapters: list[tuple[str, Path, str]] = []
    if summary_path.exists():
        exec_title = title_over.get("__exec__", S["exec_title"])
        chapters.append((exec_title, summary_path, layout_over.get("__exec__", "portrait")))
    present = {p.parent.name for p in ROOT.glob("research/*/*.md")}
    for topic in ORDER + sorted(present - set(ORDER)):
        md_file = ROOT / "research" / topic / f"{topic}.md"
        if md_file.exists():
            d_title, d_layout = TOPIC_META.get(topic, (topic.replace("_", " ").title(), "landscape"))
            title = title_over.get(topic, d_title)
            layout = layout_over.get(topic, d_layout)
            chapters.append((title, md_file, layout))
    if not chapters:
        sys.exit("nothing to build: no GROWTH_RESEARCH.md and no research/<topic>/<topic>.md found")

    conv = markdown.Markdown(extensions=["tables", "fenced_code", "sane_lists", "attr_list"])
    chapter_html, toc = [], []
    for i, (title, md_file, layout) in enumerate(chapters, 1):
        section, entry = build_chapter(title, md_file.read_text(encoding="utf-8"), layout, i, conv, S["chapter"])
        chapter_html.append(section)
        toc.append(entry)

    toc_rows = []
    for i, title, cid, secs in toc:
        toc_rows.append(
            f'<div class="toc-chap"><a href="#{cid}"><span class="tc-n">{i}</span>'
            f'<span class="tc-t">{html.escape(title)}</span></a></div>'
        )
        for t, sid in secs:
            toc_rows.append(f'<div class="toc-sec"><a href="#{sid}">{html.escape(t)}</a></div>')

    # cover stats. Row counts come from this repo's JSONs, or (for a translated mirror
    # that ships markdown only) from the sibling source repo named in config "rows_from".
    rows_root = ROOT
    if cfg.get("rows_from"):
        rows_root = (ROOT / cfg["rows_from"]).resolve()
    n_rows = 0
    for jf in rows_root.glob("research/*/*.json"):
        try:
            n_rows += len(json.loads(jf.read_text(encoding="utf-8")))
        except Exception:
            pass
    n_slices = len(present)

    d = datetime.date.today()
    month = S["months"][d.month - 1] if S["months"] else d.strftime("%B")
    today = S["date_template"].format(day=d.day, month=month, year=d.year)

    prod_css = product.replace("\\", "\\\\").replace('"', '\\"')
    footer_left = f'{prod_css} {S["footer_suffix"]}'.strip()
    meta_bits = [f'{n_slices} {html.escape(S["slices_word"])} · {n_rows} {html.escape(S["rows_word"])}']
    if S["edition_note"]:
        meta_bits.append(html.escape(S["edition_note"]))
    meta_bits.append(f'{html.escape(S["generated"])} {today}')
    meta_html = "<br>".join(meta_bits)

    css = f"""
@page {{ size: A4 portrait; margin: 18mm 15mm 16mm 15mm;
  @bottom-left {{ content: "{footer_left}"; font: 7.5pt 'Helvetica',sans-serif; color:#9098a3; }}
  @bottom-right {{ content: counter(page); font: 8pt 'Helvetica',sans-serif; color:#5b6b80; }} }}
@page landscape {{ size: A4 landscape; }}
@page cover {{ margin:0; @bottom-left{{content:none;}} @bottom-right{{content:none;}} }}
@page toc {{ @bottom-left{{content:none;}} }}
* {{ box-sizing: border-box; }}
body {{ font: 10.5pt/1.5 'Helvetica','Arial',sans-serif; color:#1f2733; margin:0; }}
h1,h2,h3,h4 {{ color:#13243b; line-height:1.25; }}
.chapter {{ page-break-before: always; }}
.chapter.landscape {{ page: landscape; }}
.chapter.portrait {{ page: portrait; }}
.chapter h1 {{ font-size:23pt; margin:0 0 4pt; padding-bottom:7pt; border-bottom:3px solid #2563eb; }}
.chnum {{ font:600 9pt 'Helvetica',sans-serif; letter-spacing:.16em; text-transform:uppercase; color:#2563eb; margin-bottom:2pt; }}
h2 {{ font-size:14pt; margin:18pt 0 5pt; padding-top:3pt; border-top:1px solid #e6eaf0; }}
h3 {{ font-size:11.5pt; margin:12pt 0 3pt; color:#2b3a52; }}
h4 {{ font-size:10.5pt; margin:9pt 0 2pt; color:#3a4a63; }}
p {{ margin:0 0 7pt; }}
a {{ color:#2563eb; text-decoration:none; }}
ul,ol {{ margin:0 0 8pt; padding-left:18pt; }}
li {{ margin:1.5pt 0; }}
strong {{ color:#13243b; }}
code {{ font:8.5pt 'DejaVu Sans Mono',monospace; background:#f1f4f8; padding:.5pt 3pt; border-radius:3px; }}
blockquote {{ margin:8pt 0; padding:5pt 12pt; border-left:3px solid #93b4f5; background:#f5f8fe; color:#33445e; }}
table {{ width:100%; border-collapse:collapse; table-layout:fixed; margin:6pt 0 12pt; font-size:7.6pt; }}
.portrait table {{ font-size:8pt; }}
thead {{ display:table-header-group; }}
th,td {{ border:.5pt solid #d4dae3; padding:2.6pt 4pt; text-align:left; vertical-align:top;
  overflow-wrap:anywhere; word-break:break-word; }}
th {{ background:#13243b; color:#fff; font-weight:600; font-size:7.4pt; }}
tbody tr:nth-child(even) {{ background:#f4f7fb; }}
table a {{ word-break:break-all; }}
tr,img {{ page-break-inside:avoid; }}
.cover {{ page:cover; height:297mm; padding:48mm 26mm 26mm; color:#fff;
  background:linear-gradient(150deg,#0f2240 0%,#13243b 42%,#1f3a63 100%);
  display:flex; flex-direction:column; }}
.cover .kicker {{ font:600 11pt 'Helvetica',sans-serif; letter-spacing:.30em; text-transform:uppercase; color:#7fb0ff; }}
.cover h1 {{ color:#fff; font-size:38pt; line-height:1.1; margin:14mm 0 0; border:none; }}
.cover .sub {{ font-size:13.5pt; color:#c7d6ee; margin-top:8mm; max-width:150mm; }}
.cover .meta {{ margin-top:auto; font-size:10.5pt; color:#9fb6d8; line-height:1.7; }}
.cover .rule {{ width:70mm; height:4px; background:#2563eb; margin:11mm 0 0; }}
.toc {{ page:toc; page-break-before:always; }}
.toc h1 {{ font-size:24pt; border-bottom:3px solid #2563eb; padding-bottom:7pt; margin:0 0 12pt; }}
.toc-chap {{ margin:11pt 0 2pt; }}
.toc-chap a {{ display:flex; align-items:baseline; font-weight:700; font-size:11.5pt; color:#13243b; }}
.toc-chap .tc-n {{ width:9mm; color:#2563eb; }}
.toc-chap .tc-t {{ flex:1; }}
.toc-chap a::after {{ content: leader('. ') target-counter(attr(href), page); color:#5b6b80; font-weight:400; }}
.toc-sec {{ margin:1pt 0 1pt 9mm; }}
.toc-sec a {{ display:flex; font-size:9pt; color:#46556b; }}
.toc-sec a::after {{ content: leader('. ') target-counter(attr(href), page); color:#8a96a6; }}
"""

    doc = (
        f'<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body>'
        f'<section class="cover"><div class="kicker">{html.escape(S["kicker"])}</div>'
        f'<h1>{html.escape(product)}</h1><div class="rule"></div>'
        f'<div class="sub">{html.escape(S["subtitle"])}</div>'
        f'<div class="meta">{meta_html}</div></section>'
        f'<section class="toc"><h1>{html.escape(S["contents"])}</h1>{"".join(toc_rows)}</section>'
        f'{"".join(chapter_html)}</body></html>'
    )

    HTML(string=doc, base_url=str(ROOT)).write_pdf(str(out))
    print(f"wrote {out} ({len(chapters)} chapters)")


if __name__ == "__main__":
    main()
