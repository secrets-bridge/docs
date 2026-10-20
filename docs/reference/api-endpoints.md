# HTTP API endpoints

Every route the api exposes today. Auth column shows what's
required to call it.

| Auth | Meaning |
|---|---|
| `public` | No auth, open route (probes, login) |
| `session` | A signed-in session: the `sb_session` cookie from `/auth/login` or a sign-in callback. There are no bearer tokens; scripts keep the cookie in a jar (`curl -c jar`, then `-b jar`) |
| `session + perm` | A session + the named permission via `auth.Require(perm)` |
| `agent` | An agent's `X-Agent-Secret` header (validated by `AgentAuth` middleware) |
| `gateway` | A Gateway's `X-Gateway-Secret` header (validated by `GatewayAuth` middleware) |
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
| `POST` | `/api/v1/auth/login` | public | `{email, password}` → `{expires_at, user}`, and sets the `sb_session` cookie. No token in the body |
| `GET` | `/api/v1/auth/providers` | public | Sign-in buttons for the login page: each enabled console provider, plus the env-var OIDC provider (`type: "oidc"`) when `SB_OIDC_ISSUER` is set. 120 a minute per IP |

## Sign in with Google

Google configured from the console. See
[Sign in with Google](../operations/google-sign-in.md) for the flow. "Fresh
MFA" means the route also runs `RequireFreshMFA` and answers
`401 step_up_required` on a stale session.

### Sign-in round trip

| Method | Path | Auth | Notes |
|---|---|---|---|
| `GET` | `/api/v1/auth/sso/google/start` | public | Redirects to Google. 30 a minute per IP |
| `GET` | `/api/v1/auth/sso/google/callback` | public | Google returns here. On success, sets the session cookie and redirects to `return_to`. **Every refusal redirects to `/login?error=sso`**, whatever the reason; the reason is in the audit log as `auth.sso.callback` `error_kind`. 60 a minute per IP |
| `POST` | `/api/v1/auth/sso/google/connect` | session + fresh MFA | Starts Connect Google for the caller's account. Returns `{redirect_url}`; the callback comes back to `/me#sso_ticket=…` |
| `POST` | `/api/v1/auth/sso/google/finish` | session | `{ticket}`. Redeems a Connect or Test ticket, only on the session that started it (`403 sso_ticket_refused` otherwise). Returns `{purpose, result}` with `result` `linked`, `ok` or `failed` (and `reason` for a failed test). A refused link is `409 link_refused` with a `reason` such as `identity_taken` |
| `GET` | `/api/v1/users/me/identities` | session | Connected accounts: `provider_type`, `email`, `linked_at` |
| `DELETE` | `/api/v1/users/me/identities/google` | session + fresh MFA | Disconnect. `409 identity_required` when the Google sign-in created the account |

### Sign-in providers and settings

Every route needs a **global** `auth.sso.edit`.

| Method | Path | Auth | Notes |
|---|---|---|---|
| `GET` | `/api/v1/sso/providers` | `session + auth.sso.edit` | List. Each provider has `redirect_url` (empty until a public address is set) and `client_secret_set`, never the secret |
| `POST` | `/api/v1/sso/providers` | `session + auth.sso.edit` + fresh MFA | `{type: "google", display_name, client_id, client_secret, allowed_domains, require_approval, default_role_id}`. Created turned off. `require_approval` defaults to `true` |
| `GET` | `/api/v1/sso/providers/:id` | `session + auth.sso.edit` | One provider |
| `PUT` | `/api/v1/sso/providers/:id` | `session + auth.sso.edit` + fresh MFA | Edit everything except the secret and `enabled`. A `client_secret` field gets `400` |
| `PUT` | `/api/v1/sso/providers/:id/secret` | `session + auth.sso.edit` + fresh MFA | `{client_secret}`. Replace the secret |
| `POST` | `/api/v1/sso/providers/:id/enable` | `session + auth.sso.edit` + fresh MFA | `409 provider_not_ready` with `missing` (`public_url`, `client_secret`, `allowed_domains`) |
| `POST` | `/api/v1/sso/providers/:id/disable` | `session + auth.sso.edit` + fresh MFA | |
| `POST` | `/api/v1/sso/providers/:id/test` | `session + auth.sso.edit` + fresh MFA | Starts a Test round trip, also while the provider is off. Returns `{redirect_url}`; the callback comes back to `/admin/sign-in#sso_ticket=…` |
| `DELETE` | `/api/v1/sso/providers/:id` | `session + auth.sso.edit` + fresh MFA | Remove |
| `GET` | `/api/v1/sso/settings` | `session + auth.sso.edit` | `public_url`, `public_url_source` (`env`, `console` or empty) and `pending_cap` |
| `PUT` | `/api/v1/sso/settings` | `session + auth.sso.edit` + fresh MFA | `{public_url, pending_cap}`; either may be left out. `409 public_url_from_env` when `SB_PUBLIC_URL` is set. `pending_cap` is 1 to 10,000 |

