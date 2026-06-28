#!/usr/bin/env python3
"""Generate a self-contained HTML explorer over the growth-research JSON sidecars.

Reads each ``research/<topic>/<topic>.json`` and produces:

    html/index.html                   ← landing page with one card per slice
    html/<topic>.html                 ← per-slice explorer (filters + charts + table)

Each HTML file inlines its data, so they work via double-click (no server).
Uses Tailwind CSS + Chart.js from CDN — no build step.

Run from the repo root:

    python3 scripts/build_html.py
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RESEARCH = REPO / "research"
HTML_DIR = REPO / "html"

TOPICS: dict[str, dict] = {
    "subreddits": {
        "title": "Subreddits",
        "icon": "💬",
        "tagline": "Where to advertise & engage on Reddit",
        "fields": [
            ("category", "Category"),
            ("subreddit", "Subreddit"),
            ("approx_subs", "Approx. subs"),
            ("fit", "Fit"),
            ("geography", "Geography"),
            ("angle", "Angle"),
            ("self_promo_flags", "Red flags"),
        ],
        "url_field": "url",
        "name_field": "subreddit",
        "filter_fields": [
            ("category", "Category"),
            ("fit", "Fit"),
            ("geography", "Geography"),
        ],
        "charts": [
            ("category", "By category", "bar"),
            ("fit", "By product surface", "doughnut"),
        ],
    },
    "magazines": {
        "title": "Magazines / Press",
        "icon": "📰",
        "tagline": "Where to buy ads & pitch press releases",
        "fields": [
            ("category", "Category"),
            ("outlet", "Outlet"),
            ("country", "Country"),
            ("fit", "Fit"),
            ("audience", "Audience"),
            ("reach", "Reach"),
            ("notes", "Notes"),
        ],
        "url_field": "url",
        "name_field": "outlet",
        "filter_fields": [
            ("category", "Category"),
            ("fit", "Fit"),
            ("country", "Country"),
        ],
        "charts": [
            ("category", "By category", "bar"),
            ("fit", "By product surface", "doughnut"),
        ],
    },
    "conferences": {
        "title": "Conferences & Events",
        "icon": "🎫",
        "tagline": "Where to exhibit, sponsor & speak",
        "fields": [
            ("category", "Category"),
            ("event", "Event"),
            ("dates", "Dates"),
            ("city", "City"),
            ("country", "Country"),
            ("fit", "Fit"),
            ("attendees", "Attendees"),
            ("sponsorship_range", "Sponsorship"),
            ("why_it_matters", "Why it matters"),
        ],
        "url_field": "url",
        "name_field": "event",
        "filter_fields": [
            ("category", "Category"),
            ("fit", "Fit"),
            ("country", "Country"),
        ],
        "charts": [
            ("category", "By category", "bar"),
            ("country", "By country", "doughnut"),
        ],
    },
    "partners": {
        "title": "Partners & Ecosystem",
        "icon": "🤝",
        "tagline": "Partners, channels, competitors, vendors",
        "fields": [
            ("category", "Category"),
            ("company", "Company"),
            ("what_they_do", "What they do"),
            ("role", "Role"),
            ("surface", "Surface"),
            ("geography", "Geography"),
            ("pitch", "Pitch"),
            ("partner_program_or_contact", "Program / contact"),
        ],
        "url_field": "url",
        "name_field": "company",
        "filter_fields": [
            ("category", "Category"),
            ("role", "Role"),
            ("surface", "Surface"),
            ("geography", "Geography"),
        ],
        "charts": [
            ("category", "By category", "bar"),
            ("role", "By role", "doughnut"),
        ],
    },
    "influencers": {
        "title": "Influencers / KOLs",
        "icon": "🎤",
        "tagline": "Named humans who shift buyer opinion",
        "fields": [
            ("category", "Category"),
            ("name", "Name"),
            ("handle", "Handle"),
            ("audience_size", "Audience size"),
            ("audience_description", "Audience"),
            ("fit", "Fit"),
            ("geography", "Geography"),
            ("engagement_angle", "Angle"),
            ("contact_path", "Contact"),
        ],
        "url_field": "url",
        "name_field": "name",
        "filter_fields": [
            ("category", "Category"),
            ("fit", "Fit"),
            ("geography", "Geography"),
        ],
        "charts": [
            ("category", "By category", "bar"),
            ("fit", "By product surface", "doughnut"),
        ],
    },
    "competitor_intel": {
        "title": "Competitor Intel",
        "icon": "⚔️",
        "tagline": "Pricing, funding, weaknesses to exploit",
        "fields": [
            ("category", "Category"),
            ("name", "Name"),
            ("founded_year", "Founded"),
            ("hq_country", "HQ"),
            ("employees_approx", "Employees"),
            ("revenue_or_funding", "Revenue / funding"),
            ("pricing_snapshot", "Pricing"),
            ("key_features", "Key features"),
            ("notable_customers", "Notable customers"),
            ("strengths", "Strengths"),
            ("weaknesses_to_exploit", "Weaknesses"),
            ("threat_level", "Threat"),
        ],
        "url_field": "url",
        "name_field": "name",
        "filter_fields": [
            ("category", "Category"),
            ("threat_level", "Threat"),
            ("hq_country", "HQ"),
        ],
        "charts": [
            ("threat_level", "By threat level", "doughnut"),
            ("category", "By category", "bar"),
        ],
    },
    "pricing": {
        "title": "Pricing & Packaging",
        "icon": "💰",
        "tagline": "Market scan, value prop, recommended tiers & strategy",
        "fields": [
            ("category", "Category"),
            ("item", "Item"),
            ("surface", "Surface"),
            ("price_point", "Price point"),
            ("billing_model", "Billing model"),
            ("value_metric", "Value metric"),
            ("target_segment", "Target segment"),
            ("positioning", "Positioning"),
            ("benchmark_anchor", "Benchmark anchor"),
            ("rationale", "Rationale"),
            ("risk_or_note", "Risk / note"),
            ("confidence", "Confidence"),
        ],
        "url_field": "url",
        "name_field": "item",
        "filter_fields": [
            ("category", "Category"),
            ("surface", "Surface"),
            ("billing_model", "Billing model"),
            ("confidence", "Confidence"),
        ],
        "charts": [
            ("category", "By category", "bar"),
            ("billing_model", "By billing model", "doughnut"),
        ],
    },
    "regulatory": {
        "title": "Regulatory Windows",
        "icon": "📜",
        "tagline": "Laws & deadlines that unlock budget",
        "fields": [
            ("category", "Category"),
            ("jurisdiction", "Jurisdiction"),
            ("regulation_name", "Regulation"),
            ("effective_date", "Effective date"),
            ("status", "Status"),
            ("summary", "Summary"),
            ("relevance_to_product", "Relevance"),
            ("compliance_burden_on", "Burden on"),
            ("sales_angle", "Sales angle"),
            ("risk_to_us", "Risk to us"),
            ("notes", "Notes"),
        ],
        "url_field": "url",
        "name_field": "regulation_name",
        "filter_fields": [
            ("category", "Category"),
            ("status", "Status"),
            ("jurisdiction", "Jurisdiction"),
            ("compliance_burden_on", "Burden"),
        ],
        "charts": [
            ("jurisdiction", "By jurisdiction", "doughnut"),
            ("status", "By status", "bar"),
        ],
    },
}


# Page template — uses {{NAME}} as placeholders (replaced via simple .replace()).
# We avoid str.format() so we don't have to double-escape every {} in the JS.
PAGE_TEMPLATE = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{TITLE}} — Esferaup Growth Research</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }
  th[data-sort] { cursor: pointer; user-select: none; }
  th[data-sort]:hover { background-color: rgb(226 232 240); }
  .filter-chip { transition: all 0.12s; }
  .filter-chip.active { background-color: rgb(79 70 229); color: white; border-color: rgb(79 70 229); }
  td { max-width: 320px; }
  td.angle, td.notes, td.summary, td.relevance, td.what_they_do, td.weaknesses_to_exploit, td.strengths, td.why_it_matters, td.audience_description, td.engagement_angle, td.pitch, td.sales_angle { white-space: normal; }
</style>
</head>
<body class="bg-slate-50 text-slate-900">

<div class="max-w-[1400px] mx-auto px-4 py-6">

<nav class="mb-4 text-sm">
  <a href="index.html" class="text-indigo-600 hover:text-indigo-800">← Esferaup Growth Research</a>
</nav>

<header class="mb-5 flex items-end justify-between flex-wrap gap-2">
  <div>
    <h1 class="text-3xl font-bold mb-1">{{ICON}} {{TITLE}}</h1>
    <p class="text-slate-600">{{TAGLINE}}</p>
  </div>
  <div class="text-xs text-slate-500">Source: <a href="../research/{{TOPIC}}/{{TOPIC}}.md" class="text-indigo-600 hover:underline">{{TOPIC}}.md</a> · <a href="../research/{{TOPIC}}/{{TOPIC}}.xlsx" class="text-indigo-600 hover:underline">{{TOPIC}}.xlsx</a></div>
</header>

{{STATS_ROW}}

<div class="grid grid-cols-1 md:grid-cols-2 gap-5 mb-6">
  {{CHART_BLOCKS}}
</div>

<div class="bg-white rounded-lg shadow-sm border border-slate-200 p-5 mb-5">
  <div class="flex items-center justify-between mb-3 flex-wrap gap-2">
    <h2 class="text-base font-semibold">Filters</h2>
    <div class="flex items-center gap-3">
      <input id="search" type="text" placeholder="Search across all fields…" class="px-3 py-2 border border-slate-300 rounded-md text-sm w-64" />
      <button id="clear-filters" class="px-3 py-2 text-sm text-indigo-600 hover:text-indigo-800 hover:bg-indigo-50 rounded">Clear</button>
      <span id="row-count" class="text-sm text-slate-600 font-medium"></span>
    </div>
  </div>
  <div id="filter-area" class="space-y-3"></div>
</div>

<div class="bg-white rounded-lg shadow-sm border border-slate-200 overflow-x-auto">
  <table class="w-full text-sm" id="data-table">
    <thead class="bg-slate-100 sticky top-0">
      <tr>{{TABLE_HEADERS}}</tr>
    </thead>
    <tbody id="table-body"></tbody>
  </table>
</div>

<p class="text-xs text-slate-500 mt-6">Regenerate: <code class="bg-slate-100 px-1 rounded">python3 scripts/build_html.py</code></p>

</div>

<script id="data" type="application/json">{{DATA_JSON}}</script>
<script>
const DATA = JSON.parse(document.getElementById('data').textContent);
const FIELDS = {{FIELDS_JS}};
const FILTER_FIELDS = {{FILTER_FIELDS_JS}};
const URL_FIELD = "{{URL_FIELD}}";
const NAME_FIELD = "{{NAME_FIELD}}";
const CHARTS = {{CHARTS_JS}};

const activeFilters = {};
FILTER_FIELDS.forEach(([k]) => activeFilters[k] = new Set());

let searchQuery = "";
let sortField = null;
let sortAsc = true;

const BADGE_COLORS = {
  // surface / fit
  "Pro": "bg-indigo-100 text-indigo-800",
  "Parents": "bg-emerald-100 text-emerald-800",
  "Both": "bg-violet-100 text-violet-800",
  "Adjacent": "bg-slate-100 text-slate-600",
  "Backend": "bg-amber-100 text-amber-800",
  // threat
  "High": "bg-rose-100 text-rose-800",
  "Medium": "bg-amber-100 text-amber-800",
  "Low": "bg-slate-100 text-slate-600",
  // status
  "In force": "bg-emerald-100 text-emerald-800",
  "Phased rollout": "bg-amber-100 text-amber-800",
  "Pending entry into force": "bg-amber-100 text-amber-800",
  "Proposal / draft": "bg-slate-100 text-slate-600",
  "Repealed": "bg-rose-100 text-rose-800",
  // burden
  "Buyer": "bg-emerald-100 text-emerald-800",
  "Us as SaaS": "bg-rose-100 text-rose-800",
  "Ecosystem partner": "bg-violet-100 text-violet-800",
};

const ROLE_COLORS = {
  "PARTNER": "bg-emerald-100 text-emerald-800",
  "CHANNEL": "bg-indigo-100 text-indigo-800",
  "COMPETITOR": "bg-rose-100 text-rose-800",
  "CUSTOMER": "bg-violet-100 text-violet-800",
  "VENDOR": "bg-amber-100 text-amber-800",
  "RED FLAG": "bg-rose-200 text-rose-900",
};

const BADGE_FIELDS = new Set(["fit","surface","role","threat_level","status","compliance_burden_on","confidence"]);

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
}

function colorBadge(value) {
  if (!value) return "<span class='text-slate-400'>—</span>";
  // Role can be combined ("PARTNER | CHANNEL")
  const parts = String(value).split(/\\s*\\|\\s*/);
  if (parts.length > 1) {
    return parts.map(colorBadge).join(' ');
  }
  let cls = BADGE_COLORS[value] || ROLE_COLORS[value];
  if (!cls) {
    for (const [k, v] of Object.entries(ROLE_COLORS)) {
      if (String(value).includes(k)) { cls = v; break; }
    }
  }
  if (!cls) cls = "bg-slate-100 text-slate-700";
  return `<span class="inline-block px-2 py-0.5 rounded text-xs font-medium ${cls}">${escapeHtml(value)}</span>`;
}

function uniqueValues(rows, field) {
  const vals = new Set();
  rows.forEach(r => { const v = r[field]; if (v) vals.add(v); });
  return [...vals].sort((a, b) => String(a).localeCompare(String(b)));
}

function renderFilters() {
  const area = document.getElementById("filter-area");
  area.innerHTML = "";
  FILTER_FIELDS.forEach(([field, label]) => {
    const values = uniqueValues(DATA, field);
    if (values.length === 0) return;
    const wrap = document.createElement("div");
    wrap.innerHTML = `<div class="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">${escapeHtml(label)}</div><div class="flex flex-wrap gap-1.5"></div>`;
    const chipBar = wrap.querySelector("div:last-child");
    values.forEach(v => {
      const chip = document.createElement("button");
      chip.className = "filter-chip px-2.5 py-1 rounded-full text-xs border border-slate-300 bg-white hover:border-indigo-400";
      chip.textContent = v;
      chip.onclick = () => {
        const set = activeFilters[field];
        if (set.has(v)) { set.delete(v); chip.classList.remove("active"); }
        else { set.add(v); chip.classList.add("active"); }
        renderTable();
      };
      chipBar.appendChild(chip);
    });
    area.appendChild(wrap);
  });
}

function filterRows() {
  return DATA.filter(row => {
    for (const [field, set] of Object.entries(activeFilters)) {
      if (set.size > 0 && !set.has(row[field])) return false;
    }
    if (searchQuery) {
      const blob = Object.values(row).join(" ").toLowerCase();
      if (!blob.includes(searchQuery.toLowerCase())) return false;
    }
    return true;
  });
}

function sortRows(rows) {
  if (!sortField) return rows;
  return [...rows].sort((a, b) => {
    const av = (a[sortField] || "").toString().toLowerCase();
    const bv = (b[sortField] || "").toString().toLowerCase();
    return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
  });
}

function renderTable() {
  const rows = sortRows(filterRows());
  document.getElementById("row-count").textContent = `${rows.length} / ${DATA.length} rows`;
  const body = document.getElementById("table-body");
  body.innerHTML = "";
  rows.forEach((row, idx) => {
    const tr = document.createElement("tr");
    tr.className = (idx % 2 === 0 ? "bg-white" : "bg-slate-50/60") + " border-t border-slate-100";
    tr.innerHTML = FIELDS.map(([key, label]) => {
      const v = row[key] || "";
      const cellCls = `px-3 py-2 align-top text-slate-700 ${key}`;
      if (key === NAME_FIELD && row[URL_FIELD] && row[URL_FIELD] !== "—") {
        return `<td class="${cellCls}"><a href="${escapeHtml(row[URL_FIELD])}" target="_blank" rel="noopener" class="text-indigo-600 hover:text-indigo-800 hover:underline font-medium">${escapeHtml(v)}</a></td>`;
      }
      if (BADGE_FIELDS.has(key)) {
        return `<td class="${cellCls}">${colorBadge(v)}</td>`;
      }
      return `<td class="${cellCls}">${escapeHtml(v)}</td>`;
    }).join("");
    body.appendChild(tr);
  });
}

function renderChart(canvasId, field, title, type) {
  const counts = {};
  DATA.forEach(r => {
    const v = r[field] || "—";
    counts[v] = (counts[v] || 0) + 1;
  });
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 14);
  const labels = entries.map(([k]) => k.length > 36 ? k.slice(0, 34) + "…" : k);
  const data = entries.map(([, v]) => v);
  const palette = ["#4f46e5","#0ea5e9","#10b981","#f59e0b","#ef4444","#8b5cf6","#ec4899","#14b8a6","#f97316","#3b82f6","#a855f7","#22c55e","#eab308","#64748b"];
  new Chart(document.getElementById(canvasId), {
    type,
    data: { labels, datasets: [{ data, backgroundColor: type === "doughnut" ? palette : palette[0], borderWidth: 0 }] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: type === "doughnut", position: "right", labels: { boxWidth: 10, font: { size: 11 } } },
        title: { display: false },
        tooltip: { callbacks: { label: (ctx) => `${ctx.label}: ${ctx.parsed.y ?? ctx.parsed}` } },
      },
      indexAxis: type === "bar" ? "y" : undefined,
      scales: type === "bar" ? { x: { beginAtZero: true, ticks: { precision: 0 } } } : undefined,
    },
  });
}

document.getElementById("search").addEventListener("input", e => {
  searchQuery = e.target.value;
  renderTable();
});

document.getElementById("clear-filters").addEventListener("click", () => {
  document.getElementById("search").value = "";
  searchQuery = "";
  Object.values(activeFilters).forEach(s => s.clear());
  document.querySelectorAll(".filter-chip.active").forEach(c => c.classList.remove("active"));
  renderTable();
});

document.querySelectorAll("th[data-sort]").forEach(th => {
  th.addEventListener("click", () => {
    const field = th.dataset.sort;
    if (sortField === field) sortAsc = !sortAsc;
    else { sortField = field; sortAsc = true; }
    document.querySelectorAll("th[data-sort] .sort-ind").forEach(s => s.textContent = "");
    th.querySelector(".sort-ind").textContent = sortAsc ? " ↑" : " ↓";
    renderTable();
  });
});

renderFilters();
renderTable();
CHARTS.forEach((c, i) => renderChart(`chart-${i}`, c[0], c[1], c[2]));
</script>

</body>
</html>"""


