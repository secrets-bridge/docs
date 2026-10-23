# Reveal sessions

Slice M introduced **reveal sessions**, the time-limited bulk-reveal
surface that replaces the per-row "click, see one secret, modal
closes" flow from earlier slices. This page is the operator-facing
reference: what a session is, what knobs control it, what
invariants the system holds during the open window, and what
happens when the window closes.

If you came here from
[Policy templates](policy-templates.md#anatomy-of-a-policy-rule)
looking for `reveal_ttl_seconds`, the section
[**TTL, `reveal_ttl_seconds`**](#ttl-reveal_ttl_seconds) is the
short answer.

## What a reveal session is

A reveal session is a **server-side breadcrumb** that pairs the
SPA's visible-plaintext window with a TTL anchor. It is created when
the developer clicks "Reveal" on an approved (or auto-executed via
[direct reveal](policy-templates.md#template-1-non-prod-direct-reveal))
read request. The row lives in `reveal_sessions` and carries:

| Column | Purpose |
|---|---|
| `user_id` | Caller identity. Only this user can expire or list the session. |
| `project_id` / `environment_id` | Scope binding so the audit trail tells operators which surface a reveal opened on. |
| `access_request_id` | The read request whose wraps this session bundles. |
| `wrap_ids` | The `secret_wraps` rows the session has authority to reveal. |
| `ttl_seconds` | Server-enforced TTL (see below). |
| `opened_at` / `expires_at` | The window. |
| `expired_at` + `expired_reason` | Set when the session ends, `ttl` (sweeper), `user_hide` (Hide Now), or `unmount` (SPA navigated away). |

The row **never** carries a plaintext value. The plaintexts live in
the SPA's React state during the open window and are wiped at TTL=0
or earlier on Hide Now / unmount.

## How it differs from the request-flow single-shot retrieval

Before Slice M, the only way to retrieve a value was the per-wrap
single-shot endpoint
([`GET /api/v1/requests/:id/wraps/:wrap_id`](../reference/api-endpoints.md)).
Each click consumed exactly one wrap; the user typed in the SPA's
modal, copied, closed, and to view another key they clicked again
on another wrap.

The reveal session is **bulk + time-bound** instead:

| | Single-shot (pre-M) | Reveal session (M) |
|---|---|---|
| Plaintexts shown | One per click | All at once, in a table |
| Server-side surface | One endpoint per click | One Open + N existing single-shot fetches |
| TTL anchor | Per-wrap `expires_at` only | Session `expires_at` AND per-wrap `expires_at` (advanced in lockstep on expiry) |
| Operator audit row | `wrap.retrieve` per click | `reveal.session.opened` once + `wrap.retrieve` per fetch + `reveal.session.expired` |
| UX | Modal per key | Page with a countdown |

The single-shot flow still exists, `RevealModal` in the request
detail page uses it for legacy flows. The reveal session is the new
default for the direct-reveal path; approval-flow reads still pass
through the modal until Slice N migrates them.

## Lifecycle

```text
SPA opens session   →   POST /api/v1/reveal-sessions { access_request_id }
                        ←  { session_id, expires_at, ttl_seconds, wraps: [...] }
SPA fetches each    →   GET  /api/v1/requests/:id/wraps/:wrap_id  (× N)
plaintext (existing
single-shot path)
SPA renders table + countdown over expires_at - now
       │
       ├── countdown hits 0  ──→ React state cleared; copy buttons disabled
       │                        worker sweeper marks session expired (reason='ttl')
       │                        worker sweeper advances wrap.expires_at = now
       │                        any further GET on a wrap_id → 410
       │
       ├── user clicks Hide Now ─→ POST /api/v1/reveal-sessions/:id/expire { reason: 'user_hide' }
       │                          api advances wrap.expires_at = now
       │                          state cleared client-side
       │
       └── tab navigates away  ─→ POST /api/v1/reveal-sessions/:id/expire { reason: 'unmount' }
                                  (fire-and-forget; sweeper is the safety net)
```

## TTL, `reveal_ttl_seconds`

TTL is **policy-driven**, not caller-driven. The matched
[policy rule's](policy-templates.md#anatomy-of-a-policy-rule)
`reveal_ttl_seconds` column anchors how long the session lives.

| Knob | Where | Range | Default |
|---|---|---|---|
| `reveal_ttl_seconds` | `policy_rules` row | 10..300 | 60 (seed rule) |

PRD-recommended values:

| Environment kind | Suggested TTL | Why |
|---|---|---|
| `non_prod` | 120 s | Comfortable read-and-copy window |
| `prod` | 60 s | Tighter on real-data surfaces |

The api **clamps** out-of-range values defensively (the schema CHECK
also rejects them, but the service-layer clamp guards legacy /
imported rules); a value of 0 falls back to 60.

The TTL is **not** the wrap's TTL, that comes from the workflow's
`wrap_ttl_*` columns. `reveal_ttl_seconds` only bounds the session
window. When the window expires (or on Hide Now), the underlying
wraps' `expires_at` is advanced to "now" so a leaked wrap_id is
unusable after the window, see
[The server-side guarantee](#the-server-side-guarantee) below.

## Hard rules

The platform holds these invariants by construction (schema, code,
and the worker sweeper). Operators do not need to wire them.

| Rule | How enforced |
|---|---|
| **No secret values in PostgreSQL** (outside the KMS-wrapped `secret_wraps.encrypted_value` column) | The `reveal_sessions` table has no value column; only `wrap_ids` (UUIDs). Canary tests scan `reveal_sessions::text` after every Open. |
| **No secret values in Redis** | The api never writes plaintext to Redis; sessions are Postgres-only. |
| **No secret values in logs** | The `reveal.session.opened` audit metadata carries `key_names[]` only, never values. The api's structured logger never receives plaintext. |
| **No secret values in API errors** | All error paths return generic messages; the canary scan asserts the same against `audit_events.metadata`. |
| **No secret values in browser state after expiry** | The SPA holds plaintext in React refs only; the TTL=0 effect rewrites every row's value to the empty string. No `localStorage` / `sessionStorage` / cookie writes anywhere in the page. |
| **No re-reveal after expiry** | Wraps are single-shot AND `expires_at`-bounded; once the sweeper advances them, the user-bound retrieve endpoint returns 410. |
| **Caller owns the session** | Open binds `user_id`; the expire endpoint refuses non-owners with 403; ListActive filters by caller. |

## The server-side guarantee

The promise this slice makes: **when a session expires, the wraps it
issued become unreachable**. The worker sweeper
(`reveal-sessions-expired`) closes the window in two steps:

1. Atomic `UPDATE … RETURNING` against `reveal_sessions`: every row
   whose `expires_at <= now() AND expired_at IS NULL` is marked
   expired with `reason='ttl'`. The query returns the
   `(session_id, wrap_ids)` pairs so the sweeper can advance each
   wrap in lockstep.
2. For each wrap_id from the returned set: `UPDATE secret_wraps SET
   expires_at = now()`. Any further user-bound retrieve returns 410
   (the storage layer's `expires_at` filter does the rejection).

This holds even when the SPA has already cleared its plaintext: a
leaked wrap_id is **server-side unusable** after the session ends.

The sweeper runs at `SB_WORKER_REVEAL_SESSIONS_EXPIRED_INTERVAL`
(default `5s`), fast enough that a leaked wrap_id stays unusable
within a few seconds of TTL elapse. See
[Configuration reference](config.md) for the full env var.

## Copy All policy

PRD §15 calls out a Copy-All button on the bulk reveal page. Today
the UI ships a per-row Copy CTA only, Copy-All is a future PRD §15
follow-up that will be **disabled by default in PROD** via a policy
knob (the exact column is TBD; the contract is: PROD environments
must opt in explicitly, non-PROD environments default opt-out unless
the policy rule turns it on).

When Copy-All ships, the policy_rules surface will likely grow a
`copy_all_allowed bool` column. Operators planning Slice N work
should anticipate this and avoid scripting against `policy_rules`
columns as if the set is stable.

## Operator queries

### "What reveal sessions are open right now?"

```sql
SELECT id, user_id, project_id, environment_id,
       opened_at, expires_at,
       array_length(wrap_ids, 1) AS wrap_count
FROM reveal_sessions
WHERE expired_at IS NULL
ORDER BY opened_at DESC
LIMIT 50;
```

### "Did the worker sweeper close every past-TTL session?"

```sql
SELECT count(*) AS overdue
FROM reveal_sessions
WHERE expired_at IS NULL
  AND expires_at < now() - INTERVAL '30 seconds';
```

A non-zero count means the sweeper has not run since the row aged
past TTL, investigate the worker. The `worker_scheduler_runs_total
{task="reveal-sessions-expired"}` Prometheus counter is the
authoritative liveness signal.

### "Trace one user's reveal history"

```sql
SELECT created_at, action, resource, metadata
FROM audit_events
WHERE actor = 'user:alice'
  AND action LIKE 'reveal.session.%'
ORDER BY created_at DESC
LIMIT 100;
```

The `reveal.session.opened` row carries `key_names[]` so you can
see **which keys** were exposed without ever holding the values.

## Related

- [Policy templates](policy-templates.md), how to wire
  `reveal_ttl_seconds` per (project, env) scope
- [Project environments](project-environments.md), the `kind=prod`
  hard boundary the PolicyEngine enforces alongside reveal sessions
- [API endpoints](../reference/api-endpoints.md#reveal-sessions), the
  three HTTP routes this surface exposes
- [Configuration reference](config.md), the worker sweeper interval
- [Cross-team requests](cross-team-requests.md), reveal sessions also
  work for `type='cross_team'` requests after Slice N; the SPA flow
  is the same as for read requests.
