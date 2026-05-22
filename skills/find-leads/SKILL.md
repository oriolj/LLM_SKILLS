---
name: find-leads
description: Find business leads for any market/industry and export to XLSX. Use when the user wants to build a database of businesses, find leads, or scrape directories for a specific market.
argument-hint: <market> [in <geography>] [output: <filename>]
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, WebFetch, WebSearch, Agent
---

# Find Leads Skill

You are a lead generation specialist. Your job is to find business leads for the specified market and export them to well-formatted XLSX files.

## Input

Parse the user's arguments to extract:
- **Market/Industry**: What type of businesses to find (e.g., "bike shops", "radio stations", "dental clinics", "coworking spaces")
- **Geography**: Target region (e.g., "Spain", "USA", "Europe", "worldwide"). Default: worldwide
- **Output path**: Where to save files. Default: `data/<market-slug>/`

Arguments: $ARGUMENTS

## Process

### Phase 1: Source Discovery

Search for open data sources relevant to this market. For each source found, evaluate accessibility and data quality.

**Source types to look for (in priority order):**

1. **Professional colleges/registries** (for professional services) — When searching for professionals (accountants, lawyers, architects, doctors, gestorías, etc.), **always** search for the relevant "Colegio Profesional" or professional body first. In Spain, every regulated profession has one. These are the highest-quality sources with 95-100% contact rates. Examples:
   - `gestors.cat` / `registro.consejogestores.org` for gestorías
   - `icab.cat` / `abogacia.es` for lawyers
   - `economistas.es` for economists/accountants
   - `coam.org` for architects
   - Search: `"colegio" OR "col·legi" OR "registro" + <profession> + <region>`
   - Many professional registries have **search APIs with specialty/service filters** — look for query parameters like `SpecialtyId`, `categoria`, `servicio` to filter for the user's specific need (e.g., "contabilidad" within gestorías).
