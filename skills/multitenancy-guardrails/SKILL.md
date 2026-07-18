---
name: multitenancy-guardrails
description: 'Design, review and test tenant isolation in multi-tenant SaaS (row-level tenancy with a tenant FK: municipality_id, client_id, org_id, team_id). Use when building or reviewing ANY endpoint that touches tenant-owned data, when the user asks "is multitenancy safe here", "check tenant isolation", "audit IDOR", "can tenant A see tenant B", when adding a new model/handler/export/background job to a multi-tenant app, when writing tenant isolation tests, or when a security review flags cross-tenant access. Covers: the scoping rules (404 not 403, never trust client tenant ids, UUIDs are not authorization), the leak-vector checklist (exports, files/media, stats, HTMX fragments, background jobs, emails, search/RAG retrieval, cache and rate-limit keys, storage paths, magic links, merge/bulk ops, embeds/widgets), Django and Go enforcement patterns, Postgres RLS as defense-in-depth, and the two-tenant isolation test suite every project must have.'
---

# Multitenancy guardrails

Row-level multi-tenancy (shared tables + tenant FK) is the default architecture for small/mid SaaS. It is also the architecture where one missing `WHERE tenant_id = ...` becomes a data breach. These rules make isolation systematic instead of hopeful. They were distilled from real audits (six products, same day: one had NO scoping at all on any admin endpoint; the others leaked through stats, exports and department views) plus the OWASP Multi-Tenant Security Cheat Sheet.

## Core rules

1. **The tenant comes from the server, never the client.** Resolve tenant from the authenticated session/user record, the subdomain, or a server-validated header — never from a form field, JSON body, or query param. A `municipality_id` in a POST body is an attack vector, not a parameter.
2. **Scope at the data-access layer, once.** Every fetch of a tenant-owned row goes through a helper that injects the tenant filter (`get_object_or_404(Model, pk=..., tenant__in=user_tenants)` / a `guardX(ctx, id)` store function). Handlers never call raw `get(pk=...)` on tenant-owned models. If the codebase has both scoped and unscoped fetch paths, the unscoped one WILL eventually be used by mistake — delete it or make it private to admin tooling.
3. **404, never 403, on cross-tenant access.** A 403 confirms the object exists (ID probing). Cross-tenant must be indistinguishable from nonexistent.
4. **UUIDs are not authorization.** Unguessable IDs reduce enumeration risk; they do not replace the ownership check. Every ID accepted from a request gets ownership-verified, even UUIDv4.
5. **Membership is a set, not a scalar.** Users may belong to N tenants (the shared-manager/shared-secretary case). Model it as M2M/join from day one; "switch tenant" endpoints validate membership server-side.
6. **New endpoint = new isolation test.** An endpoint without a cross-tenant test is unreviewed. Make it a PR checklist item.

## The leak-vector checklist

Audits that only check CRUD screens miss where real leaks live. Walk ALL of these for every tenant-owned resource:

| Vector | The classic mistake |
|---|---|
| **Exports / downloads** (CSV, DOCX, PDF, reports) | Fetch by ID without tenant check; whole-tenant export reachable by a role that should see a subset (e.g. department user exporting the full org CSV) |
| **Files / media / attachments** | Serving by path or ID with no ownership check; media URLs guessable; presigned URLs minted without verifying the object's tenant |
| **Stats / aggregates / dashboards** | COUNT/AVG queries missing the tenant filter (numbers leak existence and scale); "all-tenant" stats visible to scoped roles |
| **Partial/HTMX/AJAX fragments** | The page is scoped but its fragment endpoints (inline edit, row refresh, dropdown options) are not |
| **Background jobs / scheduled tasks** | Job runs without tenant context and processes/emails across tenants; job parameters carry raw IDs that are never re-verified at execution time |
| **Emails / notifications** | Notification fan-out queries missing the tenant join; templates interpolating another tenant's data via shared context |
| **Search / RAG retrieval / embeddings** | Vector or FTS query without the tenant filter — retrieval-augmented answers are a *high-bandwidth* cross-tenant leak; filter at query time, not post-filter after top-k |
| **Cache keys** | `cache.get(f"config:{slug}")` where slug is client-controlled, or keys missing the tenant component entirely — tenant A gets tenant B's cached page |
| **Rate-limit keys** | Keyed only per-IP or only per-user: one tenant can exhaust another's quota, or per-tenant limits don't exist |
| **Storage paths** | Uploads under user-controlled names/paths; missing tenant prefix means listing or guessing crosses tenants |
| **Magic links / tokens / reference codes** | Token lookup not joined to tenant; token from tenant A working on tenant B's subdomain |
| **Merge / bulk / admin operations** | Merging or bulk-updating rows accepts IDs from mixed tenants; re-parenting rows silently moves them across tenants |
| **Embeds / widgets / public APIs** | Widget API key of tenant A accepted while serving tenant B's content; CORS + key checks not bound together |
| **Admin panels** (Django admin etc.) | Registered models expose all tenants to any staff-flagged user; API keys/secrets visible cross-tenant |

