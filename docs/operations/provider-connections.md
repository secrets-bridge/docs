# Provider connections

A **provider connection** is the Control Plane's metadata registry for an
external secret store — its URL, region, KV mount, role hint, and the
project / environment scopes it can be consumed from. It is **not** a
credential. The agent authenticates with its own workload identity
(IRSA / Kubernetes auth / instance role); the Control Plane never holds
the provider's secret material and never proxies it.

EPIC P (api#92) replaced the legacy operator-edited
`SB_DISCOVER_TARGETS_JSON` env var with a first-class admin surface:
- A typed `provider_connections` row per external store
- A `project_provider_connections` join table that binds each connection
  to one or more (project, environment) tuples
- A periodic discovery scheduler that reads from the table instead of
  the env var
- An admin SPA page at `/admin/provider-connections`
- A developer dropdown returned by the same URL with a sanitized
  projection (`{id, name, type}` only) when callers pass a `project_id`

This page is the operator-facing reference: the model, the bindings, the
discovery lifecycle, the disable semantics, the triage SQL, and the
deprecation timeline.

If you came here from
[Cross-team requests](cross-team-requests.md#target-vs-destination)
looking for "where does the destination dropdown's list come from," the
short answer is: the connections bound to the **source** project + env
via this page.

## Model

| Field | Notes |
|---|---|
| `id` | UUID |
| `name` | unique per Control Plane; editable; appears in dropdowns + audit |
| `type` | `vault` / `aws-sm` / `azure-kv` / `gcp-sm` / `kubernetes` — **immutable** after create (the SPA disables the select on edit) |
| `cluster_name` | matches the agent's `SB_CLUSTER_NAME`; required when `discover_enabled=true` (DB CHECK enforces) |
| `description` | optional, ≤ 500 characters |
| `status` | `active` (default) or `disabled` |
| `scope` | JSON object — provider-specific connection metadata. **No credentials.** |
| `auth_method` | optional provider hint (e.g. `kubernetes` for Vault) |
| `discover_enabled` | toggles whether the worker schedules periodic discovery |
| `discover_interval_seconds` | between 60 and 86400 |
| `last_discover_*` | `at` / `status` / `started_at` / `error` — written by the worker after each discover job |

### Project binding model

`project_provider_connections` is the N:M binding table. One connection
can serve many projects; one project can have many connections bound to
different environments. The rules:

| Row shape | Means |
|---|---|
| `(connection_id, project_id, environment_id=NULL)` | Project-wide binding — every environment in the project sees this connection in the dropdown |
| `(connection_id, project_id, environment_id=<env>)` | Env-specific binding — only that environment sees it |

Two partial UNIQUE indexes (one with `WHERE environment_id IS NULL`,
one with `WHERE environment_id IS NOT NULL`) enforce no-duplicate
bindings per Postgres NULL semantics. A connection can be bound to both
"project-wide" AND env-specific overrides in the same project; the
developer dropdown returns the union with no deduplication needed (the
api projects `{id, name, type}` and ignores duplicate ids).

## Scope JSON shape per provider

The `scope` JSON is **metadata only** — the agent reads it to know
*where* to connect, never *what credential* to use. The keys below are
the minimum the api validates; provider connectors may accept more.

### Vault

| Key | Required | Notes |
|---|---|---|
| `address` | yes | `https://` URL; `http://` refused unless `SB_ALLOW_INSECURE_VAULT_ADDR=true` on the api |
| `kvMount` | yes | KV v2 mount path (e.g. `secret`) |
| `kvPrefix` | no | optional path prefix scoping discovery |
| `namespace` | no | Vault Enterprise namespace |

### AWS Secrets Manager

| Key | Required | Notes |
|---|---|---|
| `region` | yes | e.g. `us-east-1` |
| `roleArn` | no | `arn:aws:iam::<12 digits>:role/<path>` if the agent should AssumeRole |
| `endpoint` | no | VPC endpoint / LocalStack override |

### Azure Key Vault

| Key | Required | Notes |
|---|---|---|
| `vaultName` | yes | the short vault name |
| `tenantId` | yes | tenant UUID |
| `clientId` | yes | workload identity client id |

### GCP Secret Manager

| Key | Required | Notes |
|---|---|---|
| `projectId` | yes | GCP project id (not the secrets-bridge project) |
| `serviceAccount` | no | impersonation target if not the default |

### Kubernetes

| Key | Required | Notes |
|---|---|---|
| `namespace` | no | scope discovery to a single namespace |

## Hard rules

EPIC P bakes several **non-negotiable** rules into the layer; trying to
violate them returns a stable 4xx with a structured envelope:

| Rule | How enforced |
|---|---|
| **No credentials in `scope`** | Service-layer refuses 14 credential-shaped keys (case-insensitive) — `aws_access_key_id`, `awsAccessKey`, `password`, `token`, `clientSecret`, `privateKey`, etc. Returns 400 `credential_in_scope` with the banned key. |
| **No secret-shaped values in `scope`** | Regex pass over every string value: AWS keys (`AKIA…`), Vault tokens (`hvs.…`), JWTs (`eyJ…`), Google OAuth (`ya29.…`). Returns 400 `secret_in_scope` with the field. Deployment-level override `SB_PROVIDER_CONN_REJECT_SECRETS=false` for emergencies; **audited at boot**. |
| **Valid provider URL** | Vault `address` parsed for scheme, no userinfo, no token-shaped query params. Returns 400 `invalid_provider_url`. |
| **Valid AWS role ARN** | `^arn:aws:iam::\d{12}:role/[A-Za-z0-9+=,.@_/-]+$`. Returns 400 `invalid_role_arn`. |
| **`discover_enabled=true ⇒ cluster_name IS NOT NULL`** | DB CHECK constraint + service-layer pre-flight. Returns 400 `discover_requires_cluster`. |
| **`last_discover_error` is sanitized** | Pre-persist pipeline: credential redaction → JSON blob strip → 280-char truncate (order is load-bearing — see [API + scope hard rules](#api-scope-hard-rules) below). |

The same sanitizer runs in two places — the api side (P2,
`api/pkg/sanitize.DiscoverError`) and the worker side (P4, defense in
depth before `MarkDiscoverFinished`). Belt + braces.

## Permissions

| Permission | Where it gates |
|---|---|
| `integration.edit` | Sidebar entry; admin list path; all CRUD; discover-now; bindings; delete |
| `secret.request` (scoped to project, env) | Developer dropdown — `GET /provider-connections?project_id=…&environment_id=…` returns only the bound connections, sanitized to `{id, name, type}` |

The same URL `GET /provider-connections` branches by query-string
shape:

- **No** `project_id` → admin path (`integration.edit` required). Full
  projection (scope, auth_method, discovery status).
- `project_id` + (optional `environment_id`) → developer dropdown
  (`secret.request` scoped). Sanitized projection: id + name + type
  only — never scope, auth_method, or discovery fields.
- `environment_id` **without** `project_id` → 400 `project_id_required`
  **before** any permission check (no enumeration leak).

## Discovery model

A discover job runs `ListMetadata` against the external store and upserts
the result into the `secrets` table — the discovery feed the UI's
[Secrets](../components/ui.md) page reads from.

| Setting | Behavior |
|---|---|
| `discover_enabled=false` | The worker scheduler never picks up this row. No periodic discovery. |
| `discover_enabled=true` + `cluster_name` set | The worker picks it up every `discover_interval_seconds`. |
| **Discover now** (admin button) | Manual one-off via `POST /provider-connections/:id/discover-now`. Requires `status=active` AND `cluster_name` set. Per-target Redis lock prevents concurrent re-trigger. |

### Status lifecycle

`provider_connections.last_discover_status` follows a strict state
machine:

```
NULL ── start ──▶ running ── success ──▶ success
                       ╰── failure ──▶ failure
                       ╰── 2× interval elapsed (worker sweeper) ──▶ failure
```

`MarkDiscoverFinished` rejects `running` as a terminal status —
terminal-only is `success` / `failure`. The worker's
`PostDiscoverScheduler` long-stale sweeper (worker#13, P-follow-up)
will flip rows stuck in `running` past `2 × discover_interval_seconds`.

### "Possibly stale" — UI-only derivation

The admin SPA's discover column renders a `warning` pill labelled
"possibly stale" when:

```
last_discover_status === 'running' AND
last_discover_started_at + 2 * discover_interval_seconds * 1000 < now
```

This is **pure client-side derivation** — no backend mutation. The pill
is a visual nudge that something needs operator attention; the connection
is still safe to use. The worker sweeper is the system-of-record for
reconciliation.

Operator escape hatch if you need to clear a "running" row manually:

```sql
UPDATE provider_connections
SET    last_discover_status = 'failure',
       last_discover_error  = 'cleared by operator',
       last_discover_at     = NOW(),
       updated_at           = NOW()
WHERE  id = $1
  AND  last_discover_status = 'running';
```

The audit trail will show the next discover scheduler tick as a fresh
`discover.start`; the previous stuck row's history stays in
`audit_events`.

## Disable semantics

Flipping `status` from `active` to `disabled` is **graceful** — it
doesn't blow up in-flight requests, but it stops every new dependency:

| What stops | What doesn't |
|---|---|
| Dropdown returns the row (developers can't pick it for new submits) | Existing bindings stay in the table |
| Periodic discovery scheduler skips the row | `secrets` rows previously discovered remain queryable |
| Manual "Discover now" returns 409 `connection_disabled` | Audit history stays intact |
| Cross-team submit with a disabled destination returns 409 `connection_disabled` | In-flight requests that *already* enqueued an agent job complete normally — the agent fails at provider resolve time and the request transitions to `failed` |
| New requests can't pick the row | Re-enabling restores everything; no data migration needed |

The "fail at agent resolve" path is intentional. The api can't reach back
into queued sync jobs to invalidate them, so the agent's executor is the
last line of defense for a destination that disappeared between enqueue
and claim.

## Scoped bindings (`integration.bind`)

EPIC Q (api#99) added a project-scoped permission so section heads can
self-serve binds on their own projects without holding the global
`integration.edit`. Platform retains full control over connection
lifecycle (create, update, delete, discover-now); scoped users can only
bind / unbind, and only on connections platform has explicitly enabled
for self-service.

### `self_service_bindable` — the platform opt-in flag

Migration 0031 added a `BOOLEAN NOT NULL DEFAULT false` flag on
`provider_connections`. Default-deny: every existing row stays
invisible to `integration.bind` callers until platform flips the flag
via the admin SPA's connection edit drawer.

```sql
ALTER TABLE provider_connections
    ADD COLUMN self_service_bindable BOOLEAN NOT NULL DEFAULT false;
```

A connection that is `self_service_bindable=false` behaves exactly as
before EPIC Q — only `integration.edit` callers see and bind it.

### Hard rules for scoped binders

| Action | Rule |
|---|---|
| Bind | Requires `environment_id` in the body. Project-wide bindings (`environment_id IS NULL`) are platform-only. |
| Bind | Refused on `env.kind='prod'` — production bindings are platform-team territory. |
| Bind | Refused on `status='disabled'` connections (409 `connection_disabled`). |
| Bind | Refused on `self_service_bindable=false` connections (403 `connection_not_self_service_bindable`). |
| Unbind | Allowed regardless of current `self_service_bindable` — cleanup is always allowed for bindings the user could have created. |
| Unbind | Refused on `env.kind='prod'` — admin path required. |
| Unbind | Refused on project-wide bindings (`environment_id IS NULL`) — platform-only. |
| Both | Requires actor coverage of `(project_id, environment_id)` via the existing team-aware resolver. |

### `integration.edit` does NOT auto-cover `integration.bind` server-side

This is a deliberate decision per the §2 Q6 sign-off. Granting an
operator `integration.edit` does **not** automatically grant them
`integration.bind` at the API layer — the api treats the two
permissions as distinct. The SPA's capability helper unifies them in
the UI (admins get the binder CTA on every env page for ergonomics),
but the api still gates each endpoint strictly.

**Operator implication:** if you want a section head to self-serve
binds, grant them the `provider_connection_binder` role (or any role
carrying `integration.bind`) scoped to their team or project. Granting
`integration.edit` alone won't enable the project-anchored URLs.

### The `provider_connection_binder` seed role

Migration 0032 seeds a system role scoped to one capability:

```
Role:         provider_connection_binder
Permission:   integration.bind
Scope at:     user_roles.scope = {project_id: "..."} OR {team_id: "..."}
is_system:    true (editable, not deletable)
Auto-granted: no — operators grant explicitly
```

Team-scoped grants automatically cover the team's descendant project
subtree via the team-aware resolver (the same expansion EPIC L Slice 2
set up for `secret.approve`).

### Capability helper pattern in the SPA

The SPA decides which endpoint family to hit by reading two capability
helpers (`canBindProviderConnectionOnEnv` + `canUnbindBinding`), each
returning `{allowed, via}` where `via` is the permission that carried
the action:

| `via` | URL family used |
|---|---|
| `integration.edit` | `POST /provider-connections/:id/bindings` + `DELETE /provider-connection-bindings/:id` (admin) |
| `integration.bind` | `POST /projects/:id/provider-connection-bindings` + `DELETE /projects/:id/provider-connection-bindings/:bid` (scoped) |
| `null` | UI hides the action — server still enforces a stable 403 if anyone tries |

The generic `hasPermission('integration.bind')` keeps its strict
semantic everywhere else in the SPA — it returns `true` only for
explicit `integration.bind` grants. The capability helpers are the
ONLY place that knows "admin can act on every env including prod via
the admin URLs."

### Triage SQL — scoped bindings

**What connections are currently bindable for self-service:**

```sql
SELECT id, name, type, cluster_name
FROM provider_connections
WHERE status = 'active' AND self_service_bindable = true
ORDER BY name;
```

**Recent out-of-scope binding probes (security signal — operators
should know when section heads are reaching outside their subtree):**

```sql
SELECT occurred_at, actor,
       metadata->>'attempted_project_id'      AS attempted_project,
       metadata->>'attempted_environment_id'  AS attempted_env,
       metadata->>'actor_permission_attempted' AS perm
FROM audit_events
WHERE action = 'binding.denied_out_of_scope'
ORDER BY occurred_at DESC
LIMIT 20;
```

Note: this audit event deliberately omits `provider_connection_id` —
the gate-order protection means the actor failed coverage BEFORE the
connection was loaded, and including it would defeat the whole
enumeration-leak protection.

**Bind-path breakdown (last 7 days — who's using scoped vs admin?):**

```sql
SELECT
  count(*) FILTER (WHERE metadata->>'actor_permission_used' = 'integration.bind') AS scoped_binds,
  count(*) FILTER (WHERE metadata->>'actor_permission_used' = 'integration.edit') AS admin_binds
FROM audit_events
WHERE action = 'binding.create'
  AND occurred_at > NOW() - INTERVAL '7 days';
```

**Bindings owned by a specific actor (incident response — when a
section head's account is compromised):**

```sql
SELECT occurred_at,
       metadata->>'provider_connection_id' AS connection_id,
       metadata->>'project_id'             AS project_id,
       metadata->>'environment_id'         AS environment_id
FROM audit_events
WHERE action IN ('binding.create', 'binding.delete')
  AND actor = $1
ORDER BY occurred_at DESC;
```

### Operator playbook

**To enable a connection for self-service:**

1. Sign in as platform admin (holds `integration.edit`).
2. Navigate to `/admin/provider-connections` → edit the connection.
3. Flip the `Self-service bindable` toggle on. Save.
4. The connection now appears in scoped binders' picker drawer for
   any project/env they cover (non-prod only).

**To grant a section head bind capability:**

1. Identify the team or project subtree the section head should cover.
2. Assign the `provider_connection_binder` system role scoped to that
   team_id (preferred — covers the descendant project subtree
   automatically) or project_id (one project only).
3. The section head can now bind any `self_service_bindable=true`
   connection to non-prod envs in their subtree via the per-env card
   on `/projects/:id/env/:env_id`.

**To audit recent self-service activity:**

Run the three SQL queries above. Combine with the existing
`audit_events` correlation_id chain to reconstruct the full lifecycle
of a binding from creation through eventual cross-team request use.

**To revoke a section head's bind capability without touching their
existing bindings:**

1. Revoke the `provider_connection_binder` role assignment (via
   `/admin/assignments` or `DELETE /user-roles/:id`).
2. Their existing bindings remain in place — revoking the role does
   NOT cascade-unbind. If you need to remove specific bindings, the
   platform admin uses the admin URL family.

### Observability — Prometheus counters

EPIC Q added three counters scraped from `/metrics`:

```
provider_connection_bindings_created_total{permission_used, env_kind}
provider_connection_bindings_deleted_total{permission_used, env_kind}
provider_connection_bindings_denied_total{reason}
```

`reason` is a fixed low-cardinality set:
`out_of_scope`, `prod_blocked`, `not_self_service_bindable`,
`connection_disabled`, `connection_not_found`, `env_not_in_project`,
`binding_exists`, `binding_not_found`.

**LOW-CARDINALITY LOCK:** the counters never carry `actor_id`,
`project_id`, `connection_id`, or `environment_id` as labels — those
go to the audit trail, not Prometheus. A `denied_total{reason="prod_blocked"}`
spike on the dashboard means "scoped binders are running into the
prod wall a lot," not "any specific row is misconfigured." Pair with
the audit triage SQL above to find the actor + project + env.

## Triage SQL

**Active connections per cluster:**

```sql
SELECT cluster_name,
       count(*) FILTER (WHERE status = 'active' AND discover_enabled) AS discovering,
       count(*) FILTER (WHERE status = 'active') AS active_total,
       count(*) FILTER (WHERE status = 'disabled') AS disabled
FROM provider_connections
GROUP BY cluster_name
ORDER BY cluster_name;
```

**Rows stuck running past 2× interval (the worker sweeper's targets):**

```sql
SELECT id, name, type, cluster_name,
       last_discover_started_at,
       discover_interval_seconds,
       NOW() - last_discover_started_at AS elapsed
FROM provider_connections
WHERE last_discover_status = 'running'
  AND last_discover_started_at + (discover_interval_seconds * 2) * INTERVAL '1 second' < NOW()
ORDER BY last_discover_started_at;
```

**Connections that never successfully discovered:**

```sql
SELECT id, name, type, cluster_name, discover_enabled, last_discover_status, last_discover_at
FROM provider_connections
WHERE discover_enabled
  AND (last_discover_at IS NULL OR last_discover_status <> 'success')
ORDER BY created_at;
```

**Audit replay for one connection:**

```sql
SELECT created_at, action, actor, metadata
FROM audit_events
WHERE resource = 'provider_connection'
  AND metadata ->> 'provider_connection_id' = $1
ORDER BY created_at;
```

**Bindings + open requests against one connection (matches the 409
`connection_in_use` body):**

```sql
SELECT
  (SELECT count(*) FROM project_provider_connections
   WHERE provider_connection_id = $1)                     AS bindings_count,
  (SELECT count(*) FROM access_requests
   WHERE status IN ('pending', 'pending_values', 'pending_verification')
     AND destination_provider_connection_id = $1)         AS open_requests_count;
```

## API + scope hard rules

The 9 endpoints are documented at
[HTTP API endpoints — Provider connections](../reference/api-endpoints.md#provider-connections).

Every endpoint returns errors in the **EPIC P envelope** — distinct from
the legacy `{code, error}` shape some older endpoints still use:

```json
{
  "error_code": "credential_in_scope",
  "message":    "scope contains a credential-shaped key",
  "banned_key": "awsAccessKeyID"
}
```

19 stable error codes — see the
[Error code reference](#error-code-reference) below.

The sanitizer pipeline ordering for `last_discover_error` is
**load-bearing**:

```
credential redaction (AKIA…, hvs.…, JWT, OAuth) → JSON blob strip → truncate to 280 chars
```

Truncating first would lose credentials that span the cut point — a
provider error like `"failed: token=hvs.AAAA…"` truncated to 280 chars
might cut the token mid-string but still leak its prefix. Redacting
first guarantees no credential-shaped substring survives the truncate.

## Cross-team destination wiring

The cross-team submit drawer (Slice N5) reads its destination dropdown
from `GET /provider-connections?project_id=…&environment_id=…` — the
sanitized projection. The connection must be **bound to the source
project + env** for it to appear. If the dropdown is empty, the drawer
branches:

- Caller has `integration.edit` → a "Manage provider connections" link
  to `/admin/provider-connections`
- Caller doesn't → "Ask your platform / admin team to bind a provider
  connection to this project"

This is the same dropdown that powers any future "destination picker"
flows; the developer never sees the connection's scope, auth method, or
discovery state — just its name and provider type.

See also: [Cross-team requests — Target vs destination](cross-team-requests.md#target-vs-destination).

## SB_DISCOVER_TARGETS_JSON deprecation

P4 (worker#14) replaced the env-var-driven scheduler with the DB-backed
one this page documents. The env var is kept as a **fallback only**:

- If the DB returns at least one row that's due for discovery, the env
  var is **ignored entirely** and a WARN log fires per scheduler tick:
  > `SB_DISCOVER_TARGETS_JSON is ignored because DB-backed discover targets exist`
- If the DB returns zero rows AND the env var is set, the worker runs
  the env-var fallback with a deprecation WARN:
  > `SB_DISCOVER_TARGETS_JSON fallback is in use`

Both messages include the calendar deadline verbatim:

> `SB_DISCOVER_TARGETS_JSON is deprecated and will be removed 3 months after DB-backed provider connection discovery ships.`

**Removal target: 3 months after P4 merges.** Migrate by creating one
provider connection per env-var entry, then unsetting the env var.
worker#13 (P-follow-up) tracks the final removal.

## Live end-to-end walkthrough

The full P loop against the docker-compose stack from
[Deploying with docker-compose](docker-compose.md):

1. **Admin creates `vault-prod`** —
   `POST /provider-connections` with `type=vault`, `cluster_name=cluster-a`,
   `scope={"address":"https://vault.example.com", "kvMount":"secret"}`,
   `discover_enabled=true`, `discover_interval_seconds=3600`. Returns 201
   with the new row.
2. **Admin binds to `tenant-a/prod` + `tenant-a` (project-wide)** —
   two `POST /provider-connections/:id/bindings` calls. Both 201.
3. **Developer in `tenant-a/prod` opens cross-team submit** — drawer's
   destination dropdown shows `vault-prod (vault)` and nothing else.
   Sanitized projection — no scope, no auth method, no discovery state.
4. **Admin disables `vault-prod`** — `PUT /provider-connections/:id`
   with `status=disabled`. Drawer dropdown is empty on next render.
   Caller has `integration.edit` → "Manage provider connections" link
   surfaces. Caller doesn't → "Ask your platform team" text surfaces.
5. **Admin re-enables** — drawer dropdown shows `vault-prod` again.
6. **Admin clicks "Discover now"** —
   `POST /provider-connections/:id/discover-now` returns 202 with
   `job_id` + `correlation_id`. SPA row flips to `running` pill.
   Worker claims + executes the job; api `OnDiscoverJobCompleted`
   hook flips the row to `success`.
7. **Developer submits a cross-team request** picking `vault-prod`
   as the destination. Request lands in the source-team approver's
   inbox; agent eventually writes values to `secret/data/<ref>`.
8. **Admin tries to delete `vault-prod`** — returns 409
   `connection_in_use` with the count envelope:
   ```json
   {"error_code":"connection_in_use","message":"…","bindings_count":2,"open_requests_count":1}
   ```
   SPA's "Delete anyway" button stays disabled while either count is
   > 0.
9. **Approver closes the open request; admin unbinds both bindings**
   via `DELETE /provider-connection-bindings/:bid` ×2. Counts drop to
   0. Delete succeeds (204).
10. **Worker sweep with `SB_DISCOVER_TARGETS_JSON` ALSO set** — start
    the worker with the env var pointed at a separate fake target
    AND with a DB row due for discovery. The WARN log fires; only the
    DB target is enqueued. Then a canary scan confirms no plaintext
    leaks anywhere:

    ```sql
    SELECT count(*) FROM provider_connections
    WHERE last_discover_error ~ 'AKIA[A-Z0-9]{16}'
       OR last_discover_error ~ 'hvs\.[A-Za-z0-9_-]{20,}'
       OR last_discover_error ~ 'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+'
       OR last_discover_error ~ 'ya29\.[A-Za-z0-9_-]+';

    SELECT count(*) FROM audit_events
    WHERE metadata::text ~ 'AKIA[A-Z0-9]{16}'
       OR metadata::text ~ 'hvs\.[A-Za-z0-9_-]{20,}';
    ```

    Both counts must be `0`. They are, because the sanitizer pipeline
    redacts before persistence.

## Error code reference

23 stable codes — 19 from the EPIC P §6.A locked spec, plus 4 added
by EPIC Q (api#99). Returned in the `{error_code, message, …}`
envelope. The SPA maps every code to a friendly toast string via
`providerConnectionErrorMessage`; operators running raw `curl` see
the code in the body.

| Code | Status | Meaning |
|---|---|---|
| `connection_not_found` | 404 | The `:id` doesn't resolve |
| `connection_name_taken` | 409 | A connection with this name already exists |
| `invalid_scope` | 400 | Scope is missing required keys or carries unknown keys; envelope adds `missing_keys` + `unknown_keys` arrays |
| `credential_in_scope` | 400 | Scope has a credential-shaped key; envelope adds `banned_key` |
| `secret_in_scope` | 400 | A scope value looks like a secret; envelope adds `field` |
| `invalid_provider_url` | 400 | URL fails semantic validation; envelope adds `field` + `reason` |
| `invalid_role_arn` | 400 | ARN doesn't match `^arn:aws:iam::\d{12}:role/…$` |
| `description_too_long` | 400 | > 500 characters; envelope adds `length` + `cap` |
| `discover_requires_cluster` | 400 | `discover_enabled=true` with `cluster_name` null |
| `invalid_discover_interval` | 400 | Interval outside 60..86400 |
| `invalid_discover_status` | 400 | Transitioning to a non-terminal status (e.g. `MarkDiscoverFinished('running')`) |
| `connection_in_use` | 409 | DELETE blocked; envelope adds `bindings_count` + `open_requests_count` |
| `connection_disabled` | 409 | Action requires `status=active` (Discover now / cross-team destination / scoped bind) |
| `binding_exists` | 409 | (project, env) already bound |
| `binding_not_found` | 404 | Unbind on a missing binding id, OR scoped DELETE where the URL `projectID` doesn't match the binding's stored `project_id` (§4 correction — NEVER `out_of_scope_binding` on mismatch, which would leak existence) |
| `environment_not_in_project` | 400 | Binding references an env that doesn't belong to the project |
| `project_id_required` | 400 | `environment_id` or `for_binding=true` passed without `project_id` to the shared GET |
| `discovery_already_running` | 409 | Per-target Redis lock held — another Discover now is in flight |
| `out_of_scope_project` | 403 | Dropdown caller lacks `secret.request` scoped to (project, env) |
| `connection_not_self_service_bindable` | 403 | EPIC Q — scoped caller tried to bind a connection where `self_service_bindable=false`. Platform must opt the connection in via the admin SPA. |
| `prod_binding_not_allowed_for_scope` | 403 | EPIC Q — scoped caller tried to bind / unbind on `env.kind='prod'`. Envelope includes `{"env_kind": "prod"}`. Admin path (`integration.edit`) required for prod bindings. |
| `out_of_scope_binding` | 403 | EPIC Q — caller's `integration.bind` grant doesn't cover the target (project, env) per the team-aware resolver. Audit emits `binding.denied_out_of_scope` (security signal). |
| `environment_id_required` | 400 | EPIC Q — the binder picker (`for_binding=true`) or scoped bind body lacks `environment_id`. Scoped binders never create project-wide bindings. |

## Related

- [Cross-team requests](cross-team-requests.md) — the destination
  dropdown's primary consumer
- [Project environments](project-environments.md) — connections bind at
  project ± env granularity
- [HTTP API endpoints](../reference/api-endpoints.md#provider-connections)
  — full request/response shapes
- [Permissions catalog](../reference/permissions.md) — `integration.edit`
  reused (no new permission)
- [Worker — discover scheduler](../components/worker.md) — implementation
  of the DB-backed scheduler
