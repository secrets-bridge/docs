# HTTP API endpoints

Every route the api exposes today. Auth column shows what's
required to call it.

| Auth | Meaning |
|---|---|
| `public` | No auth, open route (probes, login) |
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

Onboarding is **self-enrollment by default**: an admin mints a one-time,
provider-connection-bound enrollment token; the agent exchanges it for its
persistent credential. The legacy direct mint is disabled unless explicitly
enabled as a break-glass admin action.

### Onboarding & admin management (session auth + permission)

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `/api/v1/provider-connections/:id/agent-enrollment-token` | `bearer + agent.mint` | Mint a one-time, connection-bound enrollment token (returned ONCE) |
| `POST` | `/api/v1/agents/enroll` | enrollment token | Exchange the token for a persistent `agent_token` (returned ONCE); creates a connection-bound agent |
| `POST` | `/api/v1/agents` | `bearer + agent.mint` | **Legacy direct mint, disabled by default** → `403 direct_agent_mint_disabled`. Break-glass only via `SB_ALLOW_DIRECT_AGENT_MINT=true` |
| `GET` | `/api/v1/agents` | `bearer + agent.list` | Thin list. New integrations should prefer the admin/provider projections below |
| `GET` | `/api/v1/admin/agents` | `bearer + agent.list` | Rich admin list + filters (`provider_connection_id`, `status`, `cluster_name`, `provider_type`); shows `provider_connection_id` |
| `GET` | `/api/v1/admin/agents/:id` | `bearer + agent.list` | Rich admin get |
| `GET` | `/api/v1/provider-connections/:id/agents` | `bearer + agent.list` | Agents for a provider connection (UI Agents tab) |
| `POST` | `/api/v1/admin/agents/:id/revoke` | `bearer + agent.revoke` | Revoke with `reason` → `revoked_at`/`revoked_by`; emits `agent.revoked` audit (`agent_id`, `provider_connection_id`, `reason`) |
| `POST` | `/api/v1/agent-enrollment-tokens/:id/revoke` | `bearer + agent.mint` | Revoke an UNUSED enrollment token |

### Agent data plane (`X-Agent-Secret`)

| Method | Path | Auth | Notes |
|---|---|---|---|
| `PUT` | `/api/v1/agents/:id/public-key` | agent | Self-register X25519 wire-envelope pubkey |
| `POST` | `/api/v1/agents/:id/heartbeat` | agent | Bodyless → **204** (unchanged). With an optional body (`status`/`agent_version`/`capabilities`) → **200** `{status, server_time, next_heartbeat_seconds}`. Bumps `last_seen_at`; first heartbeat flips `enrolled`→`active` |
| `POST` | `/api/v1/agents/:id/jobs/claim` | agent | 200 with job or 204 (queue empty) |
| `POST` | `/api/v1/agents/:id/jobs/:job_id/complete` | agent | `{status, error?}`; 204 |
| `POST` | `/api/v1/agents/:id/dek` | agent | Issue a KMS-wrapped DEK for wire-envelope encryption |
| `POST` | `/api/v1/agents/:id/wraps` | agent | Read flow: agent posts a fetched value |
| `GET` | `/api/v1/agents/:id/wraps/:wrap_id` | agent | Patch flow: agent retrieves a value (single-shot) |
| `POST` | `/api/v1/agents/:id/secrets/bulk` | agent | Discovery: bulk-upsert discovered secrets |

!!! note "Release notes: agent management"
    - **Heartbeat response shape.** A heartbeat *with a body* now returns **200** `{status, server_time, next_heartbeat_seconds}`. A **bodyless** heartbeat keeps the original empty **204**. Existing agents are unaffected.
    - **Revoke audit action.** New revocations emit `agent.revoked` (metadata: `agent_id`, `provider_connection_id`, `reason`). Legacy audit rows may still carry the older `agent.revoke` action, so dashboards should alias both.
    - **Prefer the admin/provider projections.** `GET /api/v1/agents` remains a thin list. New integrations should use `GET /api/v1/admin/agents`, `GET /api/v1/admin/agents/:id`, or `GET /api/v1/provider-connections/:id/agents` (richer projection incl. `provider_connection_id`).

