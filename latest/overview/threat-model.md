# Threat model & hard rules

These are the rules the project never breaks. They're enforced
where possible by tests, schema constraints, and CI greps; where
that isn't possible, code review is the gate.

## Hard rules: never violated

### Value-bearing data

| Rule | How it's enforced |
|---|---|
| Secret values **never** appear in Postgres outside the KMS envelope | `TestWrap_PlaintextNotInDB` scans `encrypted_value` for the plaintext canary |
| Secret values **never** appear in Redis | The `pkg/runtime` package doesn't expose a generic `Set(key, value)`: only idempotency tokens, locks, rate-limit windows, pub/sub messages |
| Secret values **never** appear in audit metadata | Service layer audits `byte_length` + SHA-256 `content_hash` only; `TestWrap_AuditTrailHashesContentNotValue` scans the audit `metadata` column for the canary |
| Secret values **never** appear in API responses | Wire shapes in `internal/handlers/*` deliberately omit value fields; the request response carries `target_keys` (names) only |
| Secret values **never** persisted in the browser | The SPA writes nothing to `localStorage` / `sessionStorage` / IndexedDB. The only cookie is the HttpOnly `sb_session` cookie the api sets, which page scripts can't read |

### Provider credentials

| Rule | How it's enforced |
|---|---|
| Provider credentials **never** leave the agent's network boundary | The CP doesn't have any column or field that could hold one; the agent's resolvers refuse credential-shaped keys in the payload (e.g. seven banned `aws*Key*` names) |
| Provider credentials **never** in frontend code | The UI talks **only** to the Control Plane API; there's no provider SDK in the SPA's dependency tree |
| The Control Plane holds **no** Argo CD credentials | The api and worker have no Argo CD client: an `archguard` test in the api, worker and core repos fails the build if non-test code imports a package path containing `argocd`, `argoproj` or `argo-cd`, or builds an Argo CD API path, and it runs against seeded bad files so it can't pass vacuously. A router test fails if any route other than the read-only `GET /requests/:id/gitops` history mentions `gitops` or `argocd`. Migration 0049 dropped the table that held the old KMS-wrapped tokens; its test scans every text, bytea and jsonb column for canary token bytes. The Argo CD token lives only in the Gateway's own boundary |

### Append-only audit

| Rule | How it's enforced |
|---|---|
| `audit_events` rejects UPDATE and DELETE at the schema layer | `BEFORE UPDATE` / `BEFORE DELETE` triggers raise an exception; `TestAuditEvents_TableIsAppendOnly` runs `pool.Exec` against the triggers and asserts both fail |
| The repository interface for audit events has no `Update` / `Delete` methods | A typo in a SQL string can't surface through the interface; review would catch it |

### Network posture

| Rule | How it's enforced |
|---|---|
| The agent accepts no inbound connections for control-plane or user traffic | Its only listener serves `/healthz`, `/readyz` and `/metrics` on `SB_LOCAL_ADDR`. The binary binds `127.0.0.1:8090` by default. The `agent` Helm chart binds `0.0.0.0:8090` because kubelet probes come from the node, creates no Service, and its default NetworkPolicy denies all ingress (`ingress: []`). Where the CNI doesn't enforce NetworkPolicy, that probe port is reachable on the pod IP from inside the cluster network. |
| The agent never imports any DB or Redis driver | The agent's CI greps `go.sum` for `pgx`, `lib/pq`, `redis/go-redis`, `mongo-driver`, etc., and fails the build if any appear |
| `core` stays infra-free | Same `go.sum` audit on the `core` repo; no `database/sql`, no `redis/go-redis` |
| Plain `http://` to the Control Plane is refused by default | Agent's `validateEndpoint` rejects non-https schemes unless `SB_INSECURE_TRANSPORT=true` is set; loud WARN log at startup if the flag is on |

### Gateway (Release 1, in progress)

