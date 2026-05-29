# Threat model & hard rules

These are the rules the project never breaks. They're enforced
where possible by tests, schema constraints, and CI greps; where
that isn't possible, code review is the gate.

## Hard rules — never violated

### Value-bearing data

| Rule | How it's enforced |
|---|---|
| Secret values **never** appear in Postgres outside the KMS envelope | `TestWrap_PlaintextNotInDB` scans `encrypted_value` for the plaintext canary |
| Secret values **never** appear in Redis | The `pkg/runtime` package doesn't expose a generic `Set(key, value)` — only idempotency tokens, locks, rate-limit windows, pub/sub messages |
| Secret values **never** appear in audit metadata | Service layer audits `byte_length` + SHA-256 `content_hash` only; `TestWrap_AuditTrailHashesContentNotValue` scans the audit `metadata` column for the canary |
| Secret values **never** appear in API responses | Wire shapes in `internal/handlers/*` deliberately omit value fields; the request response carries `target_keys` (names) only |
| Secret values **never** persisted in the browser | `src/auth/AuthContext` keeps tokens in React state; `localStorage` / `sessionStorage` / cookies / IndexedDB are deliberately unused |

### Provider credentials

| Rule | How it's enforced |
|---|---|
| Provider credentials **never** leave the agent's network boundary | The CP doesn't have any column or field that could hold one; the agent's resolvers refuse credential-shaped keys in the payload (e.g. seven banned `aws*Key*` names) |
| Provider credentials **never** in frontend code | The UI talks **only** to the Control Plane API — there's no provider SDK in the SPA's dependency tree |
| ArgoCD tokens (for §26 observation) are KMS-wrapped at rest | Stored in `argocd_endpoints.token_ciphertext` (BYTEA) via the same `KeyManager` used for `secret_wraps`; canary scan returns zero hits |

### Append-only audit

| Rule | How it's enforced |
|---|---|
| `audit_events` rejects UPDATE and DELETE at the schema layer | `BEFORE UPDATE` / `BEFORE DELETE` triggers raise an exception; `TestAuditEvents_TableIsAppendOnly` runs `pool.Exec` against the triggers and asserts both fail |
| The repository interface for audit events has no `Update` / `Delete` methods | A typo in a SQL string can't surface through the interface — review would catch it |

### Network posture

| Rule | How it's enforced |
|---|---|
| The agent has no inbound public listener | `SB_LOCAL_ADDR` defaults to `127.0.0.1:8090` — loopback only |
| The agent never imports any DB or Redis driver | The agent's CI greps `go.sum` for `pgx`, `lib/pq`, `redis/go-redis`, `mongo-driver`, etc., and fails the build if any appear |
| `core` stays infra-free | Same `go.sum` audit on the `core` repo; no `database/sql`, no `redis/go-redis` |
| Plain `http://` to the Control Plane is refused by default | Agent's `validateEndpoint` rejects non-https schemes unless `SB_INSECURE_TRANSPORT=true` is set; loud WARN log at startup if the flag is on |

### Authentication & authorization

| Rule | How it's enforced |
|---|---|
| Single-shot wrap consumption is **atomic** | `MarkConsumed` is a single SQL UPDATE with `WHERE consumed_at IS NULL`; `TestRetrieve_ConcurrentAgents_ExactlyOneWins` proves 6 racers → exactly one wins |
| Agent secret comparisons are **constant-time** | `crypto/subtle.ConstantTimeCompare` on every heartbeat path |
| User login is **constant-time-ish** even on unknown email | The auth service runs `bcrypt.CompareHashAndPassword` against a dummy hash when the email isn't found, so an attacker can't enumerate users by latency |
| Generic 401 / 410 / 409 on every failure shape; the audit log carries the specifics | Login failures audit `actor=anonymous`, `error_kind=wrong_password` and `email_length` (never the email body — defends against audit-table spam) |
| `alg=none` JWT downgrade is **impossible** | The JWT verifier compares the header byte-for-byte against the exact base64 of `{"alg":"HS256","typ":"JWT"}` — no parsing surface |

## Threat model — what we defend against

| Attacker | Attack | Defense |
|---|---|---|
| Passive network listener | Capture plaintext on the wire | TLS minimum; agent refuses `http://` by default |
| Compromised system CA bundle | Forge cert against your CP | Pin a private CA via `SB_CP_CA_FILE` (replaces system roots, doesn't add) |
| TLS-terminating proxy in a service mesh | Read plaintext between TLS termination and the api process | **Wire envelope** — X25519 sealing CP→Agent, KMS-DEK envelope Agent→CP; proxy sees only ciphertext |
| Database exfiltration / stolen backup | Read every secret wrap | **Storage envelope** — per-row KMS-wrapped data key; without the KMS the dump is noise |
| Misbehaving CP process logging payloads before encryption | Plaintext in app logs | Service-layer audits `content_hash` + `byte_length` only; handlers strip value fields from logs |
| Concurrent claim race on a wrap | Two readers see the same value | Atomic `MarkConsumed` with row lock; second caller gets 410 Gone |
| Replay of an already-consumed wrap | Re-fetch a leaked wrap | Schema CHECK enforces single-shot; storage-layer test asserts |
| Timing oracle on login | Enumerate emails by response time | Dummy bcrypt on unknown-email path |
| `alg=none` JWT | Forge a token with no signature | Header compared as exact base64 string; signer never accepts anything but HS256 |
| Stale agent claiming after lease expired | Double-execution of a job | `WHERE claimed_by = $4 AND status = 'claimed'` on the complete UPDATE — owner mismatch returns 409 |

## Threat model — what we don't yet defend against (open P0 work)

| Attacker | Attack | Mitigation status |
|---|---|---|
| Compromised host running the agent | Steal `SB_AGENT_SECRET` | **Open** — workload identity (SPIFFE / IRSA) is [agent#12](https://github.com/secrets-bridge/agent/issues/12) + [api#28](https://github.com/secrets-bridge/api/issues/28) |
| Brute force / credential stuffing on `/auth/login` | Guess admin password | **Open** — rate limiting is [api#30](https://github.com/secrets-bridge/api/issues/30) |
| Operator deploys with `SB_KMS_BACKEND=local` in production | Storage envelope uses a key that lives in the same env var | **Open** — Helm default switch is [charts#2](https://github.com/secrets-bridge/charts/issues/2); api startup WARN is [api#29](https://github.com/secrets-bridge/api/issues/29) |
| KMS master key rotation breaks the platform | Operator can't rotate without downtime | **Open** — tested runbook is [api#31](https://github.com/secrets-bridge/api/issues/31) |
| DBA with direct Postgres access | Drop the audit triggers | **Acknowledged** — the schema is a defense; database-level RBAC and audit-log shipping to a separate system are deployment-side responsibilities |
| External OIDC SSO required by enterprise | Local-admin login is too coarse | **Open** — real OIDC is [api#26](https://github.com/secrets-bridge/api/issues/26) |

## What we don't do — by design

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
