---
description: "The Secrets Bridge control plane API in Go and Fiber v3: package layout, session-cookie identity, permission guards, runtime endpoints and configuration."
---

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
│   ├── auth/               # permission catalog, scope resolvers, auth.Require
│   ├── handlers/           # HTTP layer (one file per aggregate)
│   ├── middleware/         # Auth (session cookie), default-deny gate, RequestID, Logger, Recover
│   ├── observability/      # slog JSON logger
│   └── services/           # business logic (one file per aggregate)
└── pkg/
    ├── storage/            # Postgres repositories + migrations (embed.FS)
    ├── runtime/            # Redis primitives (locks, idempotency, rate limit, pub/sub)
    ├── keymgmt/            # KMS backends (local / vault-transit / aws-kms)
    └── sealing/            # X25519 + HKDF + AES-GCM for wire envelope
```

The `internal/` boundary is closed; the `pkg/` boundary is
deliberately open because `worker` imports `pkg/storage` and
`pkg/runtime`.

The api has no Argo CD client. `internal/archguard` fails the build if
non-test code imports a package path containing `argocd`, `argoproj` or
`argo-cd`, or contains `/api/v1/applications` or
`/api/v1/stream/applications`. A router test fails if any route path
contains `gitops`, `argocd` or `argo-cd`, except the read-only history route
`GET /api/v1/requests/:id/gitops`. Argo CD state reaches the api only as
[Gateway](gateway.md) evidence.

## How a request gets its identity

`middleware.AuthWith` resolves the caller once per request, in this order:

1. **Session cookie** (`sb_session`, HttpOnly), issued by `/auth/login`
   and the sign-in callbacks. It is the only user credential: logout,
   session revocation and disabling the user end it.
2. Otherwise the caller is anonymous, and the default-deny gate on
   `/api/v1` answers `401` for every route that isn't explicitly public.
   Per-route `auth.Require(perm)` checks then run on top for authenticated
   callers.

`Authorization: Bearer` is not read for users. Login returns no token, so
scripts keep the session cookie in a cookie jar (`curl -c jar` to sign in,
`-b jar` after).

Agent routes under `/api/v1/agents/:id/` authenticate separately, with the
agent's `X-Agent-Secret`. `POST /api/v1/agents/enroll` authenticates with the
one-time enrollment token in the body.

The legacy `X-User-Id` header is **ignored** unless the api runs with
`SB_ALLOW_INSECURE_HEADER_AUTH=true`, a dev-only switch that lets anyone
claim any identity. It is checked only after the session cookie,
and it must never be set on a deployment anyone else can reach. See
[Insecure switches](../operations/config.md#insecure-switches-dev-only).

## Runtime endpoints

| Path | Purpose |
|---|---|
| `GET /healthz` | Always 200. Liveness. |
| `GET /readyz` | Aggregated readiness across `postgres` + `redis` checks (+ KMS at boot). 503 with per-check failure map on failure. |
| `GET /metrics` | Prometheus exposition. |
| `POST /api/v1/auth/login` | Email + password. Sets the `sb_session` cookie and returns `{expires_at, user}`. |

See [HTTP API endpoints](../reference/api-endpoints.md) for the
full surface.

## Configuration

| Env var | Required | Default | Notes |
|---|---|---|---|
| `API_ADDR` | no | `:8080` | Listen address |
| `DATABASE_URL` | yes | - | `postgres://...` |
| `REDIS_URL` | yes | - | `redis://...` |
| `SB_WRAP_MASTER_KEY` | yes when `SB_KMS_BACKEND=local` | - | base64 32 bytes |
| `SB_KMS_BACKEND` | no | `local` | `local` / `vault-transit` / `aws-kms` |
| `SB_KMS_VAULT_ADDR` / `SB_KMS_VAULT_TOKEN` / `SB_KMS_VAULT_KEY` | yes for `vault-transit` | - | |
| `SB_KMS_AWS_REGION` / `SB_KMS_AWS_KEY_ID` | yes for `aws-kms` | - | Alias OK; ARN stored in audit |
| `SB_BOOTSTRAP_ADMIN_EMAIL` / `SB_BOOTSTRAP_ADMIN_PASSWORD` | recommended on first boot | - | Seeds local-admin user; idempotent |

See [Configuration reference](../operations/config.md) for the
exhaustive list, including the
[dev-only insecure switches](../operations/config.md#insecure-switches-dev-only)
and the [retired settings](../operations/config.md#retired-settings) such as
`SB_GITOPS_ENABLED`, which are logged by name and switch nothing on.

## What's stable, what isn't

| Area | Status |
|---|---|
| The four request lifecycles (submit / approve / reject / cancel) | Stable |
| Patch + read flows end-to-end against Vault + AWS SM | Stable |
| Single-shot wrap consumption | Stable, race-tested (6 concurrent racers) |
| Session-cookie login + `auth.Require(perm)` gating on write endpoints | Stable |
| OIDC sign-in (PKCE, group-to-role mapping, back-channel logout) | Shipped; see [Authentication](../operations/authentication.md) |
| Per-tenant KMS scoping | **Not shipped**, tracked as Piece 8c |
| Login brute-force defence | Shipped: per-account lockout (5 wrong passwords, 15 minutes) plus per-IP rate limits on the auth routes and a per-agent heartbeat limit; see [Authentication](../operations/authentication.md) |
| Tested key-rotation runbook | **Not shipped**, tracked at [api#31](https://github.com/secrets-bridge/api/issues/31) |
