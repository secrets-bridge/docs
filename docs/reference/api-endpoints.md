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

## Permissions catalog

| Method | Path | Auth | Notes |
|---|---|---|---|
| `GET` | `/api/v1/permissions` | bearer | Canonical catalog of permission strings + descriptions; cached for 5 min |