def safe_json(obj) -> str:
    """JSON dump safe to embed inside <script type="application/json">."""
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def py_to_js(arr) -> str:
    return safe_json([list(t) if isinstance(t, tuple) else t for t in arr])


def build_topic(topic: str, spec: dict) -> int:
    json_path = RESEARCH / topic / f"{topic}.json"
    if not json_path.exists():
        print(f"skip {topic}: no JSON at {json_path.relative_to(REPO)}")
        return 0
    rows = json.loads(json_path.read_text(encoding="utf-8"))

    # Stats row
    n_rows = len(rows)
    categories = sorted({r.get("category", "") for r in rows if r.get("category")})
    fit_field = None
    if rows:
        if "fit" in rows[0]:
            fit_field = "fit"
        elif "surface" in rows[0]:
            fit_field = "surface"
        elif "threat_level" in rows[0]:
            fit_field = "threat_level"
        elif "status" in rows[0]:
            fit_field = "status"
    fit_label = "Top surface"
    top_fit = "—"
    if fit_field:
        fit_counts: dict[str, int] = {}
        for r in rows:
            v = r.get(fit_field) or "—"
            fit_counts[v] = fit_counts.get(v, 0) + 1
        if fit_counts:
            top_fit = max(fit_counts, key=fit_counts.get)
            if fit_field == "threat_level":
                fit_label = "Top threat"
            elif fit_field == "status":
                fit_label = "Top status"

    stats_html = f"""<div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
      <div class="bg-white p-4 rounded-lg shadow-sm border border-slate-200">
        <div class="text-xs text-slate-500 uppercase tracking-wider">Entries</div>
        <div class="text-2xl font-bold text-indigo-600">{n_rows}</div>
      </div>
      <div class="bg-white p-4 rounded-lg shadow-sm border border-slate-200">
        <div class="text-xs text-slate-500 uppercase tracking-wider">Categories</div>
        <div class="text-2xl font-bold text-indigo-600">{len(categories)}</div>
      </div>
      <div class="bg-white p-4 rounded-lg shadow-sm border border-slate-200">
        <div class="text-xs text-slate-500 uppercase tracking-wider">{fit_label}</div>
        <div class="text-xl font-bold text-indigo-600">{top_fit}</div>
      </div>
      <div class="bg-white p-4 rounded-lg shadow-sm border border-slate-200">
        <div class="text-xs text-slate-500 uppercase tracking-wider">Markets</div>
        <div class="text-2xl font-bold text-indigo-600">ES + CA</div>
      </div>
    </div>"""

    # Chart blocks
    chart_blocks = ""
    for i, (_, title, _) in enumerate(spec["charts"]):
        chart_blocks += f"""<div class="bg-white p-5 rounded-lg shadow-sm border border-slate-200">
          <h3 class="text-sm font-semibold text-slate-700 mb-3">{title}</h3>
          <div style="position: relative; height: 280px;"><canvas id="chart-{i}"></canvas></div>
        </div>"""

    # Table headers
    headers_html = "".join(
        f'<th class="px-3 py-2 text-left text-xs font-semibold text-slate-700 uppercase tracking-wider whitespace-nowrap" data-sort="{k}">{label}<span class="sort-ind"></span></th>'
        for k, label in spec["fields"]
    )

    page = (PAGE_TEMPLATE
            .replace("{{TITLE}}", spec["title"])
            .replace("{{ICON}}", spec["icon"])
            .replace("{{TAGLINE}}", spec["tagline"])
            .replace("{{TOPIC}}", topic)
            .replace("{{STATS_ROW}}", stats_html)
            .replace("{{CHART_BLOCKS}}", chart_blocks)
            .replace("{{TABLE_HEADERS}}", headers_html)
            .replace("{{DATA_JSON}}", safe_json(rows))
            .replace("{{FIELDS_JS}}", py_to_js(spec["fields"]))
            .replace("{{FILTER_FIELDS_JS}}", py_to_js(spec["filter_fields"]))
            .replace("{{URL_FIELD}}", spec["url_field"])
            .replace("{{NAME_FIELD}}", spec["name_field"])
            .replace("{{CHARTS_JS}}", safe_json(spec["charts"])))

    HTML_DIR.mkdir(parents=True, exist_ok=True)
    (HTML_DIR / f"{topic}.html").write_text(page, encoding="utf-8")
    print(f"{topic}: {n_rows} rows → html/{topic}.html")
    return n_rows


