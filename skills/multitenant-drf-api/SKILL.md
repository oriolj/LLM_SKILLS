---
name: multitenant-drf-api
description: Traps in Django REST Framework APIs where every row belongs to a tenant (radio/org) and users have roles below "admin" (restricted editors, content editors). Load when writing or reviewing a DRF viewset/serializer that scopes by tenant, gates hidden/draft/scheduled content, resolves "which tenant does this write target", or validates per-tenant uniqueness — and when an admin backoffice reports "X exists but the user can't see/assign/edit it" or a 500 on save.
---

# Multitenant DRF API — the traps that shipped (EnaCast, 2026-09-03 sweep)

Ten bugs in one day, all the same four shapes. Check each shape before
shipping a tenant-scoped viewset.

## 1. Per-tenant uniqueness is NOT validated unless the tenant is a serializer field

`unique_together = (("slug", "radio"),)` on the model + a write serializer
that does not expose `radio` (the view injects it via `serializer.save(radio=…)`)
= DRF builds **no** `UniqueTogetherValidator` (it needs every constrained
field on the serializer). A duplicate reaches the DB and surfaces as an
`IntegrityError` **500** that the frontend can only show as "Error saving".

Fix: a mixin that resolves the tenant (instance's on update, context/request
on create) and rejects the clash with a field-keyed 400
(`{"slug": ["A news tag with this slug already exists for this radio."]}`).
Skip the query on update when no constrained field changed; filter by
`radio_id`, not a loaded object; derive the message from the model NAME —
`verbose_name` is a lazy translation and reads "A Tag de noticia with…"
under a non-English locale. Reference: `enacast_backend/api_ng/unique_validation.py`.

## 2. A concrete `class Meta:` REPLACES the abstract parent's Meta wholesale

`class NewsTag(TagAbstractModel): class Meta: verbose_name = …` silently
drops the abstract `unique_together`. Four tag models did this; prod held
33 duplicate-slug groups (8 with an empty slug). Inherit
`class Meta(TagAbstractModel.Meta):` or re-declare the constraint, and add a
migration that dedupes first (oldest keeps its slug; compare **through the
DB**, because MySQL `*_ci` collations treat `Societat`/`societat` as equal
and a Python set will not).

## 3. "Admin-only" gates exclude the roles that legitimately need the rows

Pattern: `include_hidden = param and is_radio_admin(request)` on a list
endpoint whose queryset is later narrowed to a restricted editor's assigned
programs. The editor assigned a HIDDEN program saw neither the program nor
its episodes; news editors (radio-wide content role, no assigned programs)
got an EMPTY list; failed recordings vanished for editors. Rules:

- Gate opt-ins on **"admin of the queried tenant OR content editor of the
  queried tenant"**, then let the access filter narrow. Never on
  `is_admin(request)` alone — unscoped, it also lets an admin of tenant A
  read tenant B's hidden rows by naming B.
- A role that is radio-wide (news editor) must not fall into the
  "programs_access is empty → `.none()`" branch.
- Every public-list branch must carry the same visibility trio
  (`hidden=False`, `parent__hidden=False`, `publish_dt <= now`); the
  `?program=<codename>` branch lacked one term and listed a hidden
  program's episodes anonymously.
- Detail gates: "non-public" = unpublished **or scheduled in the future**;
  gating on `published` alone leaks scheduled items by id.
- Opt-in flags like `?include_scheduled=true` need a **tenant** check, not an
  "is authenticated" check — otherwise any user lists another tenant's drafts.
- Per-object writes for the sub-admin role: swap the permission class per
  action (`get_permissions`: editors may update assigned objects; create and
  delete stay with admins) — don't clone the viewset.

## 4. One rule for "which tenant does this write target"

Five viewsets each carried "`?radio=` for superusers, else the caller's
radio"; the uniqueness validator resolved the target differently, so a
group admin's create validated against B and saved into A. Keep ONE resolver
(`resolve_write_radio(request, strict=True)`: `?radio=` when the caller may
target it — superuser, own tenant, administered tenant — else own tenant;
strict = unknown/foreign codename is a 400, never a silent fallback) and use
it for authorization, validation and `save()`. Its read-side twin
(`user_may_target_radio`) gates non-public reads. Also: a lookup helper that
*returns None* for an unknown codename (instead of raising) will bypass
`except DoesNotExist` — check what yours does.

## Regression matrix (write these tests)

Anonymous · authenticated user of ANOTHER tenant · restricted editor
(assigned objects only) · radio-wide content editor · tenant admin · group
admin targeting own vs administered vs foreign tenant · superuser with
`?tenant=` ≠ profile tenant. Rows: hidden/draft, scheduled/future,
disabled, off-air, public; first page and beyond the page cap; API failure
vs genuinely empty. Reproduce on prod as the real user with a rolled-back
replay (`APIRequestFactory` + `force_authenticate` inside
`transaction.atomic()` that raises) before and after the fix.

## Frontend counterpart (admin backoffice)

- In-memory "all options" helpers for admin pickers are admin-complete by
  default (hidden/unpublished/disabled included) with an explicit opt-out for
  public previews; paginate through every page; a failed reference load is a
  visible notice with retry, never an empty list.
- Operations use the SELECTED tenant, not the profile tenant; create helpers
  take the target tenant explicitly.
- Surface the backend's 4xx reason; never assume a save failure is a network error.
- Counts next to lists are server totals (`count` of a page-size-1 query or a
  statistics endpoint), never the size of the fetched sample.