The [Gateway](../components/gateway.md) is optional. Release 1 is merged and
has not passed QA. These rules hold in the merged binary, chart and control
plane. The
full STRIDE analysis is the
[Gateway threat model](https://github.com/secrets-bridge/gateway/blob/main/docs/design/threat-model.md).

| Rule | How it's enforced |
|---|---|
| The Gateway changes nothing it observes | Argo CD is read through a transport pinned to the configured origin that allows GET to exact paths only: one Application by name, `session/userinfo` and the fixed can-i questions. The application list route is not admitted; it is reserved for discovery, which is not built. Every other method, path and query key is refused before the request leaves the process. The control-plane client refuses any route outside the Gateway endpoints |
| The Gateway refuses a token that can write | At boot and at every recheck (5 minutes by default) the Gateway asks Argo CD's can-i, project-wide and for each static target it has read, about application writes, `exec`, `logs`, ApplicationSet writes and AppProject changes. A `yes` refuses the start or stops the Gateway, and a question that cannot complete fails closed. The control plane dispatches no tasks for a connector that a replica reported `over_privileged` in the last 10 minutes. Limits are listed below |
| A recreated Application is not the same target | The Gateway treats `metadata.uid` as the identity and answers `target_identity_changed` when it changes. Pinning the uid in the values (`applications[].uid`) makes the check hold across restarts on every replica. Evidence and the catalog carry a scoped digest, never the uid. The control plane pins the first digest for each target. A different digest marks the target `identity_changed` and suspends every binding on it: no dispatch, evidence refused, no new binding. Only a platform admin with a global `gateway.bind` grant and a fresh second factor can re-confirm it, and both the change and the re-confirm are audited |
| The Gateway never reads Kubernetes Secrets | Release 1 has no Kubernetes access: the chart renders no Role and mounts no service-account token. The Release 2 Kubernetes connectors refuse to start if the service account can use any verb on `secrets` or a write verb on what they read, with no override |
| The control plane cannot redirect the Gateway | A task names a connector id and a target id only. Hosts, AppProjects and Applications come from the Gateway's local configuration |
| Gateway and agent credentials are separate | Own tables, `X-Gateway-Secret` header and `GatewayAuth` middleware. The secret is stored as a SHA-256 hash and compared in constant time |
| Argo CD health is never proof of propagation | The Argo CD connector reports at most `observed` with confidence `low` and attaches the caveat `argocd_health_not_proof`. The control plane recomputes every stage outcome from the reported facts, following [ADR 0001](https://github.com/secrets-bridge/gateway/blob/main/docs/adr/0001-gateway-observation-plane.md): a task that saw only Argo CD `Healthy` and `Synced` ends `unverified` with reason `context_only`, never `verified`. There is no `failed` verdict; missing or late evidence ends `pending` and then `timed_out` |

### Authentication & authorization

| Rule | How it's enforced |
|---|---|
| Single-shot wrap consumption is **atomic** | `MarkConsumed` is a single SQL UPDATE with `WHERE consumed_at IS NULL`; `TestRetrieve_ConcurrentAgents_ExactlyOneWins` proves 6 racers → exactly one wins |
| Agent secret comparisons are **constant-time** | `crypto/subtle.ConstantTimeCompare` on every heartbeat path |
| User login is **constant-time-ish** even on unknown email | The auth service runs `bcrypt.CompareHashAndPassword` against a dummy hash when the email isn't found, so an attacker can't enumerate users by latency |
| Generic 401 / 410 / 409 on every failure shape; the audit log carries the specifics | Login failures audit `actor=anonymous`, `error_kind=wrong_password` and `email_length` (never the email body; defends against audit-table spam) |
| Users authenticate with the session cookie **only** | Login returns no token and the api ignores `Authorization: Bearer` for users. The `sb_session` cookie is HttpOnly and `SameSite=Strict` (and `Secure` outside `SB_ENV=dev`), and logout, session revocation or disabling the user ends it server-side |

## Threat model: what we defend against

| Attacker | Attack | Defense |
|---|---|---|
| Passive network listener | Capture plaintext on the wire | TLS minimum; agent refuses `http://` by default |
| Compromised system CA bundle | Forge cert against your CP | Pin a private CA via `SB_CP_CA_FILE` (replaces system roots, doesn't add) |
| TLS-terminating proxy in a service mesh | Read plaintext between TLS termination and the api process | **Wire envelope**: X25519 sealing CP→Agent, KMS-DEK envelope Agent→CP; proxy sees only ciphertext |
| Database exfiltration / stolen backup | Read every secret wrap | **Storage envelope**: per-row KMS-wrapped data key; without the KMS the dump is noise |
| Misbehaving CP process logging payloads before encryption | Plaintext in app logs | Service-layer audits `content_hash` + `byte_length` only; handlers strip value fields from logs |
| Concurrent claim race on a wrap | Two readers see the same value | Atomic `MarkConsumed` with row lock; second caller gets 410 Gone |
| Replay of an already-consumed wrap | Re-fetch a leaked wrap | Schema CHECK enforces single-shot; storage-layer test asserts |
| Timing oracle on login | Enumerate emails by response time | Dummy bcrypt on unknown-email path |
| Forged or stolen user token | Sign a token, or replay one copied from a script or log, to act as a user | There is no user token to forge: the api reads no bearer token for users. A session is a server-side row behind the HttpOnly cookie, so revoking it or disabling the user stops it on the next request |
| Stale agent claiming after lease expired | Double-execution of a job | `WHERE claimed_by = $4 AND status = 'claimed'` on the complete UPDATE; owner mismatch returns 409 |
| Brute force / credential stuffing on `/auth/login` | Guess a local user's password | Per-account lockout after 5 consecutive wrong passwords (15 minutes, independent of source IP, kept in Postgres) plus a per-IP limit of 30 attempts per 60s as anti-scan. The per-IP limiter fails open when Redis is unavailable; the lockout does not. See [Authentication](../operations/authentication.md). |
| Operator deploys with `SB_KMS_BACKEND=local` in production | Storage envelope uses a key that lives in the api's own env | The api refuses to boot with `local` unless `SB_ENV=dev`, and `SB_ENV` defaults to `production`. The `secrets-bridge` chart refuses `kms.backend=local` with `env=production` at render time. |
| Weak or shared local-admin credentials | Local password login as the only way in | OIDC sign-in (PKCE, group-claim to role mapping, back-channel logout). Local login stays as break-glass, and every successful local sign-in emits a `BREAK_GLASS_LOGIN` audit event with `severity=CRITICAL`. |
| Long-lived agent credentials passing through people | Copy an `agent_secret` from a browser, a chat message or a ticket | Direct mint (`POST /api/v1/agents`), which returns the long-lived secret to the admin, answers `403` unless the dev-only `SB_ALLOW_DIRECT_AGENT_MINT=true` is set. Agents enroll with one-time, hash-only, short-TTL tokens bound to one provider connection; the long-lived credential goes straight to the agent and is never shown to a person. |

## Threat model: what we don't yet defend against (open P0 work)

| Attacker | Attack | Mitigation status |
|---|---|---|
| Compromised host running the agent | Steal the agent credential (the identity file or `SB_AGENT_SECRET`) | **Open**: the credential is a long-lived bearer secret. Workload identity (SPIFFE / IRSA) and rotation are [agent#12](https://github.com/secrets-bridge/agent/issues/12) + [api#28](https://github.com/secrets-bridge/api/issues/28) |
| KMS master key rotation breaks the platform | Operator can't rotate without downtime | **Open**: tested runbook is [api#31](https://github.com/secrets-bridge/api/issues/31) |
| Customer admin who controls a Gateway | Report false Argo CD state for their own requests | **Accepted for Release 1**: evidence is customer-side attestation, and the design labels it with the Gateway that observed it. Signed evidence is [gateway#7](https://github.com/secrets-bridge/gateway/issues/7) and must ship before Gateway evidence is presented as compliance evidence |
| Integrator who grants the Gateway's Argo CD account a resource action | Restart or change workloads through `action/...` with the Gateway's token | **Residual, integrator review**: can-i cannot see a grant on `action/*` or `action/<group>/<kind>/<name>`, only a wildcard `*` action. The [minimal policy](../operations/gateway.md#the-minimal-policy) is one `applications, get` line per allowed AppProject, and any other line is the integrator's review |
| Integrator who grants the Gateway's Argo CD account `applications, get` on another AppProject | Read Application state outside the allowlist with the Gateway's token | **Residual, integrator review**: the local allowlist bounds what the Gateway itself reads. The read probe (`applications get` on `*/*`) reports the connector `degraded` only for a `*/*` or `*` grant, so a grant on one other AppProject, such as `tenant-b/*`, is not visible. The policy review must check it |
| Argo CD 2.4 to 2.14 with logs RBAC off | Read pod logs through `applications, get` | **Residual, integrator setting**: on 2.4 to 2.14 logs follow `applications, get` unless `server.rbac.log.enforce.enable: "true"` is set in `argocd-cm`, and the `logs get` probe answers `no` for the minimal policy while the logs stay readable. The setting is required for a Gateway on those versions. Argo CD 3.0 and later always enforce logs RBAC. Before 2.4, `applications, get` always grants logs and cannot be restricted, so those versions are not supported |
| DBA with direct Postgres access | Drop the audit triggers | **Acknowledged**: the schema is a defense; database-level RBAC and audit-log shipping to a separate system are deployment-side responsibilities |

Remaining findings from the 2026-09 security assessment are tracked in
[api#192](https://github.com/secrets-bridge/api/issues/192).

## What we don't do: by design

- **We don't store secret values long-term.** Wraps have a TTL
  measured in minutes / hours. The platform is not a secrets
  *store*; it's a governance + access plane on top of one.
- **We don't broker provider credentials.** The agent reads its own
  Vault token / IRSA role from its own environment. The CP never
  sees them.
- **We don't terminate TLS for the user.** The Helm chart wires
  ingress; the api itself is a plain HTTP server behind that
  terminator. TLS is mandatory in production but enforced at the
  network boundary, not inside the api process.
- **We don't sync K8s secrets from the CP.** The `controller`
  reconciles a CRD via GitOps semantics; the CP itself has no
  inbound connectivity into any workload cluster.
