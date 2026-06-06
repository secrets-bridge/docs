# HTTP API endpoints

Every route the api exposes today. Auth column shows what's
required to call it.

| Auth | Meaning |
|---|---|
| `public` | No auth — open route (probes, login) |
| `bearer` | A valid login JWT in `Authorization: Bearer <jwt>` |
| `bearer + perm` | Bearer JWT + the named permission via `auth.Require(perm)` |
| `agent` | An agent's `X-Agent-Secret` header (validated by `AgentAuth` middleware) |
| `user_id` | A `?user_id=<uuid>` query param matching the request's requester (stop-gap until OIDC) |

## Probes

| Method | Path | Auth | Notes |
|---|---|---|---|
| `GET` | `/healthz` | public | Always 200 |
| `GET` | `/readyz` | public | 200 when all readiness checks pass; 503 with per-check failure map otherwise |
| `GET` | `/metrics` | public | Prometheus exposition |

## Auth

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `/api/v1/auth/login` | public | `{email, password}` → `{token, expires_at, user}` |

## Agents

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `/api/v1/agents` | `bearer + agent.mint` | Mint; returns `agent_secret` ONCE |
| `GET` | `/api/v1/agents` | bearer | List (no credentials in projection) |
| `POST` | `/api/v1/agents/:id/revoke` | `bearer + agent.revoke` | Transition status → `revoked` |
| `PUT` | `/api/v1/agents/:id/public-key` | agent | Self-register X25519 wire-envelope pubkey |
| `POST` | `/api/v1/agents/:id/heartbeat` | agent | 204; bumps `last_seen_at` |
| `POST` | `/api/v1/agents/:id/jobs/claim` | agent | 200 with job or 204 (queue empty) |
| `POST` | `/api/v1/agents/:id/jobs/:job_id/complete` | agent | `{status, error?}`; 204 |
| `POST` | `/api/v1/agents/:id/dek` | agent | Issue a KMS-wrapped DEK for wire-envelope encryption |
| `POST` | `/api/v1/agents/:id/wraps` | agent | Read flow: agent posts a fetched value |
| `GET` | `/api/v1/agents/:id/wraps/:wrap_id` | agent | Patch flow: agent retrieves a value (single-shot) |
| `POST` | `/api/v1/agents/:id/secrets/bulk` | agent | Discovery: bulk-upsert discovered secrets |

## Requests (access requests)

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `/api/v1/requests` | bearer | Submit a patch request |
| `POST` | `/api/v1/requests/read` | bearer | Submit a read request |
| `GET` | `/api/v1/requests` | bearer | List with `?requester_id` + `?status` filters |
| `GET` | `/api/v1/requests/:id` | bearer | Get one + inline approvals |
| `POST` | `/api/v1/requests/:id/approve` | bearer | `{approver_id, comment?}` |
| `POST` | `/api/v1/requests/:id/reject` | bearer | `{approver_id, reason}` |
| `POST` | `/api/v1/requests/:id/cancel` | bearer | `{actor_id}` — only the requester |
| `GET` | `/api/v1/requests/:id/wraps` | user_id | List value-free wrap summaries |
| `GET` | `/api/v1/requests/:id/wraps/:wrap_id` | user_id | Single-shot retrieve (consumes) |
| `GET` | `/api/v1/requests/:id/gitops` | user_id | BRD §26 observation list (404 when feature is off) |

## Cross-team requests

Slice N — Team A → Team B value handoff. See
[Cross-team requests](../operations/cross-team-requests.md) for the
operator model, state machine, and SoD matrix.

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `/api/v1/requests/cross-team` | `bearer + secret.request` | `{target_team_id, target_project_id, target_environment_id, destination_provider_connection_id, destination_secret_ref, destination_keys[], justification}` → `AccessRequest`. Refuses `min_approvers ≥ 2` with `cross_team_min_approvers_unsupported`. NO values in body — destination_keys is the NAME list. |
| `POST` | `/api/v1/requests/:id/fill` | `bearer + secret.value.provide` | `{key_values: {<key>: base64}, fill_comment?}`. Late writers get `fill_window_expired` (410). Same-actor-as-requester returns `separation_of_duties_violated` (403). |
| `POST` | `/api/v1/requests/:id/refuse` | `bearer + secret.value.provide` | `{reason}` (≥ 10 chars). Transitions to `refused`. |
| `POST` | `/api/v1/requests/:id/verify` | `bearer + secret.approve` or `secret.security.approve` | `{decision, voted_as, comment?}` → **200 OK** with structured `VerifyResponse` (NOT 412 on partial votes). Body: `{vote_recorded, voted_as, source_votes, security_approval_required, security_vote_present, next_required[]}`. |
| `GET` | `/api/v1/requests/inbox` | `bearer + secret.value.provide` | `?team_id=` narrows to one team's inbox. Returns `AccessRequest[]` with `pending_values` status. Fail-closed: empty array when caller covers no teams. |
| `GET` | `/api/v1/requests/inbox/count` | `bearer + secret.value.provide` | `{total, per_team: [{team_id, team_name?, count}]}` — drives the sidebar badge. |
| `GET` | `/api/v1/provider-connections?project_id=:id` | bearer | Returns the connections bound to that project; the SPA's cross-team submit drawer hits this for the source project's destination dropdown. |