def build_index() -> None:
    counts: dict[str, int] = {}
    for topic in TOPICS:
        p = RESEARCH / topic / f"{topic}.json"
        counts[topic] = len(json.loads(p.read_text(encoding="utf-8"))) if p.exists() else 0

    cards = ""
    for topic, spec in TOPICS.items():
        n = counts.get(topic, 0)
        cards += f"""<a href="{topic}.html" class="group block bg-white rounded-xl shadow-sm border border-slate-200 p-6 hover:shadow-lg hover:border-indigo-300 hover:-translate-y-0.5 transition-all">
          <div class="flex items-start justify-between mb-3">
            <div class="text-4xl">{spec['icon']}</div>
            <span class="text-xs font-semibold text-indigo-700 bg-indigo-50 px-2 py-1 rounded-full">{n} entries</span>
          </div>
          <h3 class="text-lg font-bold mb-1 group-hover:text-indigo-600">{spec['title']}</h3>
          <p class="text-sm text-slate-600 mb-4">{spec['tagline']}</p>
          <div class="text-sm font-medium text-indigo-600 group-hover:text-indigo-800">Explore →</div>
        </a>"""

    total = sum(counts.values())

    index_html = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Esferaup — Growth Research</title>
<script src="https://cdn.tailwindcss.com"></script>
<style> body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }} </style>
</head>
<body class="bg-gradient-to-br from-slate-50 via-white to-indigo-50 text-slate-900 min-h-screen">

