# Control Plane API (`api`)

Repo: [`secrets-bridge/api`](https://github.com/secrets-bridge/api)
· Stack: Go 1.25 + [Fiber v3](https://docs.gofiber.io) +
[pgx v5](https://github.com/jackc/pgx) +
[go-redis v9](https://github.com/redis/go-redis)
· Container: `golang:1.25-alpine` build → `distroless/static:nonroot`

The decision-making tier. Holds metadata, owns the workflow + RBAC
domain, mediates between users (via the SPA) and agents (via
outbound HTTPS).

## Layout

```
api/
├── cmd/api/                # main, config, server bootstrap
├── internal/
│   ├── auth/               # JWT signer + permission catalog + auth.Require
│   ├── handlers/           # HTTP layer (one file per aggregate)
│   ├── middleware/         # Auth (Bearer→X-User-Id→anon), RequestID, Logger, Recover
│   ├── observability/      # slog JSON logger
│   └── services/           # business logic (one file per aggregate)
└── pkg/
    ├── storage/            # Postgres repositories + migrations (embed.FS)
    ├── runtime/            # Redis primitives (locks, idempotency, rate limit, pub/sub)
    ├── keymgmt/            # KMS backends (local / vault-transit / aws-kms)
    ├── sealing/            # X25519 + HKDF + AES-GCM for wire envelope
    └── argocd/             # read-only ArgoCD client (BRD §26)
```

The `internal/` boundary is closed; the `pkg/` boundary is
deliberately open because `worker` imports `pkg/storage` and
`pkg/keymgmt`.

## Runtime endpoints

| Path | Purpose |
|---|---|
| `GET /healthz` | Always 200. Liveness. |
| `GET /readyz` | Aggregated readiness across `postgres` + `redis` checks (+ KMS at boot). 503 with per-check failure map on failure. |
| `GET /metrics` | Prometheus exposition. |
| `POST /api/v1/auth/login` | Email + password → HS256 JWT. |

See [HTTP API endpoints](../reference/api-endpoints.md) for the
full surface.

## Configuration

| Env var | Required | Default | Notes |
|---|---|---|---|
| `API_ADDR` | no | `:8080` | Listen address |
| `DATABASE_URL` | yes | - | `postgres://...` |
| `REDIS_URL` | yes | - | `redis://...` |
| `SB_JWT_SECRET` | yes | - | 32+ bytes, base64 or raw. Fails boot if missing. |
| `SB_JWT_TOKEN_TTL` | no | `8h` | Login session lifetime |
| `SB_WRAP_MASTER_KEY` | yes when `SB_KMS_BACKEND=local` | - | base64 32 bytes |
| `SB_KMS_BACKEND` | no | `local` | `local` / `vault-transit` / `aws-kms` |
| `SB_KMS_VAULT_ADDR` / `SB_KMS_VAULT_TOKEN` / `SB_KMS_VAULT_KEY` | yes for `vault-transit` | - | |
| `SB_KMS_AWS_REGION` / `SB_KMS_AWS_KEY_ID` | yes for `aws-kms` | - | Alias OK; ARN stored in audit |
| `SB_BOOTSTRAP_ADMIN_EMAIL` / `SB_BOOTSTRAP_ADMIN_PASSWORD` | recommended on first boot | - | Seeds local-admin user; idempotent |
| `SB_GITOPS_ENABLED` | no | `false` | Mounts BRD §26 ArgoCD endpoints when true |

See [Configuration reference](../operations/config.md) for the
exhaustive list.

## What's stable, what isn't

| Area | Status |
|---|---|
| The four request lifecycles (submit / approve / reject / cancel) | Stable |
| Patch + read flows end-to-end against Vault + AWS SM | Stable |
| Single-shot wrap consumption | Stable, race-tested (6 concurrent racers) |
| JWT login + `auth.Require(perm)` gating on write endpoints | Stable since slice 7 |
| OIDC | **Not shipped**, tracked at [api#26](https://github.com/secrets-bridge/api/issues/26) |
| Per-tenant KMS scoping | **Not shipped**, tracked as Piece 8c |
| Rate limiting on auth + heartbeat | **Not shipped**, tracked at [api#30](https://github.com/secrets-bridge/api/issues/30) |
| Tested key-rotation runbook | **Not shipped**, tracked at [api#31](https://github.com/secrets-bridge/api/issues/31) |