Stable error codes on these routes:

| Code | Status | Meaning |
|---|---|---|
| `invalid_input` | 400 | A field failed validation; `field` names it |
| `default_role_privileged` | 400 | The default role holds something other than `secret.list`, `secret.request` or `audit.read` |
| `default_role_needs_approval_off` | 400 | A default role was set with approval on |
| `env_provider_is_google` | 409 | `SB_OIDC_ISSUER` is already Google |
| `provider_exists` | 409 | A Google provider already exists |
| `provider_not_ready` | 409 | Turn on is missing something; see `missing` |
| `public_url_from_env` | 409 | The address is set by `SB_PUBLIC_URL` |

### Accounts waiting for approval

Every route needs a **global** `user_role.edit`.

| Method | Path | Auth | Notes |
|---|---|---|---|
| `GET` | `/api/v1/users/pending` | `session + user_role.edit` | Waiting accounts, oldest first, at most 100, with `total` for the count |
| `POST` | `/api/v1/users/:id/approve` | `session + user_role.edit` | `{role_id, scope}`. Grants the role and clears the waiting flag in one transaction. `scope` uses the `POST /user-roles` rules; a malformed one gets `400`. `409 user_not_pending` for an account that isn't waiting |
| `POST` | `/api/v1/users/:id/decline` | `session + user_role.edit` | Disables a waiting account. `409 user_not_pending` for any other account |

A waiting account may call only `GET /api/v1/users/me` (which includes
`pending_approval: true`), `POST /api/v1/auth/logout` and
`POST /api/v1/auth/oidc/logout`. Everything else answers
`403 account_pending_approval`.

## Agents

Onboarding is **self-enrollment by default**: an admin mints a one-time,
provider-connection-bound enrollment token; the agent exchanges it for its
persistent credential. The legacy direct mint is disabled unless explicitly
enabled as a break-glass admin action.

### Onboarding & admin management (session auth + permission)

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `/api/v1/provider-connections/:id/agent-enrollment-token` | `session + agent.mint` | Mint a one-time, connection-bound enrollment token (returned ONCE) |
| `POST` | `/api/v1/agents/enroll` | enrollment token | Exchange the token for a persistent `agent_token` (returned ONCE); creates a connection-bound agent |
| `POST` | `/api/v1/agents` | `session + agent.mint` | **Legacy direct mint, disabled by default** → `403 direct_agent_mint_disabled`. Break-glass only via `SB_ALLOW_DIRECT_AGENT_MINT=true` |
| `GET` | `/api/v1/agents` | `session + agent.list` | Thin list. New integrations should prefer the admin/provider projections below |
| `GET` | `/api/v1/admin/agents` | `session + agent.list` | Rich admin list + filters (`provider_connection_id`, `status`, `cluster_name`, `provider_type`); shows `provider_connection_id` |
| `GET` | `/api/v1/admin/agents/:id` | `session + agent.list` | Rich admin get |
| `GET` | `/api/v1/provider-connections/:id/agents` | `session + agent.list` | Agents for a provider connection (UI Agents tab) |
| `POST` | `/api/v1/admin/agents/:id/revoke` | `session + agent.revoke` | Revoke with `reason` → `revoked_at`/`revoked_by`; emits `agent.revoked` audit (`agent_id`, `provider_connection_id`, `reason`) |
| `POST` | `/api/v1/agent-enrollment-tokens/:id/revoke` | `session + agent.mint` | Revoke an UNUSED enrollment token |

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

## Gateways