### VerifyResponse routing

The structured response means the SPA can render the right next-step
toast without a second round trip:

| Scenario | `voted_as` | `security_approval_required` | `security_vote_present` | `next_required[]` |
|---|---|---|---|---|
| Source vote, no security required | `source` | `false` | `false` | `[]` — transitions to `approved` |
| Source vote, security required, not yet voted | `source` | `true` | `false` | `["security_approval"]` — SPA toast "your source vote was recorded; security approval still pending" |
| Security vote, source already voted | `security` | `true` | `true` | `[]` — transitions to `approved` |

The SPA's `crossTeamErrorMessage(code)` maps the stable 403 codes to
friendly strings; see the table at the bottom of
[Cross-team requests](../operations/cross-team-requests.md#error-code-reference).

## Reveal sessions

Slice M — bulk reveal page surface. Open returns wrap_id + key_name
handles; the SPA loops over them calling the single-shot
`/requests/:id/wraps/:wrap_id` retrieve for each plaintext. See
[Reveal sessions](../operations/reveal-sessions.md) for the operator
guide.

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `/api/v1/reveal-sessions` | bearer + step-up MFA | `{access_request_id}` → `{session_id, expires_at, ttl_seconds, wraps[]}`. 20/60s per identity rate limit. |
| `GET` | `/api/v1/reveal-sessions/me/active` | bearer | Caller's active sessions; value-free summaries (no envelopes) |
| `POST` | `/api/v1/reveal-sessions/:id/expire` | bearer | `{reason: 'user_hide' \| 'unmount'}` → 204; owner-bound; idempotent server-side |

## Workflows / Policies / Roles / Assignments / Tenancy (admin)

| Method | Path | Auth |
|---|---|---|
| `POST` | `/api/v1/roles` | `bearer + role.edit` |
| `GET` | `/api/v1/roles` | bearer |
| `GET` | `/api/v1/roles/:id` | bearer |
| `PUT` | `/api/v1/roles/:id/permissions` | `bearer + role.edit` |
| `DELETE` | `/api/v1/roles/:id` | `bearer + role.edit` |
| `POST` | `/api/v1/user-roles` | `bearer + user_role.edit` |
| `GET` | `/api/v1/user-roles` | bearer |
| `DELETE` | `/api/v1/user-roles/:id` | `bearer + user_role.edit` |
| `GET` | `/api/v1/users/:userID/roles` | bearer |
| `POST` | `/api/v1/workflows` | `bearer + workflow.edit` |
| `GET` | `/api/v1/workflows` | bearer |
| `GET` | `/api/v1/workflows/:id` | bearer |
| `PUT` | `/api/v1/workflows/:id` | `bearer + workflow.edit` |
| `DELETE` | `/api/v1/workflows/:id` | `bearer + workflow.edit` |
| `POST` | `/api/v1/policies` | `bearer + policy.edit` |
| `GET` | `/api/v1/policies` | bearer |
| `GET` | `/api/v1/policies/:id` | bearer |
| `PUT` | `/api/v1/policies/:id` | `bearer + policy.edit` |
| `DELETE` | `/api/v1/policies/:id` | `bearer + policy.edit` |
| `POST` | `/api/v1/projects` | bearer |
| `GET` | `/api/v1/projects` | bearer |
| `GET` | `/api/v1/projects/:id` | bearer |
| `PUT` | `/api/v1/projects/:id/status` | bearer |
| `GET` | `/api/v1/projects/:id/environments` | bearer |
| `POST` | `/api/v1/environments` | bearer |
| `GET` | `/api/v1/environments` | bearer |
| `DELETE` | `/api/v1/environments/:id` | bearer |

## Secrets (discovered)

| Method | Path | Auth | Notes |
|---|---|---|---|
| `GET` | `/api/v1/secrets` | bearer | Filter: `cluster_name`, `provider`, `ref_prefix`, `status`, repeated `?label=k:v` |
| `GET` | `/api/v1/secrets/:id` | bearer | Single row |

## Audit

| Method | Path | Auth | Notes |
|---|---|---|---|
| `GET` | `/api/v1/audit-events` | `bearer + audit.read` | Filter: `actor`, `action`, `resource`, `correlation_id`, `since`, `until`, `limit` |

## Jobs (admin)

| Method | Path | Auth |
|---|---|---|
| `POST` | `/api/v1/jobs` | bearer |

## Integrations (BRD §26 — gated by `SB_GITOPS_ENABLED`)

| Method | Path | Auth |
|---|---|---|
| `POST` | `/api/v1/argocd-endpoints` | `bearer + integration.edit` |
| `GET` | `/api/v1/argocd-endpoints` | bearer |
| `GET` | `/api/v1/argocd-endpoints/:id/discovered-apps` | bearer |
| `PUT` | `/api/v1/argocd-endpoints/:id/enabled` | `bearer + integration.edit` |
| `DELETE` | `/api/v1/argocd-endpoints/:id` | `bearer + integration.edit` |
| `POST` | `/api/v1/gitops-app-mappings` | `bearer + integration.edit` |
| `GET` | `/api/v1/gitops-app-mappings` | bearer |
| `DELETE` | `/api/v1/gitops-app-mappings/:id` | `bearer + integration.edit` |

## Provider connections

EPIC P (api#92) admin surface + developer dropdown. The same
`GET /provider-connections` URL branches on whether `project_id` is
present — see [Provider connections — Permissions](../operations/provider-connections.md#permissions)
for the full branching matrix. All errors land in the EPIC P envelope:
`{"error_code":"…","message":"…", …}`.

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `/api/v1/provider-connections` | `bearer + integration.edit` | Create. Body: `{name, type, cluster_name?, description?, status?, scope, auth_method?, discover_enabled?, discover_interval_seconds?}`. Returns the full row on 201. |
| `GET` | `/api/v1/provider-connections` | branched | No `project_id` → admin list (`integration.edit`, full projection). `project_id` (+ optional `environment_id`) → sanitized dropdown (`{id, name, type}` per row, `secret.request` scoped). `environment_id` without `project_id` → 400 `project_id_required` BEFORE auth. |
| `GET` | `/api/v1/provider-connections/:id` | `bearer + integration.edit` | Single row, full projection. |
| `PUT` | `/api/v1/provider-connections/:id` | `bearer + integration.edit` | Update. `type` is silently rejected if changed (immutable per §5). |
| `DELETE` | `/api/v1/provider-connections/:id` | `bearer + integration.edit` | 204 on success. 409 `connection_in_use` with `{bindings_count, open_requests_count}` if any binding or pending request blocks it. |
| `POST` | `/api/v1/provider-connections/:id/discover-now` | `bearer + integration.edit` | Manual discover. 202 with `{job_id, correlation_id}`. 409 `connection_disabled` / `discovery_already_running` (per-target Redis lock) on contention. 400 `discover_requires_cluster` if `cluster_name` is null. |
| `POST` | `/api/v1/provider-connections/:id/bindings` | `bearer + integration.edit` | Bind to a (project, env). Body: `{project_id, environment_id?}`. `environment_id` absent or null binds project-wide. 409 `binding_exists` on duplicate; 400 `environment_not_in_project` if mismatched. |
| `GET` | `/api/v1/provider-connections/:id/bindings` | `bearer + integration.edit` | List bindings for one connection. |
| `DELETE` | `/api/v1/provider-connection-bindings/:bid` | `bearer + integration.edit` | Unbind. 204 on success. 404 `binding_not_found` otherwise. |

**Error codes** — the full 19-code reference lives in
[Provider connections — Error code reference](../operations/provider-connections.md#error-code-reference).

## Permissions catalog

| Method | Path | Auth | Notes |
|---|---|---|---|
| `GET` | `/api/v1/permissions` | bearer | Canonical catalog of permission strings + descriptions; cached for 5 min |