## Enforcement patterns

### Django (server-rendered / HTMX)

```python
# One helper owns the rule. Handlers use ONLY this for tenant-owned models.
def get_scoped(request, model, **kw):
    return get_object_or_404(model, tenant__in=request.user.tenants.all(), **kw)

# Or at the manager level:
class TenantQuerySet(models.QuerySet):
    def for_user(self, user):
        return self.filter(tenant__in=user.tenants.all())
```

- Middleware resolving tenant from subdomain/header sets `request.tenant` after validating it against the DB — downstream code never re-parses the host. A `with_tenant`-style view decorator that resolves membership and injects the tenant kills the copy-pasted prologue that eventually forgets the None-guard (real bug class).
- **HTMX fragment endpoints inherit no scoping from their parent page** — every inline-edit/row-refresh/dropdown endpoint gets the same `get_scoped` treatment as the full view.
- Exports and file responses (`FileResponse`, DOCX/CSV builders) fetch their objects through the scoped helper too — download endpoints are the most-forgotten surface.
- Django admin on tenant-owned models: superuser-only or scope `get_queryset()`; never expose API keys/secrets in `list_display` (any staff-flagged user would see all tenants' keys).
- Celery tasks take object IDs and RE-verify tenant on execution (the queue is a trust boundary; a task enqueued for tenant A must not act on a row that has since moved or been re-parented).
- `select_related`/`prefetch_related` don't change scoping, but a `.get(pk=...)` inside a loop over prefetch results does — grep for raw `objects.get(` in views/services as a review habit.

### Django REST Framework

DRF has extra footguns because routers generate surface area you didn't write:

```python
class TicketViewSet(ModelViewSet):
    serializer_class = TicketSerializer

    def get_queryset(self):                      # THE scoping point
        return Ticket.objects.filter(tenant__in=self.request.user.tenants.all())
```

- **Never rely on `queryset = Model.objects.all()` + permissions.** `get_object()` draws from `get_queryset()` — scope there and detail routes are automatically safe (and cross-tenant is a 404, which is what you want). `has_object_permission` alone returns 403 → existence leak.
- **Serializer related fields are a write-path leak**: `PrimaryKeyRelatedField(queryset=Category.objects.all())` accepts ANY tenant's category id — a citizen of town A attaches town B's department to their ticket. Scope related-field querysets in `__init__`/`get_fields` from `self.context["request"]`. This is the single most common cross-tenant WRITE bug in DRF codebases.
- `@action` methods and nested routers bypass your mental model — every custom action re-derives from `self.get_queryset()`, never from the model manager.
- django-filter/search/ordering operate on the scoped queryset only (pass `self.get_queryset()` as base, which is the default — don't override `filter_queryset` with a raw manager).
- Header tenancy (the `X-Client-Slug` pattern): middleware validates slug against the DB and attaches the tenant; if the API is key-authenticated, the key row itself carries the tenant FK — derive tenant from the key, never from a slug the client also sends (or you get confused-deputy mismatches).
- Throttle scopes: include the tenant in the throttle cache key (`f"{tenant.pk}:{ident}"`) so one tenant can't starve another and per-tenant plans are enforceable.

### Go (stdlib/chi + pgx/sqlc)

```go
// Store-level guard: the ONLY way handlers fetch tenant-owned rows.
func (s *Store) TicketForTenant(ctx context.Context, tenantID, id uuid.UUID) (*Ticket, error) {
    // WHERE id=$1 AND tenant_id=$2 — pgx.ErrNoRows maps to 404 at the handler
}
```

- Auth middleware resolves the user + tenant in ONE query (join session→user) and stores a typed struct in context via an unexported key. Guards must treat "no user in context" as unauthenticated — never let the zero value pass as a platform admin.
- With **sqlc**: every query on a tenant-owned table takes `tenant_id` as a parameter and the name says so (`GetTicketForTenant`, not `GetTicket`). If a query legitimately spans tenants (platform admin), name it loudly (`AdminListAllTickets`) so review catches misuse.
- The **optional-scope parameter pattern** keeps one query serving both scoped users and platform admins without string-building:
  `WHERE ($1::uuid IS NULL OR t.municipality_id = $1)` — pass `nil` for platform admin, the tenant id otherwise.
- Uploads: run the ownership guard BEFORE reading the request body (don't waste/accept a 100MB body for a 404), then `http.MaxBytesReader`.
- Objects referenced by other objects (a QR pointing at a POI, a ticket merged into another): guard BOTH sides — the object being edited and the target it points to must be same-tenant.
- NULL `tenant_id` on a user = platform admin is an acceptable minimal model — but pick the FK's `ON DELETE` deliberately: `SET NULL` silently **escalates a scoped user to platform admin** when their tenant is deleted (real finding); `CASCADE` (remove user with tenant) is usually what you mean.

### Postgres

Schema-level guardrails catch what app code misses:

- **Unique constraints must include the tenant**: `UNIQUE(email)` globally both breaks tenant B ("email already in use" — an existence leak AND a denial) and couples tenants. Use `UNIQUE(tenant_id, email)`. Same for slugs, reference codes, order numbers.
- **Composite-FK integrity trick** — make cross-tenant re-parenting impossible at the DB level:
  ```sql
  ALTER TABLE parent ADD UNIQUE (tenant_id, id);
  ALTER TABLE child  ADD FOREIGN KEY (tenant_id, parent_id) REFERENCES parent (tenant_id, id);
  ```
  Now a child row cannot point at a parent from another tenant, no matter what the app does. Worth it on the riskiest edges (payments→enrollments, messages→tickets).
- **Indexes lead with tenant_id** on tenant-owned tables: `(tenant_id, created_at)`, `(tenant_id, status)`. A bare `(created_at)` index invites unscoped full-table query plans and makes the scoped query slower than the buggy one.
- **FTS and pgvector**: the tenant filter belongs IN the query (`WHERE tenant_id = $1 ORDER BY embedding <=> $2`), never as a post-filter on top-k results — post-filtering both leaks (top-k computed across tenants) and starves results. With HNSW/IVFFlat, verify the plan still uses the index with the filter; if not, consider partial indexes per hot tenant or exact search at small scale.
- **RLS (defense-in-depth, optional)** — app-layer filtering remains mandatory; RLS catches what the app misses:
  ```sql
  ALTER TABLE t ENABLE ROW LEVEL SECURITY;
  ALTER TABLE t FORCE ROW LEVEL SECURITY;   -- without FORCE, the table owner bypasses it
  CREATE POLICY tenant_isolation ON t
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
  ```
  The app role must not be the table owner, superuser, or `BYPASSRLS`. Set context with `SET LOCAL app.tenant_id = ...` inside the transaction (safe with pgbouncer transaction pooling precisely because it's `SET LOCAL`). `current_setting(..., true)` returns NULL instead of erroring when unset — which fails closed (no rows). Write one test that queries as the app role WITHOUT setting the context and asserts zero rows. Adopt RLS when the blast radius justifies it (minors' data, health, finance).

## The isolation test suite (non-negotiable)

Every project seeds **at least two tenants** (demo data for both) and a user scoped to only one. One test module proves isolation; ~10 sharp assertions beat 100 ceremonial ones:

1. List endpoints return only own-tenant rows (assert the other tenant's known object is absent).
2. Detail/edit/delete/export of the other tenant's object by ID → **404** (assert not 403, assert no data in body).
3. File/media/attachment of the other tenant → 404.
4. Stats/dashboard numbers equal own-tenant counts exactly (seed distinct counts per tenant so a leak changes the number).
5. Fragment/AJAX/HTMX endpoints — same probes as their parent pages.
6. Tenant-switch to a non-member tenant → rejected; membership switch works.
7. Public pages of tenant A never render tenant B content (string-probe with a distinctive seeded marker).
8. Search/RAG: a query matching only tenant B's content returns nothing for tenant A.
9. Where roles exist within a tenant (department, section): repeat 1–2 across roles.
10. Platform-admin (if it exists) still sees everything — so scoping bugs don't hide as "admin works".

E2e variant: log in as the scoped user in the browser and probe 2–3 of the above through the real UI; keep the exhaustive matrix at the unit/integration level where it is cheap.

## Review checklist (paste into PR review)

- [ ] Tenant resolved server-side only (session/subdomain/validated header)
- [ ] All fetches of tenant-owned rows go through the scoped helper (grep for raw `get(pk=`/`QueryRow.*WHERE id =` without tenant)
- [ ] Cross-tenant = 404 everywhere
- [ ] Exports, files, stats, fragments, jobs, emails, search, cache keys, rate-limit keys, storage paths, tokens, bulk ops audited (table above)
- [ ] Two-tenant seed + isolation tests updated for every new endpoint
- [ ] Admin surfaces scoped or superuser-only

## Reference

- OWASP Multi-Tenant Security Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Multi_Tenant_Security_Cheat_Sheet.html