<div class="max-w-6xl mx-auto px-4 py-12">

<header class="mb-10 text-center">
  <div class="inline-flex items-center gap-2 bg-white px-3 py-1 rounded-full text-xs font-semibold text-indigo-700 border border-indigo-200 mb-4 shadow-sm">
    <span class="w-2 h-2 bg-indigo-500 rounded-full animate-pulse"></span>
    Pre-launch · España · castellano + català
  </div>
  <h1 class="text-5xl font-bold mb-3 tracking-tight">Esferaup <span class="text-slate-400 font-normal">Growth Research</span></h1>
  <p class="text-lg text-slate-600 max-w-2xl mx-auto">
    SaaS by Litus para academias extraescolares y centros especializados de desarrollo infantil. <strong>{total}</strong> entradas analizadas en 7 dimensiones de go-to-market.
  </p>
</header>

<section class="mb-10 bg-white rounded-xl shadow-sm border border-slate-200 p-6">
  <h2 class="text-xl font-bold mb-4">📍 Producto, en una página</h2>
  <div class="grid md:grid-cols-2 gap-6">
    <div>
      <div class="inline-block bg-indigo-100 text-indigo-800 text-xs font-semibold px-2 py-1 rounded mb-2">Pro surface</div>
      <p class="text-sm text-slate-700"><strong>Buyer</strong>: director/a o titular del centro. <strong>Verticales</strong>: deporte (fútbol, tenis, natación, AAMM, gimnasia, escalada), música/artes/danza, idiomas (Cambridge/Trinity, chino), refuerzo/STEAM, y <strong>centros especializados</strong> (atención temprana, TEA, neurodiversidad, logopedia, psicopedagogía, terapia ocupacional, fisioterapia pediátrica).</p>
    </div>
    <div>
      <div class="inline-block bg-emerald-100 text-emerald-800 text-xs font-semibold px-2 py-1 rounded mb-2">Parents surface</div>
      <p class="text-sm text-slate-700"><strong>Usuario</strong>: madre/padre/tutor. <strong>Hook</strong>: visión 360° del desarrollo del niño/a — un único timeline cruzando todos los centros (deporte + música + terapia + escuela), propiedad de la familia, no del centro.</p>
    </div>
  </div>