## Requests (access requests)

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `/api/v1/requests` | bearer | Submit a patch request |
| `POST` | `/api/v1/requests/read` | bearer | Submit a read request |
| `GET` | `/api/v1/requests` | bearer | List with `?requester_id` + `?status` filters |
| `GET` | `/api/v1/requests/:id` | bearer | Get one + inline approvals |
| `POST` | `/api/v1/requests/:id/approve` | bearer | `{approver_id, comment?}` |
| `POST` | `/api/v1/requests/:id/reject` | bearer | `{approver_id, reason}` |
| `POST` | `/api/v1/requests/:id/cancel` | bearer | `{actor_id}` (only the requester) |
| `GET` | `/api/v1/requests/:id/wraps` | user_id | List value-free wrap summaries |
| `GET` | `/api/v1/requests/:id/wraps/:wrap_id` | user_id | Single-shot retrieve (consumes) |
| `GET` | `/api/v1/requests/:id/gitops` | user_id | BRD §26 observation list (404 when feature is off) |

## Cross-team requests

Slice N: Team A → Team B value handoff. See
[Cross-team requests](../operations/cross-team-requests.md) for the
operator model, state machine, and SoD matrix.

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `/api/v1/requests/cross-team` | `bearer + secret.request` | `{target_team_id, target_project_id, target_environment_id, destination_provider_connection_id, destination_secret_ref, destination_keys[], justification}` → `AccessRequest`. Refuses `min_approvers ≥ 2` with `cross_team_min_approvers_unsupported`. NO values in body. destination_keys is the NAME list. |
| `POST` | `/api/v1/requests/:id/fill` | `bearer + secret.value.provide` | `{key_values: {<key>: base64}, fill_comment?}`. Late writers get `fill_window_expired` (410). Same-actor-as-requester returns `separation_of_duties_violated` (403). |
| `POST` | `/api/v1/requests/:id/refuse` | `bearer + secret.value.provide` | `{reason}` (≥ 10 chars). Transitions to `refused`. |
| `POST` | `/api/v1/requests/:id/verify` | `bearer + secret.approve` or `secret.security.approve` | `{decision, voted_as, comment?}` → **200 OK** with structured `VerifyResponse` (NOT 412 on partial votes). Body: `{vote_recorded, voted_as, source_votes, security_approval_required, security_vote_present, next_required[]}`. |
| `GET` | `/api/v1/requests/inbox` | `bearer + secret.value.provide` | `?team_id=` narrows to one team's inbox. Returns `AccessRequest[]` with `pending_values` status. Fail-closed: empty array when caller covers no teams. |
| `GET` | `/api/v1/requests/inbox/count` | `bearer + secret.value.provide` | `{total, per_team: [{team_id, team_name?, count}]}`. Drives the sidebar badge. |
| `GET` | `/api/v1/provider-connections?project_id=:id` | bearer | Returns the connections bound to that project; the SPA's cross-team submit drawer hits this for the source project's destination dropdown. |

### VerifyResponse routing

The structured response means the SPA can render the right next-step
toast without a second round trip:

| Scenario | `voted_as` | `security_approval_required` | `security_vote_present` | `next_required[]` |
|---|---|---|---|---|
| Source vote, no security required | `source` | `false` | `false` | `[]` (transitions to `approved`) |
| Source vote, security required, not yet voted | `source` | `true` | `false` | `["security_approval"]`: SPA toast "your source vote was recorded; security approval still pending" |
| Security vote, source already voted | `security` | `true` | `true` | `[]` (transitions to `approved`) |

