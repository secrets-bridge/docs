# Cross-team requests

A cross-team request is a value handoff between two teams that don't
share direct access to each other's secrets. **Team A** owns a workload
that needs a value. **Team B** owns the value. Team A submits the
request; a Team B member fills it; a Team A approver (and, when policy
requires it, a security approver) verifies; the agent writes the value
into Team A's provider. The original Team B member never touches Team A's
workload, and Team A never sees Team B's source of truth.

Cross-team requests are the safe alternative to "share me your prod
secret" Slack messages — every value handoff lands in the audit log
with a justification, a workflow snapshot, and a separation-of-duties
trail.

This page covers the operator-facing model: the state machine, the
permission matrix, the workflow knobs you can tune, and the SQL +
metrics you'll use to triage. The SPA flow is described from the user's
point of view inline; the API contract is at
[HTTP API endpoints — Cross-team requests](../reference/api-endpoints.md#cross-team-requests).

## Target vs destination

Every cross-team request carries two scopes. They look similar but
mean opposite things, and operator queries get them confused often
enough that we make the distinction here.

| Scope | Means | Example |
|---|---|---|
| **Target** (`target_team_id` + `target_project_id` + `target_environment_id`) | The team / project / env that **provides** the value. Team B's territory. The inbox is computed against this. | `team-alpha` / `team-alpha-billing` / `prod` |
| **Destination** (`destination_provider_connection_id` + `destination_secret_ref` + `destination_keys`) | Where the value **lands** after approval. Team A's territory. The agent writes here. | `vault-prod` / `tenant-a/web/db` / `["DB_PASSWORD", "DB_USER"]` |

The destination provider connection MUST be bound to the **source**
project (Team A's project). The submit endpoint rejects
`destination_provider_unbound` if the provider connection doesn't
belong to the source project. This is the architectural fence that
keeps Team B from accidentally writing into Team A's neighbours.

## State machine

```
                       ┌─ refused (Team B refused)
                       │
        submit ─→ pending_values ─→ pending_verification ─→ approved ─→ executed
                       │                  │                    │
                       │                  └─ rejected          └─ failed
                       │                  
                       └─ expired (fill_ttl elapsed)
                       │
                       └─ cancelled (requester withdrew)
```

| Status | Meaning | Who transitions it |
|---|---|---|
| `pending_values` | Waiting on Team B to fill | Filler (POST /fill → pending_verification) or Refuser (POST /refuse → refused) or sweeper (TTL → expired) or requester (POST /cancel → cancelled) |
| `pending_verification` | Filled, waiting on source (and optionally security) approval | Source approver via POST /verify (`voted_as=source`); security approver via POST /verify (`voted_as=security`) |
| `approved` | All required votes recorded; job enqueued | JobService transitions it on agent's `succeeded` (→ executed) or `failed` (→ failed) |
| `executed` | Agent wrote the value to the destination provider | Terminal |
| `failed` | Agent reported job failure | Terminal |
| `refused` | Team B declined to provide the value | Terminal — requester sees the refuse reason |
| `rejected` | Source or security approver rejected | Terminal — requester sees the rejection reason |
| `cancelled` | Requester withdrew | Terminal |
| `expired` | Fill window elapsed before Team B filled | Terminal |

Terminal states never transition. The
[N4 worker sweeper](#worker-sweepers) handles the expired path so the
observable state catches up even when no fill attempt arrives.

## Separation of duties

The cross-team flow enforces a four-actor matrix. No single user can
play more than one role on the same request — the API checks at every
mutation:

```
requester  ≠  filler  ≠  source approver  ≠  security approver
```

| Action | Blocked when actor is also… |
|---|---|
| POST /fill | requester |
| POST /verify (`voted_as=source`) | requester or filler |
| POST /verify (`voted_as=security`) | requester or filler or the source approver on this same request |

`secret.security.approve` is a **global** permission in v1, so a single
user can carry both source and security capability. The SoD check
catches the case where they try to cast both votes on the same request
— the second attempt returns 403 with
`separation_of_duties_violated`.

The SPA mirrors the API: the verify card hides the buttons the caller
cannot use AND renders the reason ("You provided the values for this
request.") so the operator knows they aren't broken — they're blocked
by design.

## Permissions and seed roles

Two new permissions land with Slice N:

| Permission | Scope | Description |
|---|---|---|
| `secret.value.provide` | **Team-scoped** (`team_id` in `user_roles.scope`) | Holder appears in the inbox for that team and can fill cross-team requests targeting it. The sidebar Inbox entry only renders for users holding this permission at any scope. |
| `secret.security.approve` | **Global in v1** | Holder can cast the security vote on cross-team requests where the bound workflow has `requires_security_approval=true`. Per-project / per-environment scoping is deferred to a follow-up. |

Two system roles ship as seed:

| Role | Permissions | Notes |
|---|---|---|
| `value_provider` | `secret.value.provide` | Assignment **must** carry a `team_id` in scope. The SPA's Assignments form enforces this with a "no team scope = global inbox access" type-to-confirm gate. |
| `security_approver` | `secret.security.approve` | Used carefully — a holder can bypass the source-side workflow on cross-team requests. The Roles editor surfaces a type-to-confirm dialog the first time `secret.security.approve` is added to a role. |

Both are `is_system=true`. The permission strings are editable, but the
roles cannot be deleted — `DELETE` returns 409 `system_row`.

## Workflow knobs

`workflow_definitions` gets two new columns for cross-team semantics:

| Column | Default | Use |
|---|---|---|
| `fill_ttl_seconds` | `86400` (24h) | How long Team B has to fill before the sweeper expires the request |
| `requires_security_approval` | `false` | When `true`, the bound request also needs a `voted_as=security` approve before transitioning to `approved`. PROD workflows typically flip this on. |

The full `min_approvers` table for cross-team:

| `min_approvers` | Semantics | Supported in v1 |
|---|---|---|
| `0` | Auto-approve on fill — verify is a no-op | ✓ |
| `1` | Single source approver required | ✓ |
| `≥ 2` | Multi-approver source side | **No** — `SubmitCrossTeam` returns 412 `cross_team_min_approvers_unsupported` |

Multi-approver cross-team is deferred to v2 because it requires a
distinct approvals counter on the request row vs the existing
`approvals` table. Operators who need it today are blocked at submit;
the error gives the SPA a clear toast.

### Workflow semantics frozen at submit

The bound workflow's `requires_security_approval` and `min_approvers`
values are snapshotted onto the request row at submit time
(`snap_requires_security_approval` + `snap_min_approvers` columns) so
that a later workflow edit doesn't retroactively change in-flight
semantics. The verify endpoint reads from the snapshot, not the live
workflow row.

This is load-bearing: if you turn `requires_security_approval=false`
to unblock an emergency, every request **submitted after that change**
gets the new behaviour, but every request **already in flight** still
needs the security vote it was submitted under. The audit log records
both the live workflow ID and the snapshotted bools.

## Hard rules — what NEVER touches the value

| Surface | Enforcement |
|---|---|
| PostgreSQL columns | `access_requests` carries no value columns; the agent's job consumes wraps via the same KMS-envelope path as the patch flow. The N1 schema CHECK constraints reject any cross-team row that's missing the target / destination / snapshot fields. |
| Redis | Used only for the inbox-count cache + idempotency tokens — no value cache. |
| Logs | The fill / refuse / verify handlers never log values, only key NAMES + actor identifiers. |
| API responses | The verify card response is value-free (no `content_hash`, no `byte_length`, no preview). The reveal session response is single-shot through the existing M-slice path. |
| Browser state | The SPA's fill page wipes the values from React state on submit success AND on component unmount. No localStorage / sessionStorage / IndexedDB writes anywhere in the flow. |
| Audit metadata | The audit log captures actor + key NAMES + workflow snapshot + correlation_id — never the value or any derivable canary. |

## Worker sweepers

The `cross-team-fill-window-expired` sweeper closes the fill window
for any `pending_values` request whose `fill_expires_at` has passed.

| Knob | Default | Use |
|---|---|---|
| `SB_WORKER_CROSS_TEAM_FILL_EXPIRED_INTERVAL` | `30s` | How often the sweeper runs. 30s is the right cadence because `fill_ttl_seconds` is hours-scale by default. |

The sweeper is defense in depth: the API's `Fill` check already
rejects late writers with `fill_window_expired`. The sweeper ensures
observable state (the inbox list, the request detail page, the
metrics) catches up within 30s even when no fill attempt arrives to
trigger that rejection.

Multi-replica safe — each worker takes a Redis lock on
`worker:sweeper:cross-team-fill-window-expired` per tick. Lock
contention is a metric, not a warning log.

## Reveal handling

Once a cross-team request lands in `executed`, the value is in the
destination provider — but the requester typically wants to see the
value once, in the SPA, to confirm the flow worked. That's exactly
what the existing reveal session page handles (Slice M).

The Slice M4 page accepts both `type='read'` and (after Slice N3)
`type='cross_team'` requests. The requester clicks "Reveal" from
the request detail page; the SPA opens a single-shot bulk session;
the page expires on TTL or on hide-now exactly like read flow.

The reveal session is bound to the **requester**, not the filler. The
filler never sees the value after submitting it — they handed it off
and the next time it appears, it's in the requester's provider.

## SPA surfaces

| Surface | Route | Caller permission |
|---|---|---|
| Submit drawer | `/projects/:id/env/:env_id` (third CTA) | `secret.request` |
| Inbox list | `/inbox` | `secret.value.provide` (any scope — fail-closed sidebar) |
| Fill / refuse | `/inbox/:request_id` | Same |
| Verify card | `/requests/:id` | `secret.approve` (source) and/or `secret.security.approve` (security) |
| Roles editor type-to-confirm | `/admin/roles` | `role.edit` |
| Assignments team-pick gate | `/admin/assignments` | `user_role.edit` |

Every cross-team mutation in the SPA invalidates both the request
detail query and the inbox queries so the sidebar badge updates on
the same tick the request transitions.

## Triage SQL

These queries assume `psql` against the API's Postgres.

**Open inbox by team**

```sql
SELECT id, requester_id, fill_expires_at, justification
FROM access_requests
WHERE type = 'cross_team'
  AND status = 'pending_values'
  AND target_team_id = $1
ORDER BY fill_expires_at;
```

**Pending verification per project**

```sql
SELECT id, requester_id, filled_by_user_id, filled_at, fill_comment
FROM access_requests
WHERE type = 'cross_team'
  AND status = 'pending_verification'
  AND source_project_id = $1
ORDER BY filled_at;
```

**Expired in the last 24h** (sweeper-flipped + service-layer-rejected)

```sql
SELECT id, requester_id, target_team_id, fill_expires_at, updated_at
FROM access_requests
WHERE type = 'cross_team'
  AND status = 'expired'
  AND updated_at > now() - interval '24 hours'
ORDER BY updated_at DESC;
```

**Audit chain for one request** — every transition surfaces with the
shared `correlation_id`:

```sql
SELECT created_at, action, actor, metadata
FROM audit_events
WHERE correlation_id = $1
ORDER BY created_at;
```

## Error code reference

The API returns stable codes the SPA maps to friendly messages. Operators
running curl smoke tests see the raw code in the response body.

| Code | Status | Meaning |
|---|---|---|
| `out_of_scope_team` | 403 | Caller doesn't cover this team's inbox |
| `out_of_scope_project` | 403 | Caller doesn't have access to this project |
| `separation_of_duties_violated` | 403 | Same actor tried to play two roles on one request |
| `cross_team_invalid_target` | 412 | Target team / project / env chain doesn't resolve |
| `cross_team_destination_unbound` | 412 | Destination provider connection isn't bound to the source project |
| `cross_team_keys_empty` | 412 | `destination_keys` is empty |
| `cross_team_already_filled` | 409 | Request is past `pending_values` |
| `fill_window_expired` | 410 | TTL elapsed before fill |
| `cross_team_min_approvers_unsupported` | 412 | Workflow `min_approvers ≥ 2` is not supported in v1 |
| `cross_team_status_invalid_transition` | 409 | Action doesn't apply to current status |
| `duplicate_vote` | 409 | Caller already voted on this request |