</section>

<h2 class="text-2xl font-bold mb-5">🔍 Explora las 7 dimensiones</h2>
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 mb-10">
  {cards}
</div>

<section class="bg-white rounded-xl shadow-sm border border-slate-200 p-6 mb-6">
  <h2 class="text-xl font-bold mb-3">🎯 Top-3 movimientos prioritarios</h2>
  <ol class="space-y-3 text-sm">
    <li class="flex gap-3"><span class="flex-shrink-0 w-6 h-6 rounded-full bg-indigo-100 text-indigo-700 font-bold text-xs flex items-center justify-center">1</span><div><strong>Acreditar Esferaup como agente digitalizador del Kit Digital</strong> antes de Q3 2026 — convierte la objeción de precio en "cuándo llega el bono". Bono Seg. III 3.000 € cubre Esferaup al 100% para academias &lt;3 empleados.</div></li>
    <li class="flex gap-3"><span class="flex-shrink-0 w-6 h-6 rounded-full bg-indigo-100 text-indigo-700 font-bold text-xs flex items-center justify-center">2</span><div><strong>Pitch LOPIVI a centros deportivos / música</strong> con mensaje "tu próxima inspección puede ser este trimestre" — normativa ya en vigor, inspecciones en ramp 2025-2026.</div></li>
    <li class="flex gap-3"><span class="flex-shrink-0 w-6 h-6 rounded-full bg-indigo-100 text-indigo-700 font-bold text-xs flex items-center justify-center">3</span><div><strong>Triple pinza Catalunya TEA</strong>: AETAPI Palma (nov 2026, bienal — única hasta 2028) + Federació Catalana d'Autisme + Aprenem Autisme como founding customer.</div></li>
  </ol>
  <p class="text-xs text-slate-500 mt-4">Top-12 completo en <code class="bg-slate-100 px-1 rounded">GROWTH_RESEARCH.md</code></p>
</section>

<footer class="text-center text-xs text-slate-500 mt-12 pb-4">
  Source of truth: <code class="bg-slate-100 px-1 rounded">research/&lt;topic&gt;/&lt;topic&gt;.md</code> · Spreadsheets: <code class="bg-slate-100 px-1 rounded">.xlsx</code> · Regenerate HTML: <code class="bg-slate-100 px-1 rounded">python3 scripts/build_html.py</code>
</footer>

</div>
</body>
</html>"""

    HTML_DIR.mkdir(parents=True, exist_ok=True)
    (HTML_DIR / "index.html").write_text(index_html, encoding="utf-8")
    print(f"index: {total} total rows → html/index.html")


def main() -> None:
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    for topic, spec in TOPICS.items():
        build_topic(topic, spec)
    build_index()


if __name__ == "__main__":
    main()