2. **Open APIs** — Free REST APIs with bulk data (like radio-browser.info, OpenStreetMap Overpass API, iTunes RSS API). Best quality, easiest to scrape.
3. **Government/regulatory databases** — Official registries and censuses. These are often the single largest source (e.g., Spain's Censo Guía de Archivos yielded 7,200+ entries alone). Search for:
   - **National open data portals**: `datos.gob.es` (Spain), `data.gov.uk` (UK), `data.gov` (USA), `data.gouv.fr` (France), etc.
   - **Regional/state open data portals**: These often have CSV/JSON downloads that national portals lack. Examples: `transparenciacatalunya.cat`, `datosabiertos.jcyl.es`, `abertos.xunta.gal`. Search for `"open data" + <region name> + <market keyword>`.
   - **Ministry-level directories**: Many countries maintain official registries for specific sectors (archives, schools, hospitals, radio stations). These may not have APIs but can be scraped via paginated search forms.
   - **National digital heritage aggregators**: Hispana (Spain), Europeana (EU), DPLA (USA). Excellent for cultural institutions — often have 95%+ email/contact rates.
4. **Wikipedia lists** — `https://en.wikipedia.org/wiki/List_of_*` or `Lists_of_*`. Good coverage, structured tables. Also check **category pages** (e.g., `Categoría:Archivos municipales en España`).
5. **Industry directories** — Trade associations, review sites, professional registries. Good data but may require scraping.
6. **Yellow pages / business directories** — Páginas Amarillas (Spain), Yellow Pages (USA/UK), etc. Often have the most entries but require bot-protection bypass (see scraping rules below). Search across multiple categories for the same market to maximize coverage, then deduplicate.
7. **Curated blog posts/lists** — Niche bloggers and researchers often maintain comprehensive link collections. Search for `"directorio" OR "lista" OR "list of" + <market> + <country>`.
8. **GitHub datasets** — Search GitHub for curated lists, databases, or scraped datasets in the market.
9. **Google Maps** — If `GOOGLE_MAPS_API_KEY` is available, use Places API text search. Costs money per query.
10. **Aggregator sites** — Yelp-like directories, niche aggregators for the industry.

**Create a `sources.md` checklist** in the output directory with all discovered sources, their URLs, data format, and accessibility status. Use `[x]` for completed, `[ ]` for pending, and note `BLOCKED` for inaccessible sources.

### Phase 2: Data Collection

For each accessible source, create a **separate XLSX file** named `leads_<source-slug>.xlsx`.

**Scraping rules:**

1. **Always use `uv run --no-project --with httpx,beautifulsoup4,lxml,openpyxl`** to run Python scripts
2. **Use httpx with browser-like headers** — WebFetch gets blocked by many sites:
   ```python
   headers = {
       "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
       "Accept": "text/html,application/xhtml+xml",
       "Accept-Language": "en-US,en;q=0.9",
   }
   ```
3. **Rate limit**: 0.3-0.5s between requests minimum. Be polite.
4. **Write scripts to files first** (e.g., `scrape_<source>.py`), don't use heredocs for long scripts — they can hang with background execution
5. **Use `PYTHONUNBUFFERED=1`** and `sys.stdout.reconfigure(line_buffering=True)` for real-time progress output
6. **Sanitize strings** for openpyxl — remove XML-illegal characters:
   ```python
   import re
   ILLEGAL_CHARS_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')
   def clean(s):
       if not s: return s
       return ILLEGAL_CHARS_RE.sub('', str(s))
   ```
7. **Print progress** every 50-100 items
8. **Handle failures gracefully** — log errors, continue with next item, report error count at end
9. **Run long scrapes in background** with `run_in_background: true`
10. **Parallelize independent sources** — launch multiple background scrapers simultaneously

**Wikipedia scraping specifics:**
- Wikipedia blocks raw WebFetch (403). Use httpx with browser headers.
- Detect redirect pages by comparing page title to expected content.
- For countries with state-level pages (USA, Mexico, Brazil), scrape each sub-page individually.
- Parse both `<table class="wikitable">` and `<ul>/<ol>` lists. Note: some Wikipedia tables lack the `wikitable` class — also check for `<table>` inside content sections.
- Remove navigation junk ("List of...", "Sovereign states", "Category portal" entries).
- Deduplicate by (name, country, region) tuple, case-insensitive.

**API scraping specifics:**
- Check API response structure with a single test request before full scrape.
- Handle pagination (offset/limit, cursor-based, next page URL).
- Save raw JSON response structure notes for debugging.

**Podcast/media market specifics:**
- **iTunes RSS API** is the best free source for podcast charts by country: `https://itunes.apple.com/es/rss/toppodcasts/limit=200/json` (change `es` to target country code). Free, no auth, returns 200 entries with names, artists, categories, Apple IDs, and links. Note: the newer `rss.applemarketingtools.com` API returns 500 errors — use the old iTunes endpoint.
- **iTunes Lookup API** enriches Apple IDs with RSS feed URLs and episode counts: `https://itunes.apple.com/lookup?id=ID1,ID2,...&country=es&entity=podcast` (batch up to 50 IDs).
- **RSS feed enrichment** is extremely high-value — fetching RSS feeds yields ~93% email addresses (from `<itunes:email>` inside `<itunes:owner>`) and ~95% website URLs (from `<link>`). Also extract: `<itunes:author>`, `<itunes:category>`, `<language>`, and social media URLs from `<description>` text. Always do this as a post-processing step when RSS feeds are available.
- **Podscan.fm** (`podscan.fm/charts/es/spotify/top`) works well with httpx and returns Spotify chart data with monthly listeners and episode counts. The official Spotify charts site (`podcastcharts.byspotify.com`) is fully JS-rendered and returns nothing with httpx.
- **Rephonic** (`rephonic.com/charts/spotify/spain/top-podcasts`) provides cross-platform charts (Spotify + Apple + YouTube). It's a Next.js site — parse `<script id="__NEXT_DATA__">` for structured data (see Next.js specifics below).

**Next.js site scraping specifics:**
- Many modern chart/directory sites use Next.js (React SSR). They embed page data in a `<script id="__NEXT_DATA__" type="application/json">` tag.
- Parse this tag with `soup.find('script', id='__NEXT_DATA__')` then `json.loads(script.string)`.
- Data is typically at `data['props']['pageProps']` — the exact structure varies per site.
- This often works even when the visible HTML has no useful content, making it more reliable than trying to parse React-rendered HTML.
- Sites confirmed to use `__NEXT_DATA__`: Rephonic, Podchaser. Sites that are JS-only with no useful `__NEXT_DATA__`: iVoox, official Spotify charts.

**Government directory scraping specifics:**
- Many government directories use JSP/ASP form-based search with POST requests. Inspect the form action, hidden fields, and encoding (some use ISO-8859-1, not UTF-8).
- Results are often paginated — look for page navigation links and iterate all pages.
- Detail pages often have richer data (phone, email, address) than list pages — follow detail links when the list is small enough.
- Government data is frequently in ALL CAPS — normalize with a `title_if_upper()` function (see Phase 4).

**Bot protection bypass (Incapsula, Cloudflare, etc.):**
- Commercial directories like Páginas Amarillas use bot protection (Incapsula/Imperva).
- **Pattern:** First visit the homepage to acquire session cookies, then use those cookies for subsequent requests.
- Use full Chrome-like headers including `Sec-Ch-Ua`, `Sec-Fetch-Dest`, `Sec-Fetch-Mode`, `Sec-Fetch-Site`:
  ```python
  headers = {
      "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
      "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
      "Sec-Ch-Ua": '"Chromium";v="131", "Not_A Brand";v="24"',
      "Sec-Ch-Ua-Mobile": "?0",
      "Sec-Ch-Ua-Platform": '"Linux"',
      "Sec-Fetch-Dest": "document",
      "Sec-Fetch-Mode": "navigate",
      "Sec-Fetch-Site": "none",
  }
  ```
- Use `httpx.Client()` (session-based) to persist cookies across requests.
- Increase rate limit to 1s+ for protected sites.

**Professional registry scraping specifics:**
- Professional registries often expose search forms with filters for province, specialty, and status (active/practicing).
- Look for hidden API endpoints — many registries render results server-side but have underlying JSON APIs.
- Some registries show basic info (name, phone, email) in list view but hide details behind reCAPTCHA on detail pages — scrape what's available in the list view first.
- When filtering by geographic area and the registry doesn't have a province field, **use postal code prefixes** to filter results (e.g., 08xxx=Barcelona, 17xxx=Girona in Spain).

**Email availability caveats:**
- Some directory sites deliberately hide email addresses and use contact forms instead (e.g., gestorias.es, asesoria-asesores-fiscales.es). Don't waste time looking for emails that aren't there.
- Professional registries (colegios profesionales) typically have the best email coverage (95-100%).
- Yellow pages rarely have emails but often have phone numbers and websites.

### Phase 3: XLSX Output Format

Every XLSX file must follow this template:

**Sheet 1: Main data sheet** (named after the source)
- **Minimum columns**: Name, Country, City/Region
- **Preferred columns**: Name, Country, City, Province/State, Region, Address, Phone, Email, Website, Category/Type, Latitude, Longitude
- **Add source-specific columns** as needed (e.g., Frequency for radio, Google Place ID, Stream URL, Rating)
- Bold white headers on colored background (use a distinct color per source)
- Freeze top row (`ws.freeze_panes = "A2"`)
- Auto-filter on all columns
- Appropriate column widths (use `openpyxl.utils.get_column_letter()` for columns beyond Z)
- Thin borders on all data cells

**Sheet 2: "Summary by Country"** (or "Summary by Region" when targeting a single country)
- Columns: Country/Region, Count
- Sorted by count descending

**Styling template:**
```python
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from openpyxl.utils import get_column_letter
from collections import Counter

header_font = Font(bold=True, color="FFFFFF", size=11)
header_fill = PatternFill(start_color="2E86AB", end_color="2E86AB", fill_type="solid")  # Change color per source
thin_border = Border(
    left=Side(style='thin'), right=Side(style='thin'),
    top=Side(style='thin'), bottom=Side(style='thin')
)
```

### Phase 4: Deduplication & Normalization

Within each source file, deduplicate by normalized key:
```python
key = (name.lower().strip(), country.lower().strip(), city.lower().strip())
```

For chain businesses, treat each location as a separate entry (e.g., "Starbucks - Downtown" and "Starbucks - Airport" are different leads).

**ALL CAPS normalization** — Government databases often store data in ALL CAPS. Use this function to normalize names and cities:
```python
def title_if_upper(s):
    """Convert ALL CAPS strings to Title Case, preserving mixed case."""
    if not s: return s
    if s == s.upper() and len(s) > 3:
        words = s.lower().split()
        # Adjust small_words for the target language
        small_words = {'de', 'del', 'la', 'las', 'los', 'el', 'en', 'y', 'e', 'o', 'a', 'al'}  # Spanish
        return ' '.join(w.capitalize() if i == 0 or w not in small_words else w for i, w in enumerate(words))
    return s
```

**Administrative division normalization** — When targeting a single country, different sources use different names for the same region (e.g., "Comunidad de Madrid" vs "Madrid" vs "MADRID", or "Comunitat Valenciana" vs "Comunidad Valenciana"). Build a normalization mapping:
```python
REGION_NORMALIZE = {
    'comunidad de madrid': 'Madrid',
    'comunitat valenciana': 'Comunidad Valenciana',
    # ... etc
}
```
Also build a **province/state → region mapping** for the target country to fill missing region data from province fields.

**Postal code → province mapping** — For countries with structured postal codes, the first digits often identify the province/state. For Spain, the first 2 digits map to provinces (01=Álava, 02=Albacete, ..., 50=Zaragoza, 51=Ceuta, 52=Melilla). Use this to fill missing geographic data cheaply.

### Phase 4.5: RSS/Feed Enrichment (for media/podcast/content markets)

When leads have RSS feed URLs (common for podcasts, blogs, news sites, YouTube channels), run a batch enrichment step:

1. Fetch each RSS feed with httpx (0.15s rate limit — feeds are lightweight)
2. Parse XML and extract:
   - `<itunes:owner>/<itunes:email>` — creator's email (highest-value field)
   - `<link>` — website URL
   - `<itunes:author>` — creator name
   - `<itunes:category text="...">` — category
   - `<language>` — language code (e.g., `es` for Spanish)
   - `<description>` — scan for email addresses (`[\w.+-]+@[\w-]+\.[\w.-]+`), social media URLs (instagram.com/, twitter.com/, youtube.com/)
3. Merge enriched data into the source XLSX, adding new columns (Website, Email, Language, etc.)
4. Report enrichment stats (% with email, % with website, % in target language)

This step typically yields **90%+ email addresses** and **95%+ website URLs** for podcast data — far more than any scraping approach.

### Phase 4.6: Curated Top Leads (for markets where "biggest/best" matters)

When the user asks for "top", "biggest", "most popular", or "grandes" leads, create a **curated high-quality file** (`leads_TOP_CURATED.xlsx`) in addition to the bulk consolidated file:

1. **Use a web research agent** (Agent tool with `subagent_type=general-purpose`) to search for authoritative rankings, award winners, annual reports, and industry publications. This finds detailed info (hosts/founders, social media, awards, audience numbers) that automated scraping cannot.
2. **Build the curated list manually** from research results — typically 50-100 entries with rich metadata.
3. **Merge with scraped data** — enrich the curated entries with emails, websites, and RSS feeds from the automated scraping phase.
4. **Include extra columns** not in the bulk file: hosts/team, awards, audience notes, social media handles.

The curated file is often more valuable than the bulk file for sales outreach, since every entry is verified as a major player in the market.

### Phase 5: Consolidation

After all sources are scraped, create a **consolidated master file** named `leads_ALL_CONSOLIDATED.xlsx` that merges and deduplicates all source files.

**Consolidation script should:**
1. Load all `leads_<source>.xlsx` files
2. Map each source's columns to a common schema
3. Normalize regions/provinces using the mappings from Phase 4
4. Normalize ALL CAPS names and cities with `title_if_upper()`
5. Deduplicate across sources by normalized (name, city) key — when merging duplicates, **keep the record with the most data** and fill in missing fields from the other record
6. Track which sources contributed to each lead (add a "Source" column)
7. Sort by region → city → name
8. Include summary sheets:
   - **Summary by Region** — counts per administrative region
   - **Summary by Category** — counts per business type
   - **Summary by Source** — how many leads each source contributed
   - **Data Quality** — percentage of leads with each field filled (city, phone, email, website, etc.)

Use a dark header color (#1A5276) for the consolidated file to distinguish it from source files.

### Phase 6: Reporting

After consolidation:

1. **Update `sources.md`** with final results for each source (lead counts, file names, data quality notes)
2. **Print a summary table** showing all files, lead counts, and coverage
3. **Clean up temp scripts** (delete `scrape_*.py` and `consolidate.py` files after successful completion)

## Output Quality Standards

- **QUALITY over QUANTITY** — Better to have fewer verified leads than many with duplicates
- **No fabricated data** — Only include data actually found in sources
- **Preserve original language** — Don't translate business names
- **Leave empty fields blank** — Don't use "N/A", "Unknown", or placeholders
- **Skip closed/defunct businesses** when detectable
- **Verify file output** — After creating each XLSX, verify it has data rows (not just headers)

## Common Pitfalls to Avoid

1. **Don't use WebFetch for scraping** — It gets blocked. Use httpx via Python scripts.
2. **Don't use heredocs for long scripts** — Write to `.py` files instead, they hang in background mode.
3. **Don't forget to sanitize strings** — openpyxl crashes on XML-illegal characters (control chars in URLs).
4. **Don't assume API response structure** — Test with one request first, then build the full scraper.
5. **Don't scrape the same data twice** — Check if a source's sub-pages redirect to the same parent page.
6. **Government sites may be geo-blocked** — FCC (USA) and ACMA (Australia) are unreachable from some regions. Note this and move on.
7. **JS-only sites need Playwright** — If a site returns empty content, it likely needs JS rendering. Note as blocked unless Playwright is available.
8. **Government data is often ALL CAPS** — Always apply `title_if_upper()` to names and cities from government sources.
9. **Region names vary across sources** — Build a normalization map early. Watch for bilingual variants (Catalan/Spanish, Basque/Spanish), doubled text from bad HTML parsing ("CataluñaCataluña"), and inconsistent specificity ("Madrid" vs "Comunidad de Madrid").
10. **Don't skip the consolidation step** — Individual source files have different schemas and duplicate entries. The consolidated file is the actual deliverable.
11. **Use `get_column_letter()` for XLSX columns** — Hardcoded `chr(64+c)` breaks for columns beyond Z (column 26+).
12. **Cross-category deduplication** — When scraping the same directory across multiple categories (e.g., "gestorías administrativas" + "contabilidad" + "asesorías contables" on Páginas Amarillas), the same business often appears in multiple categories. Always deduplicate within each source file by (name, city).
13. **Professional registries are the best source for professional services** — Don't skip them. They typically have the highest data quality (98%+ email/phone) and the most complete listings for regulated professions.
14. **Chart/ranking sites are often JS-rendered** — Podchaser, iVoox, official Spotify charts, and many "top X" sites use React/Next.js. Try `__NEXT_DATA__` parsing first; if that fails, note as BLOCKED and use alternative sources (e.g., Podscan instead of official Spotify charts).
15. **Scraped names from chart sites need heavy cleaning** — Podtail concatenates category+date to names (e.g., "La RuinaComedia11 mar"), Podscan concatenates metrics (e.g., "#1La RuinaLa Ruina0N3monthly listeners..."). Build robust name normalization with regex to strip these artifacts before deduplication.
16. **RSS feeds are a goldmine for contact data** — Don't skip the RSS enrichment step when feeds are available. It's the single highest-ROI enrichment technique for media/content leads (93%+ email yield).
17. **Apple's newer RSS API is broken** — `rss.applemarketingtools.com/api/v2/` returns 500 errors. Use the old iTunes endpoint: `itunes.apple.com/<country>/rss/toppodcasts/limit=200/json`.