The SPA's `crossTeamErrorMessage(code)` maps the stable 403 codes to
friendly strings; see the table at the bottom of
[Cross-team requests](../operations/cross-team-requests.md#error-code-reference).

## Reveal sessions

Slice M: bulk reveal page surface. Open returns wrap_id + key_name
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
| `GET` | `/api/v1/workflows/scoped-policy-authorable` | `bearer + policy.author` at any scope | R-follow-up #1 (api#112). Returns workflows where `enabled=true AND scoped_policy_authorable=true`. Auth uses the new `auth.RequireAny` middleware, which admits any non-empty scope match because `policy.author` is always scoped. Mounted BEFORE the dynamic `:id` route per the route-ordering correction. |
| `GET` | `/api/v1/workflows/:id` | bearer |
| `PUT` | `/api/v1/workflows/:id` | `bearer + workflow.edit` | R-follow-up #1 added `scoped_policy_authorable` to the body shape. Field is `*bool` with COALESCE-preserve semantic: omit the field to keep the existing value (the handler does a Get-then-merge); send `true`/`false` to flip. Critical for rolling-deploy safety with older admin clients that don't yet know about the field. |
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

## Integrations (BRD §26, gated by `SB_GITOPS_ENABLED`)

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
present. See [Provider connections: Permissions](../operations/provider-connections.md#permissions)
for the full branching matrix. All errors land in the EPIC P envelope:
`{"error_code":"…","message":"…", …}`.

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `/api/v1/provider-connections` | `bearer + integration.edit` | Create. Body: `{name, type, cluster_name?, description?, status?, scope, auth_method?, discover_enabled?, discover_interval_seconds?}`. Returns the full row on 201. |
| `GET` | `/api/v1/provider-connections` | branched | 4-way branch (EPIC P + EPIC Q): No `project_id` → admin list (`integration.edit`, full projection). `project_id` (+ optional `environment_id`) without `for_binding` → sanitized dropdown (`{id, name, type}` per row, `secret.request` scoped). `project_id` + `environment_id` + `for_binding=true` → binder picker (`integration.bind` scoped; returns active + `self_service_bindable=true` + NOT-already-bound; refuses `env.kind=prod` with 403 `prod_binding_not_allowed_for_scope`). `environment_id` without `project_id` → 400 `project_id_required` BEFORE auth. `for_binding=true` without `project_id` → 400 `project_id_required`. `for_binding=true` with `project_id` but no `environment_id` → 400 `environment_id_required`. |
| `GET` | `/api/v1/provider-connections/:id` | `bearer + integration.edit` | Single row, full projection. |
| `PUT` | `/api/v1/provider-connections/:id` | `bearer + integration.edit` | Update. `type` is silently rejected if changed (immutable per §5). |
| `DELETE` | `/api/v1/provider-connections/:id` | `bearer + integration.edit` | 204 on success. 409 `connection_in_use` with `{bindings_count, open_requests_count}` if any binding or pending request blocks it. |
| `POST` | `/api/v1/provider-connections/:id/discover-now` | `bearer + integration.edit` | Manual discover. 202 with `{job_id, correlation_id}`. 409 `connection_disabled` / `discovery_already_running` (per-target Redis lock) on contention. 400 `discover_requires_cluster` if `cluster_name` is null. |
| `POST` | `/api/v1/provider-connections/:id/bindings` | `bearer + integration.edit` | Bind to a (project, env). Body: `{project_id, environment_id?}`. `environment_id` absent or null binds project-wide. 409 `binding_exists` on duplicate; 400 `environment_not_in_project` if mismatched. |
| `GET` | `/api/v1/provider-connections/:id/bindings` | `bearer + integration.edit` | List bindings for one connection. |
| `DELETE` | `/api/v1/provider-connection-bindings/:bid` | `bearer + integration.edit` | Unbind. 204 on success. 404 `binding_not_found` otherwise. |

### Project-anchored scoped binding (EPIC Q, api#99)

`integration.bind` callers (typically section heads granted the
`provider_connection_binder` seed role) use a separate URL family
that's gated on the binding's project + env. The URL hierarchy
expresses the §3 mental model split: scoped binding is
project-ownership work, not platform registry administration. The
`integration.edit` URLs above are unchanged; admins keep using them.

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `/api/v1/projects/:projectID/provider-connection-bindings` | `bearer + integration.bind` scoped to (project, env) | Bind a self-service-bindable connection to a (project, env). Body: `{provider_connection_id, environment_id}`. `environment_id` is REQUIRED. Scoped binders never create project-wide bindings. 403 `connection_not_self_service_bindable` if the platform admin hasn't flipped the flag. 403 `prod_binding_not_allowed_for_scope` for prod envs. 409 `binding_exists`/`connection_disabled` per the locked chain. |
| `GET` | `/api/v1/projects/:projectID/provider-connection-bindings[?environment_id=:id]` | `bearer` | Joined project bindings. Server-side join adds `environment_name`, `environment_kind`, `connection_name`, `connection_type`. Optional `environment_id` narrows to env-specific + project-wide for that env. Sanitized projection (no scope / auth_method / discovery fields). |
| `DELETE` | `/api/v1/projects/:projectID/provider-connection-bindings/:bindingID` | `bearer + integration.bind` scoped to (project, binding env) | Unbind. 204 on success. **§4 correction pinned**: if `bindingID` exists under a DIFFERENT project, returns 404 `binding_not_found`, never 403 `out_of_scope_binding` (which would leak existence under another project). 403 `prod_binding_not_allowed_for_scope` for prod env bindings (admin path required). |

**New stable error codes** (EPIC Q):

| Code | Status | Meaning |
|---|---|---|
| `connection_not_self_service_bindable` | 403 | Scoped caller tried to bind a connection where `self_service_bindable=false`. |
| `prod_binding_not_allowed_for_scope` | 403 | Scoped caller tried to bind / unbind on `env.kind='prod'`. Envelope includes `{"env_kind": "prod"}`. |
| `out_of_scope_binding` | 403 | Caller's `integration.bind` grant doesn't cover the target (project, env) per the team-aware resolver. |
| `environment_id_required` | 400 | The binder picker branch (`for_binding=true`) or scoped bind body lacks `environment_id`. |

**Prometheus counters** (EPIC Q):

```
provider_connection_bindings_created_total{permission_used, env_kind}
provider_connection_bindings_deleted_total{permission_used, env_kind}
provider_connection_bindings_denied_total{reason}
```

`reason` is a fixed low-cardinality set; the counters NEVER carry
`actor_id`, `project_id`, `connection_id`, or `environment_id` as
labels. See [Provider connections: Observability](../operations/provider-connections.md#observability-prometheus-counters) for the operator-facing
discussion + the audit-event triage SQL that pairs with these.

**Error codes**: the full reference lives in
[Provider connections: Error code reference](../operations/provider-connections.md#error-code-reference).

## Project-anchored scoped policy rules (EPIC R, api#108)

`policy.author` callers (typically section heads granted the
`policy_author` seed role) use a separate URL family that's gated
on the rule's project. The URL hierarchy expresses the same §3
mental model split EPIC Q established for bindings: scoped policy
authoring is project-ownership work, not platform policy
administration. The `policy.edit` URLs above are unchanged; admins
keep using them.

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `/api/v1/projects/:projectID/policy-rules` | `bearer + policy.author` scoped to projectID | Author a scoped rule. Body: `{name, selector, priority, workflow_id, enabled}`. Selector MUST carry `environment_kind="non_prod"` OR `environment_id`; the api runs the locked 6-gate chain (coverage → priority<9000 → selector.project_id consistency → env constraint → workflow exists → INSERT). 8 stable codes listed below. |
| `GET` | `/api/v1/projects/:projectID/policy-rules` | `bearer` | List scoped rules + inherited platform rules. **§4 correction 1 sanitization**: inherited platform rows carry `selector_keys` ONLY; the `selector` field is OMITTED server-side. Scoped rows carry the full selector. Route-pinned not perm-pinned; admins acting via this URL also get the sanitized view. |
| `GET` | `/api/v1/projects/:projectID/policy-rules/:ruleID` | `bearer` | Single rule with the same sanitization rules as the list. Inherited platform row → sanitized projection. Scoped row whose `project_id` doesn't match URL projectID → 404 `policy_not_found` (§4 mismatch protection). |
| `PUT` | `/api/v1/projects/:projectID/policy-rules/:ruleID` | `bearer + policy.author` scoped to projectID | Update scoped rule. All body fields optional (omitted = preserve). **§3 Q9 lock**: explicit empty `{}` selector REJECTED with `policy_scope_too_broad.reason=selector_empty`. **§4 lock**: URL projectID mismatch returns `policy_not_found`, NEVER `out_of_scope_policy`. |
| `DELETE` | `/api/v1/projects/:projectID/policy-rules/:ruleID` | `bearer + policy.author` scoped to projectID | 204 on success. URL projectID mismatch returns 404 `policy_not_found`. Platform NULL rule returns 403 `platform_policy_not_editable`. |

**Stable error codes** (EPIC R):

| Code | Status | Meaning |
|---|---|---|
| `policy_not_found` | 404 | Rule doesn't exist OR exists under a different project. The §4 mismatch protection: never leak existence under another parent. |
| `platform_policy_not_editable` | 403 | Scoped caller tried to edit a NULL `project_id` row OR an `is_system` row via the scoped URL. |
| `out_of_scope_policy` | 403 | Caller's `policy.author` grant doesn't cover the target project per the team-aware resolver. |
| `policy_selector_mismatch` | 400 | `selector.project_id` was set but doesn't equal URL projectID. |
| `prod_policy_not_allowed_for_scope` | 403 | Scoped caller tried to author a rule that resolves to a prod env. Envelope includes `{"env_kind": "prod"}`. |
| `policy_scope_too_broad` | 400 | Selector doesn't satisfy the non-prod-by-construction invariant, OR carries an unknown `provider_type` / `operation`. Envelope includes `{"reason": "..."}`. Base variants: `env_constraint_missing`, `env_kind_invalid`, `selector_empty`, `env_kind_id_inconsistent`, `provider_type_invalid` (api#139), `operation_invalid` (api#141). |
| `policy_priority_reserved` | 400 | Priority at or above the platform-reserved band requested. The cap is admin-configurable per R-follow-up #2 (default `9000`); envelope echoes the live value: `{"cap": <live>}`. |
| `policy_environment_not_in_project` | 400 | `selector.environment_id` doesn't belong to URL projectID. |
| `workflow_not_authorable_for_scope` | 403 | R-follow-up #1 (api#112). Scoped caller picked a workflow that platform admin hasn't opted into the scoped author surface. Envelope carries `{"workflow_id": "<uuid>"}`. The actor selected the workflow from a dropdown, so logging it isn't a leak. Distinct from `platform_policy_not_editable`: the workflow exists and is reachable by admin; it just hasn't been exposed to scoped authors yet. |

**Prometheus counters** (EPIC R):

```
policy_rules_created_total{permission_used, scope}
policy_rules_updated_total{permission_used, scope}
policy_rules_deleted_total{permission_used, scope}
policy_rules_denied_total{reason}
```

`reason` is a fixed low-cardinality 9-element set (`workflow_not_authorable`
added by R-follow-up #1, api#112); the counters NEVER carry
`actor_id`, `project_id`, `policy_rule_id`, or `workflow_id` as
labels. See
[Policy templates: Observability](../operations/policy-templates.md#observability-prometheus-counters)
for the operator-facing discussion + the audit-event triage SQL
that pairs with these.

**Error codes**: the full reference table lives in
[Policy templates: Error code reference](../operations/policy-templates.md#error-code-reference).

## Team-anchored scoped policy rules (R-follow-up #3, api#114)

`policy.author` callers granted scoped to a `team_id` use this URL
family to author rules that cascade down to every descendant project
of the team subtree. The URL hierarchy expresses the §1 D4 mental
model split: team-anchored authoring is its own surface, parallel to
the project-anchored EPIC R family above. Platform admins still use
`/admin/policies` for global rules; the team URL family stays
`policy.author`-only per §4 C3.

URL is the source of truth for the row's anchor: the `team_id` is
never on the wire body (defense against URL/body confusion, same
posture R-follow-up #2 established for URL-key-wins).

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `/api/v1/teams/:teamID/policy-rules` | `bearer + policy.author` scoped to teamID | Author a team-scoped rule. Body: `{name, selector, priority, workflow_id, enabled}`. §1 C1 strict: selector MUST carry `environment_kind="non_prod"` and MUST NOT carry `project_id`, `environment_id`, or `team_id`. The 6-gate chain (coverage → team exists+active → priority < live cap → selector consistency → workflow authorable → INSERT) runs server-side. Live `priority_cap` echoed in the envelope. |
| `GET` | `/api/v1/teams/:teamID/policy-rules` | `bearer + policy.author` scoped to teamID | List team-own rules + inherited ancestor-team rules + inherited platform rules. Inherited rows carry `selector_keys` only (sanitized). Response envelope carries `priority_cap`. |
| `GET` | `/api/v1/teams/:teamID/policy-rules/:ruleID` | `bearer + policy.author` scoped to teamID | Single rule with the same sanitization rules as the list. Mismatched anchor (project rule via team URL OR rule under a different team) returns 404 `policy_not_found` per §4 mismatch protection. |
| `PUT` | `/api/v1/teams/:teamID/policy-rules/:ruleID` | `bearer + policy.author` scoped to teamID | Update team-scoped rule. R-follow-up #2 §3 critical pin preserved: priority revalidates against the LIVE cap on EVERY call (not only when priority is changing). §4 mismatch returns `policy_not_found`. Anchor is immutable post-create. |
| `DELETE` | `/api/v1/teams/:teamID/policy-rules/:ruleID` | `bearer + policy.author` scoped to teamID | 204 on success. URL teamID mismatch returns 404 `policy_not_found`. Platform NULL rule returns 403 `platform_policy_not_editable`. |

**Response envelope shape** (all GET / PUT / POST):

```json
{
  "rule": {
    "id": "...",
    "name": "...",
    "team_id": "...",
    "team_name": "...",
    "workflow_id": "...",
    "workflow_name": "...",
    "is_platform_inherited": false,
    "is_ancestor_inherited": false,
    "selector_keys": ["environment_kind", "secret_ref_prefix"],
    "selector": { "environment_kind": "non_prod", ... },
    "priority": 100,
    "enabled": true,
    "is_system": false,
    "created_at": "...",
    "updated_at": "..."
  },
  "priority_cap": 9000
}
```

For inherited rows (`is_platform_inherited = true` OR
`is_ancestor_inherited = true`), the `selector` field is OMITTED
server-side. Only `selector_keys` is exposed. Defense against
selector leakage across siblings under the same parent team.

**New stable error codes** (R-follow-up #3):

| Code | Status | Meaning | Envelope extras |
|---|---|---|---|
| `team_not_found` | 404 | Team-scoped Create gate 2: the URL teamID doesn't exist or is archived. Race-only path (coverage passed at gate 1). | - |
| `out_of_scope_team_policy` | 403 | Caller's `policy.author` grant doesn't cover the URL teamID per the team-aware resolver. Mirrors `out_of_scope_policy` for the team URL family. | - |

**3 new `policy_scope_too_broad.reason` variants** (R-follow-up #3):

- `team_selector_pins_project`: team rule selector pinned `project_id`
- `team_selector_pins_environment_id`: team rule selector pinned `environment_id`
- `team_selector_pins_team_id`: team rule selector pinned `team_id` (v1 lock)

A later slice (api#139) added an eighth variant, `provider_type_invalid`,
fired when `selector.provider_type` is present but not in the
backend-owned enum (`aws-sm`, `vault`, `gcp-sm`, `azure-kv`,
`kubernetes`). A sibling slice (api#141) added a ninth,
`operation_invalid`, fired when `selector.operation` is present but not
in the backend-owned enum (`read`, `patch`, `reveal`). Both apply on ALL
three authoring paths: project, team, and admin. See the operator
guide's
[Selector enum values are backend-owned](../operations/policy-templates.md#selector-enum-values-are-backend-owned).

The full reason set on `policy_scope_too_broad` is now 9 variants.

**Workflow validation collapse (§4 C4)**: workflow not-found,
workflow disabled, and workflow not-`scoped_policy_authorable` all
return the SAME response: `403 workflow_not_authorable_for_scope`
with envelope `{workflow_id}`. The SPA doesn't have to handle three
separate envelopes; the api collapses them into one for cleaner UX.

### Project envelope extension

`GET /api/v1/projects/:projectID/policy-rules` (the existing EPIC R
surface) now also carries team-inherited rows. The projection adds:

- `is_team_inherited`: `true` when the rule's `team_id` is set
- `team_name`: populated for team-inherited rows via server-side JOIN
- `workflow_name`: populated for ALL rows via server-side JOIN
  (eliminates the SPA's N+1 lookup against `/workflows`)

Inherited team rows are sanitized identically to inherited platform
rows: `selector_keys` only, no `selector`. Read-only on the scoped
URL; manage on the team's own page or via `/admin/policies`.

### `GET /api/v1/users/me/policy-author-team-coverage`

NEW (R-follow-up #3, api#126). Returns the resolved team set from the
api's `EffectiveTeamAccess(actor, policy.author)` helper: every team
the actor's grants cover, subtree-expanded.

Permission: bearer only. Exposes ONLY the caller's own coverage; not
enumerable across other users.

```json
{
  "global": false,
  "team_ids": ["<uuid>", "<uuid>", ...]
}
```

SPA reads this to drive sidebar visibility + `canAuthorTeamPolicy`
without walking the team tree client-side.

### Admin /admin/policies team anchor support (slice 1d, api#127)

`POST /api/v1/policies` and `PUT /api/v1/policies/:id` now accept the
`team_id` anchor in the body. Server-side selector safety per §5 C5
applies even on the admin path: team-anchored rules can't carry
`selector.project_id`, `selector.environment_id`, or
`selector.team_id`, and `selector.environment_kind` must equal
`"non_prod"`. Same `policy_scope_too_broad.reason` envelope.

Counter cardinality `{permission_used="policy.edit", scope="team"}`
fires when admin creates a team-scoped rule from `/admin/policies`.
Admin audit events emit the normalized `policy.create` /
`policy.update` / `policy.delete` action names with `scope` reflecting
the actual anchor + `actor_permission_used: "policy.edit"`.

### Team lineage transactional audit

`PUT /api/v1/teams/:id` (existing) now emits the
`policy.team_lineage_changed` audit event in the SAME transaction as
the `parent_team_id` UPDATE when the parent actually changes. Metadata
carries the new + old parent IDs + `team_policy_rule_count` +
`affected_project_count` (subtree size). When parent doesn't change
(name-only update) → no audit event (idempotent).

If audit append fails, the parent UPDATE rolls back, so transactional
atomicity is preserved.

## Policy rule change history (R-follow-up #5, api#132)

Three read endpoints expose the audit chain for a single policy
rule. The api walks the chain in time order, computes a diff
between consecutive snapshots, normalizes legacy action names, and
returns a rendered timeline. UI consumes this via the per-anchor
Detail pages.

Hard rule: the §6 selector lock from EPIC R is unwavering. The
wire response carries `selector_keys` (set-based, sorted) and
**NEVER** selector VALUES, on every entry of the chain.

| Method | Path | Auth | Notes |
|---|---|---|---|
| `GET` | `/api/v1/projects/:projectID/policy-rules/:ruleID/history` | `bearer + policy.author` covering projectID | Scoped (project). 404 `policy_not_found` on missing rule OR anchor mismatch (silent, gate-order enumeration protection). After delete: 404. |
| `GET` | `/api/v1/teams/:teamID/policy-rules/:ruleID/history` | `bearer + policy.author` covering teamID | Scoped (team). Coverage gate runs as a HANDLER helper (not middleware) so denial emits the same audit + counter signal as the rest of the gate chain (per R-follow-up #3 §3 C3). After delete: 404. |
| `GET` | `/api/v1/policies/:ruleID/history` | `bearer + policy.edit` | Admin. **Existence check via the audit chain, NOT `policyRepo.Get`**. Admin retains forensic visibility after delete if at least one event exists. NO anchor routing; admin sees regardless of anchor. |

**Query params** that all 3 endpoints support:

- `limit=<int>`: default 50; cap 500 (`storage.MaxPolicyHistoryLimit`). Server-side cap defends against operator typos.

**Response envelope shape** (200):

```json
{
  "rule_id":  "<uuid>",
  "scope":    "platform" | "project" | "team",
  "entries":  [<HistoryEntry>, ...],
  "has_more": false,
  "limit":    50
}
```

`scope` reflects the rule's anchor (not the URL family). For the
admin endpoint with a deleted rule, scope is derived from the most
recent event's metadata; falls back to `"platform"` for pre-§4 C2
legacy events with no scope key.

`has_more=true` indicates an older event was capped by `limit`. The
SPA grows `limit` per "Load more" click (50 → 100 → 200 …) per
OQ3-A; cursor pagination is deferred.

**`HistoryEntry` shape**:

```json
{
  "event_id":             "<uuid>",
  "occurred_at":          "<rfc3339>",
  "actor":                "user:<uuid>" | "agent:<uuid>" | "system:<kind>",
  "actor_display":        "<resolved name>",
  "correlation_id":       "<uuid>",
  "action":               "policy.create" | "policy.update" | "policy.delete",
  "actor_permission_used": "policy.author" | "policy.edit",
  "scope":                "platform" | "project" | "team",
  "changes": [
    { "key": "priority",      "before": 100,  "after": 200 },
    { "key": "name",          "before": "old", "after": "new" },
    { "key": "enabled",       "before": true,  "after": false },
    { "key": "workflow_id",   "before": "<uuid>", "after": "<uuid>",
      "before_workflow_name": "approval-v1", "after_workflow_name": "approval-v2" },
    { "key": "selector_keys", "before": ["environment_kind"], "after": ["environment_kind", "secret_ref_prefix"] }
  ],
  "snapshot_after": {
    "name":          "...",
    "enabled":       true,
    "priority":      100,
    "workflow_id":   "<uuid>",
    "workflow_name": "approval-v1",
    "selector_keys": ["..."]
  }
}
```

- `action` is always the **normalized** name. Legacy events from
  before R-follow-up #3 §4 C2 (action names `policy.created_for_scope`
  etc.) are mapped server-side before return. The SPA sees one
  stable enum.
- `changes` is empty on `policy.create` (chain head) and on
  `policy.delete` (terminal event; `snapshot_after` carries the
  last-known snapshot from the prior event per §3 D3 step 5).
- For legacy events lacking the `name`/`enabled` snapshot fields
  (pre-slice-1b), `snapshot_after.name` / `.enabled` are omitted
  on the wire; SPA renders `(unknown)` placeholders.
- `workflow_name` is resolved server-side via batch lookup
  (`workflows.ListByIDs`). When the workflow has been deleted, the
  field is omitted; SPA renders `(deleted)`.

**Anchor mismatch: silent 404, no audit emit**

Scoped endpoints route through the same enumeration-protection
pattern as the per-anchor `Get` handlers: if the rule's
`project_id` (or `team_id`) doesn't match the URL's, the response
is `404 policy_not_found`, the same envelope as a truly missing rule.
NO `policy.denied_anchor_mismatch` audit event; that would defeat
the very enumeration protection it claims to enhance. Slice 1c §4
OQ4-1 lock.

### Counter

```
policy_rule_history_views_total{scope}
```

LOW-CARDINALITY LOCK preserved: `scope ∈ {platform, project, team}`,
3 values total. NEVER carries `actor_id`, `rule_id`, `project_id`,
or `team_id` labels. Per-rule reads live in the audit log via
`audit.read.policy_history` (see below).

### Audit emit on read

Every successful history list emits one audit event:

```json
{
  "action":   "audit.read.policy_history",
  "actor":    "<actor>",
  "resource": "policy_rule:<rule-uuid>",
  "metadata": {
    "policy_rule_id": "<uuid>",
    "scope":          "platform" | "project" | "team",
    "entry_count":    <int>
  }
}
```

Provides forensic traceability for "who read whose history": a
post-incident query for `action='audit.read.policy_history'`
returns every history view across the entire span. Operators
investigating leaked screenshots / "who saw the old version"
scenarios reach for this surface.

### Snapshot extension on the existing emit sites

Slice 1b extended the metadata on `policy.create / .update / .delete`
across all 3 emit sites (admin, project-scoped, team-scoped). New
events carry:

- `name` (the rule's current name)
- `enabled` (the rule's current enabled state)
- Project-scoped path also now carries `scope: "project"` and
  `team_id: null` for cross-cohort consistency (was missing from the
  R-follow-up #3 §4 C2 normalization; slice 1b closes the gap).

No data backfill; append-only audit. Legacy events render gracefully
in the SPA as `(unknown)` for the missing keys.

## Platform settings (R-follow-up #2, api#113)

Admin surface for cross-cutting platform configuration. v1 ships
exactly one whitelisted key (`platform_reserved_priority`) that
controls the priority band scoped policy authors are bounded below.
Future admin-configurable knobs slot in as new rows in the same table
without per-knob migrations.

**Hard rule**: `platform_settings` must NEVER store secrets,
credentials, tokens, or provider auth material. The service-layer
whitelist + reviewers + the DB CHECK constraint all enforce this.

All three routes are gated by `policy.edit` (the platform policy
admin permission). The SettingsService keeps an in-memory cache with
Redis pub/sub-driven invalidation (channel
`secrets-bridge:platform_settings:<key>`); subscribers re-fetch from
Postgres on every notification rather than trusting the payload, with
a 5-minute TTL backstop for missed messages.

| Method | Path | Auth | Notes |
|---|---|---|---|
| `GET` | `/api/v1/platform-settings` | `bearer + policy.edit` | List all whitelisted rows. Non-whitelisted rows in the table (shouldn't exist in v1) are filtered out service-side. |
| `GET` | `/api/v1/platform-settings/:key` | `bearer + policy.edit` | One row. Unknown / non-whitelisted key → 404 `unknown_platform_setting`. |
| `PUT` | `/api/v1/platform-settings/:key` | `bearer + policy.edit` | Update. Body: `{value: <json>}`. URL `:key` wins over any `key` in the body (defense against URL/body confusion). Transactional: BEGIN → SELECT FOR UPDATE → validate → UPDATE → INSERT audit → COMMIT → pub/sub publish AFTER commit. |

**Response shape** (`PlatformSetting`):

```json
{
  "key": "platform_reserved_priority",
  "value": 9000,
  "updated_at": "2026-06-08T12:34:56.789Z",
  "updated_by": "alice"
}
```

`value` is generic JSON. Callers narrow per-key. For
`platform_reserved_priority` it's an integer between `100` and
`1,000,000`.

**Stable error codes** (R-follow-up #2):

| Code | Status | Meaning | Envelope extras |
|---|---|---|---|
| `unknown_platform_setting` | 404 | Key is not in the v1 whitelist OR the row doesn't exist. | - |
| `invalid_platform_setting` | 400 | Value failed the per-key validator (out of bounds, wrong JSON shape, non-integer for integer keys). The DB CHECK is a defense-in-depth backstop; the service layer pre-validates and emits the friendly bounds. | `{"min": 100, "max": 1000000}` for `platform_reserved_priority` |
| `platform_setting_unavailable` | 503 | The SettingsService cache reload failed (Postgres unreachable, KMS cascading failure, etc.). Service gates that depend on the setting fail closed and return this code; admins and Author drawers can't proceed until the cache is readable again. | - |

**Prometheus counters** (R-follow-up #2):

```
platform_setting_updates_total{key, result}
platform_setting_cache_reloads_total{key, trigger}
```

- `key` is the whitelisted key string (low-cardinality, v1 has one).
- `result` ∈ `{ok, invalid, unavailable, conflict}`.
- `trigger` ∈ `{boot, pubsub, on_demand}`.

LOW-CARDINALITY LOCK: counters NEVER carry `actor_id`. The
`platform_setting.updated` audit event carries the actor + old/new
value for forensic lookup.

See
[Adjusting the reserved priority band](../operations/policy-templates.md#adjusting-the-reserved-priority-band)
for the operator playbook (grandfather rule, triage SQL, fail-closed
posture).

## Permissions catalog

| Method | Path | Auth | Notes |
|---|---|---|---|
| `GET` | `/api/v1/permissions` | bearer | Canonical catalog of permission strings + descriptions; cached for 5 min |
