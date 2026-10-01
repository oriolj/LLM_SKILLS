---
name: enacast-insights
description: Publish and operate podcast channels on EnaCast AI / Enacast Insights (pod.enacast.com, repo EnaCast/enacast-ai) through its per-client publishing API — create a channel, upload episodes (presigned PUT to Backblaze), set thumbnails, import your own transcript and chapters, set the glossary and analysis context, read back the AI sections and the machine transcript for comparison, issue/revoke client API keys, and deploy changes to enacast-ai safely. Use when the user wants something published "as a podcast on pod.enacast.com", mentions Enacast Insights / EnaCast AI / pod.enacast.com channels, publishing API keys (`eai_…`), the BikeCRM Interviews podcast, or when a content repo needs a podcast feed with transcripts and chapters.
---

# Enacast Insights (pod.enacast.com) — publishing podcasts through the API

EnaCast AI (repo `~/git/EnaCast/enacast-ai`, Django + Ninja, Enantena scope; hq
`docs/projects.md` row "EnaCast AI = Enacast Insights") hosts podcast channels at
`pod.enacast.com/c/<slug>/` (the per-channel subdomain `<slug>.pod.enacast.com` needs the
wildcard DNS that does not exist yet, 2026-10-01). For each episode it transcribes (Whisper on the
GPU worker), analyses (AI title, summary, tags, sections), serves an episode page, SRT/VTT
transcripts and an RSS feed for Apple/Spotify (`/c/<slug>/rss.xml`).

**The contract is `backend/docs/PUBLISHING_API.md`** in that repo: read it before calling the
API; this skill keeps the workflow and the traps.

## Keys and access

- One key per Client (`ClientApiKey`, migration `channels 0089`, 2026-10-01): `Authorization:
  Bearer eai_<40>`. A key sees only its own client's `manual` channels (anything else is 404).
- Issue a key in production as a one-off in the web container — the plaintext is printed once,
  only its hash is stored:
  `ssh -p 1922 root@enacast-ai-fsn1-1` → `docker exec $(docker ps --filter name=z75pe720 --format '{{.Names}}' | head -1) python manage.py create_client_api_key --client "<Client>" [--create --email <owner>] --name "<what uses it>"`.
  Pipe the output straight into the hq secrets file (grep `eai_[A-Za-z0-9]{40}`), never into chat;
  catalogue it in hq `CLAUDE.md` and ask Oriol to `make secrets-encrypt FILE=…` (`secrets-in-git`).
  Revoke in the enacast-ai admin (Client API keys).
- Known keys: BikeCRM → hq `homelab/secrets/enacast-ai-publish-bikecrm.env`
  (`ENACAST_AI_PUBLISH_KEY_BIKECRM`), used by bikecrm-content-creation `scripts/publish_pod.py`.

## Publishing workflow (the BikeCRM Interviews run, 2026-10-01)

1. **Channel** — `POST /api/publish/v1/channels` (`manual`, slug immutable, language en/es/ca/hu):
   - `glossary`: the words Whisper gets wrong plus every proper noun (shops, people, brands);
   - `custom_llm_context` (≤ 4000): who speaks, what the show is, how to name things, what NOT to
     do (e.g. "never present the product as an advert");
   - `prefer_ai_insights: false` to show your titles/descriptions instead of the AI ones;
   - `itunes_category` (Apple's exact top-level name), `owner_email`;
   - a square cover ≥ 1400 px (3000×3000 JPEG) via `PUT /channels/{slug}/logo`.
2. **Episode** — `POST /channels/{slug}/episodes` (title, description ≤ 1500, `published_at`:
   order the feed by setting it), then **media**: `POST /episodes/{uuid}/upload` (presigned PUT,
   6 h, ≤ 5 GiB, `audio/*`/`video/*`), `PUT` the bytes with exactly the returned headers and
   **without** the Authorization header, then `POST …/upload/complete` with the returned key.
   Server-to-server, no CORS needed. A 0.44 GB file took ~45 s end to end.
3. **Thumbnail** `PUT /episodes/{uuid}/thumbnail` (becomes the RSS `itunes:image`),
   **chapters** `PUT /episodes/{uuid}/chapters` (`[{start, title}]`: they replace the AI sections
   on the page and in the feed's `podcast:chapters`; the AI sections stay readable in
   `ai_sections`), **transcript** `PUT /episodes/{uuid}/transcript` (segments with speaker; needs
   the media first, 409 otherwise).
4. The worker still runs (MP3 companion, duration, Whisper): its transcript is kept as the
   **machine** one (`GET …/transcript?source=machine`) and never overwrites an import; the
   analysis re-runs on the imported transcript. An episode is public (site + feed) once its
   analysis is done and, for video, once the MP3 exists.
5. **Compare** after processing: `ai_sections` vs your chapters, the machine transcript vs yours
   (a cheap quality check of their pipeline, worth reporting to the EnaCast team).

## Media

- Video works on the site; the **RSS enclosure is always the extracted MP3** (fixed 2026-10-01:
  before, a video episode could hand podcast apps the video).
- HEVC 1080p is fine (Oriol, 2026-10-01): Main 8-bit, `hvc1` tag (Safari needs it), `+faststart`.
  With VAAPI encode as `hev1` and re-tag by stream copy: tagging `hvc1` in a VAAPI encode writes a
  file every decoder shows green. Don't upload 4K masters (multi-GB, slow, no benefit).
- Use your own reviewed transcript when you have one (timed on the episode's timeline: an
  intro/cards shift every time).

## Changing enacast-ai itself

Rules from its `DEPLOY.md`: any push touching `backend/**` deploys **four** Coolify apps (web,
celery worker, update-channels, sweep; blue-green); check `df -h /` first (never below 15 GB free;
`docker builder prune -af` + `docker image prune -af --filter until=24h`, again after the deploy);
at most one backend push per hour; migrations run on boot. Review before pushing (an adversarial
review found a cross-tenant `..` key and a GPU requeue loop in the first version of this API).
After deploy: `/private_api/health`, `showmigrations`, a real call. The house also wants a
`team_mail/` file only when the team is mailed, and QA entries in `../enacast/QA_PENDING.md`.

## Open items (2026-10-01)

Wildcard DNS for `*.pod.enacast.com`; no delete/replace-media endpoints; no rate limits (each
transcript PUT re-queues an LLM analysis); two `linea-de-servei` video episodes left the feed
for lack of an MP3 (backfill). Follow-ups in enacast-ai `backend/FUTURE_IMPROVEMENTS.md`.