Release 1 of the [Gateway](../components/gateway.md): the registry and the
observation tasks. Install steps are in [Gateway](../operations/gateway.md). The
flow behind the task routes is in
[Observation flow](../components/gateway.md#observation-flow).

### Gateway machine routes

The `/api/v1/gateways/` prefix is exempt from the session gate. Enrollment is
authenticated by the one-time token only; every other route needs
`X-Gateway-Secret` and is rate limited per authenticated Gateway. Errors are
`{"error": "<code>"}` from a closed list and never echo request content.

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `/api/v1/gateways/enroll` | enrollment token | `{enrollment_token, cluster_name?}` → `201 {gateway_id, gateway_secret, heartbeat_interval_seconds, claim_poll_seconds}`. The secret is returned once. Refused over plain `http` outside `SB_ENV=dev` (`403 https_required`). 10 a minute per IP |
| `POST` | `/api/v1/gateways/:id/heartbeat` | gateway | `{replica_id, gateway_version, contract_versions, status, in_flight, catalog_version?, connectors?}` → `{status, server_time, next_heartbeat_seconds, claim_poll_seconds, contract_version, catalog_version}`. `429 replica_limit` past `max_replicas`. A replica that reports `over_privileged` is audited as `gateway.over_privileged` |
| `PUT` | `/api/v1/gateways/:id/catalog` | gateway | Full replace of advertised connectors and targets → `{accepted, targets_stale, catalog_version}`. Never approves or binds anything. A target no longer advertised stays, marked stale |
| `POST` | `/api/v1/gateways/:id/tasks/claim` | gateway | E4. `{replica_id, max_tasks: 1}` → `200` with one task (`task_id`, `attempt_id`, `attempt_count`, `lease_expires_at`, `deadline_at`, `request_id`, `correlation_id`, `skew_margin_seconds`, `gateway_scope`, `connector_refs`, `expected_change`, `rollout_baseline`), or `204` with `Retry-After: 5` when nothing is claimable or no heartbeat has negotiated a contract version yet. Scoped to the authenticated Gateway. `429 inflight_limit` with `Retry-After` when the Gateway is at `max_inflight_tasks` or the replica already holds a task. `409 contract_version_unsupported`. 2400 a minute |
| `POST` | `/api/v1/gateways/:id/tasks/:task_id/lease` | gateway | E5. `{replica_id, attempt_id}` → `{lease_expires_at}`. Extends the lease by 60s, capped at the deadline. 1200 a minute |
| `POST` | `/api/v1/gateways/:id/tasks/:task_id/release` | gateway | E6. `{replica_id, attempt_id, reason}` with `reason` one of `shutdown`, `over_capacity`, `connector_unavailable` → `204`. The task goes back to the queue. Never counts as a failure. 1200 a minute |
| `POST` | `/api/v1/gateways/:id/tasks/:task_id/result` | gateway | E7. A closed-schema evidence result (`schema_version`, `task_id`, `attempt_id`, `gateway_id`, `replica_id`, `gateway_version`, `started_at`, `finished_at`, `attempt_status`, `refusal_reason?`, `stages`, `clock`) → `{status, task_state, verdict, next}`. `status` is `accepted`, or `duplicate` for the same body sent again for the same attempt. `next` is `none` or `rescheduled`. Body limit 64 KiB. 1200 a minute |

A revoked or disabled Gateway gets `401` on every route above. The E4 to E7
rate limits fail closed: without Redis they answer `503`, which the Gateway
treats as transient. The claim, lease and release bodies are limited to 4 KiB.

Task route error codes:

| Status | Code | Meaning |
|---|---|---|
| `400` | `invalid_request` | Malformed body, unknown field, or ids that do not match the path |
| `401` | `unauthorized` | The Gateway is not live (revoked or disabled) |
| `404` | `not_found` | Unknown task, or a task of another Gateway |
| `409` | `attempt_superseded` | The attempt is not the task's current one: its lease ran out and the task was claimed again, it was released, or the Gateway was revoked or disabled while it held the lease |
| `409` | `lease_expired` | The lease ended before the call |
| `409` | `task_closed` | The task is closed (`done`, `dead`, `cancelled`), or its deadline passed and this call closed it as `timed_out` |
| `409` | `result_conflict` | A different body for an attempt whose result was already accepted |
| `409` | `contract_version_unsupported` | None of the Gateway's contract versions is the one tasks are written in |
| `422` | `schema_violation` | The result is outside the closed schema, names a stage the task does not expect, or fails the evidence binding |
| `422` | `evidence_out_of_window` | `started_at`, `finished_at` or `observed_at` is outside the attempt, allowing for clock skew |
| `429` | `inflight_limit` | Claim only: the Gateway or the replica is at its in-flight limit |

### Gateway admin routes (session auth + permission)

Every write also needs a fresh second factor.

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `/api/v1/admin/gateways` | `session + gateway.mint` + fresh MFA | `{name, boundary, environment_id?, max_replicas?, max_inflight_tasks?}` → `201`, status `pending`. `409 gateway_name_taken` |
| `GET` | `/api/v1/admin/gateways` | `session + gateway.list` | `{items: [...]}` with status (`pending`, `active`, `stale`, `disabled`, `revoked`), versions, last heartbeat and replica count. Never credentials |
| `GET` | `/api/v1/admin/gateways/:id` | `session + gateway.list` | `{gateway, replicas, connectors, bindings, enrollment_tokens}`, metadata only |
| `POST` | `/api/v1/admin/gateways/:id/enrollment-token` | `session + gateway.mint` + fresh MFA | `{expires_in_seconds?, expected_cluster_name?}` → `201 {id, gateway_id, enrollment_token, expires_at}`. The token is returned once. Default TTL 900s, clamped to 60 to 86400. `409 gateway_not_pending` once enrolled |
| `POST` | `/api/v1/admin/gateway-enrollment-tokens/:id/revoke` | `session + gateway.mint` + fresh MFA | Revoke an unused token. `204` |
| `POST` | `/api/v1/admin/gateways/:id/revoke` | `session + gateway.revoke` + fresh MFA | `{reason?}` → the Gateway, status `revoked`. `409 gateway_already_revoked` |
| `POST` | `/api/v1/admin/gateways/:id/connectors/:cid/approve` | `session + gateway.bind` + fresh MFA | `:cid` is the connector's `id`. `409 connector_not_advertised` |
| `POST` | `/api/v1/admin/gateway-bindings` | `session + gateway.bind` + fresh MFA | `{gateway_id, environment_id, project_id?, secret_id \| (provider_connection_id + secret_ref), argocd_connector_id, argocd_target_id, observation_timeout_seconds?}` → `201`. Argo CD targets only in Release 1 |
| `GET` | `/api/v1/admin/gateway-bindings` | `session + gateway.bind` | Optional `?gateway_id=` |
| `DELETE` | `/api/v1/admin/gateway-bindings/:id` | `session + gateway.bind` + fresh MFA | `204`. Cancels the binding's open tasks (`binding_removed`) |
| `PUT` | `/api/v1/admin/gateways/:id/enabled` | `session + gateway.revoke` + fresh MFA | `{enabled}` → the Gateway. Disable refuses its calls with `401` and moves its leased tasks back to `queued`. Enable returns it to `active`, or `pending` if it never enrolled. `409 gateway_revoked` |
| `GET` | `/api/v1/admin/gateways/:id/tasks` | `session + gateway.list` | `{items, counts}`. Optional `?state=` (`queued`, `leased`, `done`, `dead`, `cancelled`) and `?limit=` (1 to 500, default 100). Each item has `state`, `verdict`, `verdict_reason`, `attempt_count`, `failure_count`, `not_before`, `deadline_at` and ids, never secret values |
| `GET` | `/api/v1/admin/environments/:id/observation-source` | `session + gateway.bind` | `{environment_id, observation_source}`, either `gateway` or `none`. A stored value that is not one of them reads as `none`. `404 environment_not_found` |
| `PUT` | `/api/v1/admin/environments/:id/observation-source` | `session + gateway.bind` + fresh MFA | `{observation_source}` with `gateway` or `none` → `{environment_id, observation_source, previous_observation_source, tasks_cancelled}`. Leaving `gateway` cancels the environment's open tasks (`source_changed`). `400 source_retired` for `control_plane`, `400 invalid_observation_source` for any other value |

Audit actions, all with ids, enums and counts only: `gateway.create`,
`gateway.enrollment_token.create`, `gateway.enrollment_token.revoke`,
`gateway.enroll`, `gateway.revoke`, `gateway.auth.rejected`,
`gateway.replica_limit`, `gateway.over_privileged`, `gateway.catalog.updated`,
`gateway.connector.missing`, `gateway.connector.approval_reset`,
`gateway.connector.approved`, `gateway.binding.create`,
`gateway.binding.delete`, `gateway.enable`, `gateway.disable` and
`environment.observation_source.update`.

Observation audit actions: `observation.task.created`,
`observation.task.claimed`, `observation.task.released`,
`observation.task.lease_expired`, `observation.evidence.accepted`,
`observation.evidence.rejected` (with a `reason`),
`gateway.evidence.outcome_mismatch`, `observation.task.verdict`,
`observation.task.dead`, `observation.task.timed_out`,
`observation.task.superseded`, `observation.task.cancelled` and
`request.observation_skipped` (with a `reason` such as `no_gateway_binding` or
`source_none`).

## Requests (access requests)

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `/api/v1/requests` | session | Submit a patch request |
| `POST` | `/api/v1/requests/read` | session | Submit a read request |
| `GET` | `/api/v1/requests` | session | List with `?requester_id` + `?status` filters |
| `GET` | `/api/v1/requests/:id` | session | Get one + inline approvals |
| `POST` | `/api/v1/requests/:id/approve` | session | `{approver_id, comment?}` |
| `POST` | `/api/v1/requests/:id/reject` | session | `{approver_id, reason}` |
| `POST` | `/api/v1/requests/:id/cancel` | session | `{actor_id}` (only the requester) |
| `GET` | `/api/v1/requests/:id/wraps` | user_id | List value-free wrap summaries |
| `GET` | `/api/v1/requests/:id/wraps/:wrap_id` | user_id | Single-shot retrieve (consumes) |
| `GET` | `/api/v1/requests/:id/gitops` | session, requester only | Read-only history of the retired control-plane Argo CD poller. Rows are never written or rewritten. Each row has `id`, `application_name`, `application_namespace`, `polling_state` (repeated as `status`), `history: true`, `label: history_context_only`, `history_status` and filtered `observed_state`, plus `polls_count`, `last_polled_at`, `timeout_at`, `terminal_at` and `last_error` as a class. `history_status` is `argocd_healthy_synced_context_only`, `timed_out_unverified`, `failed` or `not_completed_poller_removed` (rows the poller never finished). None of them is proof that a value reached a workload. `403` for anyone but the requester. Live Argo CD state is in `/observations` |
| `GET` | `/api/v1/requests/:id/observations` | session | Gateway evidence for the request, behind the same read check as `GET /requests/:id`: `{observation_source, rollup, label, tasks}`. `rollup` is `none` (no task), `pending`, `verified`, `partially_observed`, `unverified` or `timed_out`. `label` is always `observed_operational_state`. Each task has `gateway_name`, `state`, `verdict`, `verdict_reason`, `deadline_at` and `stages`; each stage has `outcome`, `reported_outcome`, `observed_at`, `connector_id`, `target_id`, `caveats` and `facts`. Argo CD stages always carry `argocd_health_not_proof`. Resource names are not included. A task past its deadline that the worker has not closed yet is shown as `timed_out` with `timed_out_at_read: true`; the read writes nothing |

## Cross-team requests

Slice N: Team A → Team B value handoff. See
[Cross-team requests](../operations/cross-team-requests.md) for the
operator model, state machine, and SoD matrix.

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `/api/v1/requests/cross-team` | `session + secret.request` | `{target_team_id, target_project_id, target_environment_id, destination_provider_connection_id, destination_secret_ref, destination_keys[], justification}` → `AccessRequest`. Refuses `min_approvers ≥ 2` with `cross_team_min_approvers_unsupported`. NO values in body. destination_keys is the NAME list. |
| `POST` | `/api/v1/requests/:id/fill` | `session + secret.value.provide` | `{key_values: {<key>: base64}, fill_comment?}`. Late writers get `fill_window_expired` (410). Same-actor-as-requester returns `separation_of_duties_violated` (403). |
| `POST` | `/api/v1/requests/:id/refuse` | `session + secret.value.provide` | `{reason}` (≥ 10 chars). Transitions to `refused`. |
| `POST` | `/api/v1/requests/:id/verify` | `session + secret.approve` or `secret.security.approve` | `{decision, voted_as, comment?}` → **200 OK** with structured `VerifyResponse` (NOT 412 on partial votes). Body: `{vote_recorded, voted_as, source_votes, security_approval_required, security_vote_present, next_required[]}`. |
| `GET` | `/api/v1/requests/inbox` | `session + secret.value.provide` | `?team_id=` narrows to one team's inbox. Returns `AccessRequest[]` with `pending_values` status. Fail-closed: empty array when caller covers no teams. |
| `GET` | `/api/v1/requests/inbox/count` | `session + secret.value.provide` | `{total, per_team: [{team_id, team_name?, count}]}`. Drives the sidebar badge. |
| `GET` | `/api/v1/provider-connections?project_id=:id` | session | Returns the connections bound to that project; the SPA's cross-team submit drawer hits this for the source project's destination dropdown. |

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
| `POST` | `/api/v1/reveal-sessions` | session + step-up MFA | `{access_request_id}` → `{session_id, expires_at, ttl_seconds, wraps[]}`. 20/60s per identity rate limit. |
| `GET` | `/api/v1/reveal-sessions/me/active` | session | Caller's active sessions; value-free summaries (no envelopes) |
| `POST` | `/api/v1/reveal-sessions/:id/expire` | session | `{reason: 'user_hide' \| 'unmount'}` → 204; owner-bound; idempotent server-side |

## Workflows / Policies / Roles / Assignments / Tenancy (admin)

| Method | Path | Auth |
|---|---|---|
| `POST` | `/api/v1/roles` | `session + role.edit` |
| `GET` | `/api/v1/roles` | session |
| `GET` | `/api/v1/roles/:id` | session |
| `PUT` | `/api/v1/roles/:id/permissions` | `session + role.edit` | `409 role_is_sso_default` when the role is a sign-in provider's default role and the change would add a privileged permission |
| `DELETE` | `/api/v1/roles/:id` | `session + role.edit` |
| `POST` | `/api/v1/user-roles` | `session + user_role.edit` |
| `GET` | `/api/v1/user-roles` | session |
| `DELETE` | `/api/v1/user-roles/:id` | `session + user_role.edit` |
| `GET` | `/api/v1/users/:userID/roles` | session |
| `POST` | `/api/v1/workflows` | `session + workflow.edit` |
| `GET` | `/api/v1/workflows` | session |
| `GET` | `/api/v1/workflows/scoped-policy-authorable` | `session + policy.author` at any scope | R-follow-up #1 (api#112). Returns workflows where `enabled=true AND scoped_policy_authorable=true`. Auth uses the new `auth.RequireAny` middleware, which admits any non-empty scope match because `policy.author` is always scoped. Mounted BEFORE the dynamic `:id` route per the route-ordering correction. |
| `GET` | `/api/v1/workflows/:id` | session |
| `PUT` | `/api/v1/workflows/:id` | `session + workflow.edit` | R-follow-up #1 added `scoped_policy_authorable` to the body shape. Field is `*bool` with COALESCE-preserve semantic: omit the field to keep the existing value (the handler does a Get-then-merge); send `true`/`false` to flip. Critical for rolling-deploy safety with older admin clients that don't yet know about the field. |
| `DELETE` | `/api/v1/workflows/:id` | `session + workflow.edit` |
| `POST` | `/api/v1/policies` | `session + policy.edit` |
| `GET` | `/api/v1/policies` | session |
| `GET` | `/api/v1/policies/:id` | session |
| `PUT` | `/api/v1/policies/:id` | `session + policy.edit` |
| `DELETE` | `/api/v1/policies/:id` | `session + policy.edit` |
| `POST` | `/api/v1/projects` | session |
| `GET` | `/api/v1/projects` | session |
| `GET` | `/api/v1/projects/:id` | session |
| `PUT` | `/api/v1/projects/:id/status` | session |
| `GET` | `/api/v1/projects/:id/environments` | session |
| `POST` | `/api/v1/environments` | session |
| `GET` | `/api/v1/environments` | session |
| `DELETE` | `/api/v1/environments/:id` | session |

## Secrets (discovered)

| Method | Path | Auth | Notes |
|---|---|---|---|
| `GET` | `/api/v1/secrets` | session | Filter: `cluster_name`, `provider`, `ref_prefix`, `status`, repeated `?label=k:v` |
| `GET` | `/api/v1/secrets/:id` | session | Single row |

## Audit

| Method | Path | Auth | Notes |
|---|---|---|---|
| `GET` | `/api/v1/audit-events` | `session + audit.read` | Filter: `actor`, `action`, `resource`, `correlation_id`, `since`, `until`, `limit` |

## Jobs (admin)

| Method | Path | Auth |
|---|---|---|
| `POST` | `/api/v1/jobs` | session |

## Provider connections

EPIC P (api#92) admin surface + developer dropdown. The same
`GET /provider-connections` URL branches on whether `project_id` is
present. See [Provider connections: Permissions](../operations/provider-connections.md#permissions)
for the full branching matrix. All errors land in the EPIC P envelope:
`{"error_code":"…","message":"…", …}`.

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `/api/v1/provider-connections` | `session + integration.edit` | Create. Body: `{name, type, cluster_name?, description?, status?, scope, auth_method?, discover_enabled?, discover_interval_seconds?}`. Returns the full row on 201. |
| `GET` | `/api/v1/provider-connections` | branched | 4-way branch (EPIC P + EPIC Q): No `project_id` → admin list (`integration.edit`, full projection). `project_id` (+ optional `environment_id`) without `for_binding` → sanitized dropdown (`{id, name, type}` per row, `secret.request` scoped). `project_id` + `environment_id` + `for_binding=true` → binder picker (`integration.bind` scoped; returns active + `self_service_bindable=true` + NOT-already-bound; refuses `env.kind=prod` with 403 `prod_binding_not_allowed_for_scope`). `environment_id` without `project_id` → 400 `project_id_required` BEFORE auth. `for_binding=true` without `project_id` → 400 `project_id_required`. `for_binding=true` with `project_id` but no `environment_id` → 400 `environment_id_required`. |
| `GET` | `/api/v1/provider-connections/:id` | `session + integration.edit` | Single row, full projection. |
| `PUT` | `/api/v1/provider-connections/:id` | `session + integration.edit` | Update. `type` is silently rejected if changed (immutable per §5). |
| `DELETE` | `/api/v1/provider-connections/:id` | `session + integration.edit` | 204 on success. 409 `connection_in_use` with `{bindings_count, open_requests_count}` if any binding or pending request blocks it. |
| `POST` | `/api/v1/provider-connections/:id/discover-now` | `session + integration.edit` | Manual discover. 202 with `{job_id, correlation_id}`. 409 `connection_disabled` / `discovery_already_running` (per-target Redis lock) on contention. 400 `discover_requires_cluster` if `cluster_name` is null. |
| `POST` | `/api/v1/provider-connections/:id/bindings` | `session + integration.edit` | Bind to a (project, env). Body: `{project_id, environment_id?}`. `environment_id` absent or null binds project-wide. 409 `binding_exists` on duplicate; 400 `environment_not_in_project` if mismatched. |
| `GET` | `/api/v1/provider-connections/:id/bindings` | `session + integration.edit` | List bindings for one connection. |
| `DELETE` | `/api/v1/provider-connection-bindings/:bid` | `session + integration.edit` | Unbind. 204 on success. 404 `binding_not_found` otherwise. |

### Project-anchored scoped binding (EPIC Q, api#99)

`integration.bind` callers (typically section heads granted the
`provider_connection_binder` seed role) use a separate URL family
that's gated on the binding's project + env. The URL hierarchy
expresses the §3 mental model split: scoped binding is
project-ownership work, not platform registry administration. The
`integration.edit` URLs above are unchanged; admins keep using them.

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `/api/v1/projects/:projectID/provider-connection-bindings` | `session + integration.bind` scoped to (project, env) | Bind a self-service-bindable connection to a (project, env). Body: `{provider_connection_id, environment_id}`. `environment_id` is REQUIRED. Scoped binders never create project-wide bindings. 403 `connection_not_self_service_bindable` if the platform admin hasn't flipped the flag. 403 `prod_binding_not_allowed_for_scope` for prod envs. 409 `binding_exists`/`connection_disabled` per the locked chain. |
| `GET` | `/api/v1/projects/:projectID/provider-connection-bindings[?environment_id=:id]` | `session` | Joined project bindings. Server-side join adds `environment_name`, `environment_kind`, `connection_name`, `connection_type`. Optional `environment_id` narrows to env-specific + project-wide for that env. Sanitized projection (no scope / auth_method / discovery fields). |
| `DELETE` | `/api/v1/projects/:projectID/provider-connection-bindings/:bindingID` | `session + integration.bind` scoped to (project, binding env) | Unbind. 204 on success. **§4 correction pinned**: if `bindingID` exists under a DIFFERENT project, returns 404 `binding_not_found`, never 403 `out_of_scope_binding` (which would leak existence under another project). 403 `prod_binding_not_allowed_for_scope` for prod env bindings (admin path required). |

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
| `POST` | `/api/v1/projects/:projectID/policy-rules` | `session + policy.author` scoped to projectID | Author a scoped rule. Body: `{name, selector, priority, workflow_id, enabled}`. Selector MUST carry `environment_kind="non_prod"` OR `environment_id`; the api runs the locked 6-gate chain (coverage → priority<9000 → selector.project_id consistency → env constraint → workflow exists → INSERT). 8 stable codes listed below. |
| `GET` | `/api/v1/projects/:projectID/policy-rules` | `session` | List scoped rules + inherited platform rules. **§4 correction 1 sanitization**: inherited platform rows carry `selector_keys` ONLY; the `selector` field is OMITTED server-side. Scoped rows carry the full selector. Route-pinned not perm-pinned; admins acting via this URL also get the sanitized view. |
| `GET` | `/api/v1/projects/:projectID/policy-rules/:ruleID` | `session` | Single rule with the same sanitization rules as the list. Inherited platform row → sanitized projection. Scoped row whose `project_id` doesn't match URL projectID → 404 `policy_not_found` (§4 mismatch protection). |
| `PUT` | `/api/v1/projects/:projectID/policy-rules/:ruleID` | `session + policy.author` scoped to projectID | Update scoped rule. All body fields optional (omitted = preserve). **§3 Q9 lock**: explicit empty `{}` selector REJECTED with `policy_scope_too_broad.reason=selector_empty`. **§4 lock**: URL projectID mismatch returns `policy_not_found`, NEVER `out_of_scope_policy`. |
| `DELETE` | `/api/v1/projects/:projectID/policy-rules/:ruleID` | `session + policy.author` scoped to projectID | 204 on success. URL projectID mismatch returns 404 `policy_not_found`. Platform NULL rule returns 403 `platform_policy_not_editable`. |

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
| `POST` | `/api/v1/teams/:teamID/policy-rules` | `session + policy.author` scoped to teamID | Author a team-scoped rule. Body: `{name, selector, priority, workflow_id, enabled}`. §1 C1 strict: selector MUST carry `environment_kind="non_prod"` and MUST NOT carry `project_id`, `environment_id`, or `team_id`. The 6-gate chain (coverage → team exists+active → priority < live cap → selector consistency → workflow authorable → INSERT) runs server-side. Live `priority_cap` echoed in the envelope. |
| `GET` | `/api/v1/teams/:teamID/policy-rules` | `session + policy.author` scoped to teamID | List team-own rules + inherited ancestor-team rules + inherited platform rules. Inherited rows carry `selector_keys` only (sanitized). Response envelope carries `priority_cap`. |
| `GET` | `/api/v1/teams/:teamID/policy-rules/:ruleID` | `session + policy.author` scoped to teamID | Single rule with the same sanitization rules as the list. Mismatched anchor (project rule via team URL OR rule under a different team) returns 404 `policy_not_found` per §4 mismatch protection. |
| `PUT` | `/api/v1/teams/:teamID/policy-rules/:ruleID` | `session + policy.author` scoped to teamID | Update team-scoped rule. R-follow-up #2 §3 critical pin preserved: priority revalidates against the LIVE cap on EVERY call (not only when priority is changing). §4 mismatch returns `policy_not_found`. Anchor is immutable post-create. |
| `DELETE` | `/api/v1/teams/:teamID/policy-rules/:ruleID` | `session + policy.author` scoped to teamID | 204 on success. URL teamID mismatch returns 404 `policy_not_found`. Platform NULL rule returns 403 `platform_policy_not_editable`. |

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

Permission: session only. Exposes ONLY the caller's own coverage; not
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
| `GET` | `/api/v1/projects/:projectID/policy-rules/:ruleID/history` | `session + policy.author` covering projectID | Scoped (project). 404 `policy_not_found` on missing rule OR anchor mismatch (silent, gate-order enumeration protection). After delete: 404. |
| `GET` | `/api/v1/teams/:teamID/policy-rules/:ruleID/history` | `session + policy.author` covering teamID | Scoped (team). Coverage gate runs as a HANDLER helper (not middleware) so denial emits the same audit + counter signal as the rest of the gate chain (per R-follow-up #3 §3 C3). After delete: 404. |
| `GET` | `/api/v1/policies/:ruleID/history` | `session + policy.edit` | Admin. **Existence check via the audit chain, NOT `policyRepo.Get`**. Admin retains forensic visibility after delete if at least one event exists. NO anchor routing; admin sees regardless of anchor. |

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
| `GET` | `/api/v1/platform-settings` | `session + policy.edit` | List all whitelisted rows. Non-whitelisted rows in the table (shouldn't exist in v1) are filtered out service-side. |
| `GET` | `/api/v1/platform-settings/:key` | `session + policy.edit` | One row. Unknown / non-whitelisted key → 404 `unknown_platform_setting`. |
| `PUT` | `/api/v1/platform-settings/:key` | `session + policy.edit` | Update. Body: `{value: <json>}`. URL `:key` wins over any `key` in the body (defense against URL/body confusion). Transactional: BEGIN → SELECT FOR UPDATE → validate → UPDATE → INSERT audit → COMMIT → pub/sub publish AFTER commit. |

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
| `GET` | `/api/v1/permissions` | session | Canonical catalog of permission strings + descriptions; cached for 5 min |
