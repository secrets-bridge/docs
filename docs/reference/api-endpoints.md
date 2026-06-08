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
| `GET` | `/api/v1/workflows/scoped-policy-authorable` | `bearer + policy.author` at any scope | R-follow-up #1 (api#112). Returns workflows where `enabled=true AND scoped_policy_authorable=true`. Auth uses the new `auth.RequireAny` middleware — admits any non-empty scope match because `policy.author` is always scoped. Mounted BEFORE the dynamic `:id` route per the route-ordering correction. |
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
expresses the §3 mental model split — scoped binding is
project-ownership work, not platform registry administration. The
`integration.edit` URLs above are unchanged; admins keep using them.

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `/api/v1/projects/:projectID/provider-connection-bindings` | `bearer + integration.bind` scoped to (project, env) | Bind a self-service-bindable connection to a (project, env). Body: `{provider_connection_id, environment_id}`. `environment_id` is REQUIRED — scoped binders never create project-wide bindings. 403 `connection_not_self_service_bindable` if the platform admin hasn't flipped the flag. 403 `prod_binding_not_allowed_for_scope` for prod envs. 409 `binding_exists`/`connection_disabled` per the locked chain. |
| `GET` | `/api/v1/projects/:projectID/provider-connection-bindings[?environment_id=:id]` | `bearer` | Joined project bindings — server-side join adds `environment_name`, `environment_kind`, `connection_name`, `connection_type`. Optional `environment_id` narrows to env-specific + project-wide for that env. Sanitized projection (no scope / auth_method / discovery fields). |
| `DELETE` | `/api/v1/projects/:projectID/provider-connection-bindings/:bindingID` | `bearer + integration.bind` scoped to (project, binding env) | Unbind. 204 on success. **§4 correction pinned**: if `bindingID` exists under a DIFFERENT project, returns 404 `binding_not_found` — never 403 `out_of_scope_binding` (which would leak existence under another project). 403 `prod_binding_not_allowed_for_scope` for prod env bindings (admin path required). |

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
labels. See [Provider connections — Observability](../operations/provider-connections.md#observability-prometheus-counters) for the operator-facing
discussion + the audit-event triage SQL that pairs with these.

**Error codes** — the full reference lives in
[Provider connections — Error code reference](../operations/provider-connections.md#error-code-reference).

## Project-anchored scoped policy rules (EPIC R, api#108)

`policy.author` callers (typically section heads granted the
`policy_author` seed role) use a separate URL family that's gated
on the rule's project. The URL hierarchy expresses the same §3
mental model split EPIC Q established for bindings — scoped policy
authoring is project-ownership work, not platform policy
administration. The `policy.edit` URLs above are unchanged; admins
keep using them.

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `/api/v1/projects/:projectID/policy-rules` | `bearer + policy.author` scoped to projectID | Author a scoped rule. Body: `{name, selector, priority, workflow_id, enabled}`. Selector MUST carry `environment_kind="non_prod"` OR `environment_id`; the api runs the locked 6-gate chain (coverage → priority<9000 → selector.project_id consistency → env constraint → workflow exists → INSERT). 8 stable codes listed below. |
| `GET` | `/api/v1/projects/:projectID/policy-rules` | `bearer` | List scoped rules + inherited platform rules. **§4 correction 1 sanitization**: inherited platform rows carry `selector_keys` ONLY; the `selector` field is OMITTED server-side. Scoped rows carry the full selector. Route-pinned not perm-pinned — admins acting via this URL also get the sanitized view. |
| `GET` | `/api/v1/projects/:projectID/policy-rules/:ruleID` | `bearer` | Single rule with the same sanitization rules as the list. Inherited platform row → sanitized projection. Scoped row whose `project_id` doesn't match URL projectID → 404 `policy_not_found` (§4 mismatch protection). |
| `PUT` | `/api/v1/projects/:projectID/policy-rules/:ruleID` | `bearer + policy.author` scoped to projectID | Update scoped rule. All body fields optional (omitted = preserve). **§3 Q9 lock**: explicit empty `{}` selector REJECTED with `policy_scope_too_broad.reason=selector_empty`. **§4 lock**: URL projectID mismatch returns `policy_not_found`, NEVER `out_of_scope_policy`. |
| `DELETE` | `/api/v1/projects/:projectID/policy-rules/:ruleID` | `bearer + policy.author` scoped to projectID | 204 on success. URL projectID mismatch returns 404 `policy_not_found`. Platform NULL rule returns 403 `platform_policy_not_editable`. |

**Stable error codes** (EPIC R):

| Code | Status | Meaning |
|---|---|---|
| `policy_not_found` | 404 | Rule doesn't exist OR exists under a different project. The §4 mismatch protection — never leak existence under another parent. |
| `platform_policy_not_editable` | 403 | Scoped caller tried to edit a NULL `project_id` row OR an `is_system` row via the scoped URL. |
| `out_of_scope_policy` | 403 | Caller's `policy.author` grant doesn't cover the target project per the team-aware resolver. |
| `policy_selector_mismatch` | 400 | `selector.project_id` was set but doesn't equal URL projectID. |
| `prod_policy_not_allowed_for_scope` | 403 | Scoped caller tried to author a rule that resolves to a prod env. Envelope includes `{"env_kind": "prod"}`. |
| `policy_scope_too_broad` | 400 | Selector doesn't satisfy the non-prod-by-construction invariant. Envelope includes `{"reason": "..."}` — variants: `env_constraint_missing`, `env_kind_invalid`, `selector_empty`, `env_kind_id_inconsistent`. |
| `policy_priority_reserved` | 400 | Priority `>= 9000` requested; reserved for platform. Envelope includes `{"cap": 9000}`. |
| `policy_environment_not_in_project` | 400 | `selector.environment_id` doesn't belong to URL projectID. |
| `workflow_not_authorable_for_scope` | 403 | R-follow-up #1 (api#112). Scoped caller picked a workflow that platform admin hasn't opted into the scoped author surface. Envelope carries `{"workflow_id": "<uuid>"}` — the actor selected the workflow from a dropdown, so logging it isn't a leak. Distinct from `platform_policy_not_editable`: the workflow exists and is reachable by admin; it just hasn't been exposed to scoped authors yet. |

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
[Policy templates — Observability](../operations/policy-templates.md#observability-prometheus-counters)
for the operator-facing discussion + the audit-event triage SQL
that pairs with these.

**Error codes** — the full reference table lives in
[Policy templates — Error code reference](../operations/policy-templates.md#error-code-reference).

## Permissions catalog

| Method | Path | Auth | Notes |
|---|---|---|---|
| `GET` | `/api/v1/permissions` | bearer | Canonical catalog of permission strings + descriptions; cached for 5 min |
