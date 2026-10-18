# Configuration reference

Every environment variable across `api` / `agent` / `worker` /
`controller`. Defaults shown match the source tree as of v0.X.

## api

| Env var | Required | Default | Notes |
|---|---|---|---|
| `API_ADDR` | no | `:8080` | Listen address |
| `API_SHUTDOWN_GRACE` | no | `15s` | SIGTERM grace period |
| `LOG_LEVEL` | no | `info` | `debug` / `info` / `warn` / `error` |
| `SB_ENV` | no | `production` | `production` or `dev`; anything else fails boot. `dev` allows the `local` KMS backend, seeds three dev users on an empty database and drops the `Secure` cookie flag. Never `dev` outside a laptop. |
| `DATABASE_URL` | **yes** |  | `postgres://user:pass@host:5432/db` |
| `DATABASE_MAX_CONNS` | no | `10` | pgxpool size |
| `DATABASE_CONN_LIFETIME` | no | `1h` | |
| `REDIS_URL` | **yes** |  | `redis://host:6379/0` |
| `REDIS_POOL_SIZE` | no | `10` | |
| `REDIS_DIAL_TIMEOUT` | no | `5s` | |
| `REDIS_NAMESPACE` | no | `secrets-bridge` | Key prefix |
| `SB_JWT_SECRET` | **yes** |  | 32+ bytes, base64 or raw. Fails boot if too short. |
| `SB_JWT_TOKEN_TTL` | no | `8h` | Login session lifetime |
| `SB_WRAP_MASTER_KEY` | yes when `SB_KMS_BACKEND=local` |  | base64 32 bytes (`openssl rand -base64 32`) |
| `SB_KMS_BACKEND` | no | `local` | `local` / `vault-transit` / `aws-kms`. `local` is refused at boot unless `SB_ENV=dev`, so production must set one of the other two. |
| `SB_KMS_VAULT_ADDR` | yes for `vault-transit` |  | |
| `SB_KMS_VAULT_TOKEN` | yes for `vault-transit` |  | |
| `SB_KMS_VAULT_KEY` | yes for `vault-transit` |  | Transit key name |
| `SB_KMS_VAULT_MOUNT` | no | `transit` | |
| `SB_KMS_AWS_REGION` | yes for `aws-kms` |  | |
| `SB_KMS_AWS_KEY_ID` | yes for `aws-kms` |  | Alias / ARN / key id |
| `SB_KMS_AWS_ENDPOINT` | no |  | LocalStack / VPC endpoint override |
| `SB_BOOTSTRAP_ADMIN_EMAIL` | recommended on first boot |  | See [Bootstrap](bootstrap.md) |
| `SB_BOOTSTRAP_ADMIN_PASSWORD` | recommended on first boot |  | |
| `SB_BOOTSTRAP_ADMIN_USER_ID` | optional |  | Opaque user_id for pre-OIDC role assignment |
| `SB_GITOPS_ENABLED` | no | `false` | BRD §26 ArgoCD endpoints + observation fan-out |
| `SB_OBJECTSTORE_BUCKET` | see note |  | Bucket for media (logos). See [Object storage](object-storage.md) |
| `SB_OBJECTSTORE_REGION` | see note |  | Bucket region |
| `SB_OBJECTSTORE_ENDPOINT` | no |  | Endpoint override for S3-compatible servers such as MinIO (`https://s3.example.com`). Unset for AWS S3. |
| `SB_OBJECTSTORE_PREFIX` | no |  | Key prefix inside the bucket |
| `SB_OBJECTSTORE_SSE` | no |  | `AES256` (SSE-S3) or `aws:kms` (SSE-KMS) |
| `SB_OBJECTSTORE_KMS_KEY_ID` | yes for `aws:kms` |  | KMS key id, ARN or alias |
| `SB_OBJECTSTORE_FORCE_PATH_STYLE` | no |  | `true` for path-style addressing (most MinIO setups) |

!!! note "Object storage is in progress"
    The `SB_OBJECTSTORE_*` settings ship with
    [api#253](https://github.com/secrets-bridge/api/issues/253). Whether
    they are required, and their defaults, are not settled yet. Check the
    release notes. Credentials come from the standard AWS SDK chain, as for
    `aws-kms`; there are no object-storage credential variables.

The dev-only switches the api also reads are listed under
[Insecure switches](#insecure-switches-dev-only).

## agent

| Env var | Required | Default | Notes |
|---|---|---|---|
| `SB_CP_ENDPOINT` | **yes** |  | `https://api.example.com` |
| `SB_INSECURE_TRANSPORT` | no | `false` | Dev only: allows `http://` to the control plane. See [Insecure switches](#insecure-switches-dev-only) |
| `SB_CP_CA_FILE` | no |  | Pin a private CA (replaces system roots) |
| `SB_CP_TLS_SERVER_NAME` | no |  | SNI override for private DNS |
| `SB_ENROLLMENT_TOKEN` | first boot |  | One-time token from `POST /api/v1/provider-connections/<id>/agent-enrollment-token`. Exchanged once at `POST /api/v1/agents/enroll`, then never used again. Deliver it through a Secret. |
| `SB_ENROLLMENT_ENABLED` | no | `true` | Enroll on first boot when no identity is stored and a token is set |
| `SB_IDENTITY_FILE` | no | `/etc/secrets-bridge/identity.json` | Where the agent writes `{agent_id, agent_secret}` after enrolling (mode `0600`) and reads it on every restart. Must be writable and survive restarts. |
| `SB_PROVIDER_TYPE` | no | `aws-sm` | Reported at enrollment; must match the provider connection's `type` |
| `SB_AGENT_NAME` | no | hostname | Reported at enrollment |
| `SB_REGION` | no |  | Reported at enrollment |
| `SB_CLUSTER_NAME` | **yes** for discovery |  | Stamped on every discovered secret; must match the token's `expected_cluster_name` when one is set |
| `SB_AGENT_ID` / `SB_AGENT_SECRET` | no |  | A pre-provisioned credential. When set they take precedence over the identity file and enrollment is skipped. Only agents created by the dev-only direct mint need them. |
| `SB_HEARTBEAT_INTERVAL` | no | `30s` | |
| `SB_CLAIM_INTERVAL` | no | `5s` | |
| `SB_CLAIM_CONCURRENCY` | no | `4` | Worker pool size |
| `SB_LOCAL_ADDR` | no | `127.0.0.1:8090` | Listener for `/healthz`, `/readyz`, `/metrics` only. The `agent` Helm chart sets `0.0.0.0:8090` so kubelet probes can reach it; the chart's NetworkPolicy denies all ingress to the pod. |
| `SB_AGENT_PRIVATE_KEY` | no |  | base64 X25519 private key (wire envelope) |
| `SB_AGENT_PRIVATE_KEY_FILE` | no |  | File path alternative |
| `SB_VAULT_ADDR` | yes for Vault |  | |
| `SB_VAULT_TOKEN` | yes for Vault token auth |  | |
| `SB_VAULT_KUBERNETES_ROLE` | yes for Vault k8s auth |  | Alternative to token |
| `SB_VAULT_NAMESPACE` | no |  | Vault Enterprise namespace |
| `SB_AWS_REGION` | yes for AWS SM |  | |
| `SB_AWS_ROLE_ARN` | no |  | Cross-account AssumeRole |
| `SB_AWS_ENDPOINT` | no |  | LocalStack / VPC endpoint override |

**AWS credentials** are read from the standard AWS SDK chain
(IRSA, instance role, `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`,
shared profile). The agent deliberately does **not** add new env
vars for AWS credentials, that would invite operators to mix
sources.

## worker

| Env var | Required | Default | Notes |
|---|---|---|---|
| `DATABASE_URL` | **yes** |  | Same Postgres as the api |
| `REDIS_URL` | **yes** |  | Same Redis as the api |
| `SB_WORKER_GITOPS_ENABLED` | no | `false` | Must match api's `SB_GITOPS_ENABLED` |
| `SB_DISCOVER_TARGETS_JSON` | no |  | Periodic discovery targets (admin API tracked) |
| `SB_SWEEP_WRAPS_INTERVAL` | no | `60s` | |
| `SB_SWEEP_SECRETS_INTERVAL` | no | `5m` | |
| `SB_SWEEP_SECRETS_STALE_AFTER` | no | `24h` | |
| `SB_SWEEP_AGENTS_INTERVAL` | no | `60s` | |
| `SB_SWEEP_AGENTS_STALE_AFTER` | no | `5m` | |
| `SB_SWEEP_JOBS_INTERVAL` | no | `30s` | |
| `SB_SWEEP_GITOPS_POLL_INTERVAL` | no | `15s` | |
| `SB_SWEEP_GITOPS_TIMEOUT_INTERVAL` | no | `60s` | |
| `SB_NOTIFICATION_WEBHOOK_URL` | no |  | Generic webhook |
| `SB_NOTIFICATION_WEBHOOK_FORMAT_SLACK` | no | `false` | Wraps payload in `{text: ...}` |

## controller

| Env var | Required | Default | Notes |
|---|---|---|---|
| `KUBECONFIG` | for out-of-cluster runs |  | In-cluster uses the projected SA |
| `LEADER_ELECTION_NAMESPACE` | no | controller's own | |
| `METRICS_ADDR` | no | `:8080` | Prometheus exposition |
| `WATCH_NAMESPACE` | no | "" (all) | Limit reconciliation scope |

## Secret material, naming convention

| Material | What it is | Where it lives | Rotation |
|---|---|---|---|
| `SB_JWT_SECRET` | HMAC key for HS256 login tokens | api env / K8s Secret | Operator-rotated (no rotation runbook yet, tracked) |
| `SB_WRAP_MASTER_KEY` | Master key for the `local` KMS backend | api env / K8s Secret | **Don't use in production**, use Vault Transit or AWS KMS |
| `SB_KMS_VAULT_TOKEN` | Vault token for the `vault-transit` backend | api env / K8s Secret | Lease-tracked; refresh via Vault rotation |
| Agent identity (`agent_id` + `agent_secret`) | Per-agent credential, sent as `X-Agent-Secret` | `SB_IDENTITY_FILE` on a persistent volume (or `SB_AGENT_ID` / `SB_AGENT_SECRET`) | Revoke the agent, create a new enrollment token, re-enroll with an empty identity file |
| `SB_ENROLLMENT_TOKEN` | One-time enrollment token | K8s Secret, read on first boot | Single use; expires after 15 minutes by default |
| `SB_BOOTSTRAP_ADMIN_PASSWORD` | Seed admin password | api env at first boot | **Rotate immediately after first sign-in** |

None of these should ever appear in:

- Git history (use a K8s Secret, sealed-secret, or external-secrets-operator binding)
- CI logs (mask via the CI's secret-masking facility)
- Docker images (env vars in `Dockerfile ENV` are baked into layers)
- Application logs (the api strips them from all log lines)

## Insecure switches (dev only)

!!! danger "Never set any of these in production"
    Each switch below turns off a security control so a laptop dev loop
    works without TLS, a real KMS or MFA hardware. All of them default to
    the safe value. If you find one set on a shared or routable
    deployment, treat it as an incident.

| Switch | Component | Default | What the unsafe value does | Guard |
|---|---|---|---|---|
| `SB_ENV=dev` | api | `production` | Allows the `local` KMS backend and `SB_MFA_DEV_ALLOW_PWD`, seeds three dev users with logged passwords on an empty database, and drops the `Secure` flag from session cookies | Unknown values fail boot; WARN log at boot |
| `SB_KMS_BACKEND=local` (with `SB_WRAP_MASTER_KEY`) | api | `local` | Keeps the storage-envelope master key in the api's own environment, next to the data it protects | api refuses to boot unless `SB_ENV=dev`, so an unset backend fails closed in production; the `secrets-bridge` chart refuses `kms.backend=local` with `env=production` |
| `SB_ALLOW_INSECURE_HEADER_AUTH=true` | api | `false` | Accepts an `X-User-Id` header as the caller's identity when there is no session cookie or bearer token. Anyone who can reach the api can act as any user. | Not tied to `SB_ENV`; WARN log at boot |
| `SB_ALLOW_DIRECT_AGENT_MINT=true` | api | `false` | Re-enables `POST /api/v1/agents`, which creates an agent and returns a long-lived `agent_secret` outside the enrollment flow | No boot-time WARN. While off, the route answers `403 direct_agent_mint_disabled` |
| `SB_ALLOW_INSECURE_VAULT_ADDR=true` | api | `false` | Accepts `http://` Vault addresses on provider connections | WARN log at boot |
| `SB_PROVIDER_CONN_REJECT_SECRETS=false` | api | `true` | Turns off the check that rejects secret-shaped values (AWS keys, Vault tokens, JWTs, OAuth tokens) in provider-connection scope. Credential-shaped key names are still refused. | WARN log at boot |
| `SB_MFA_DEV_ALLOW_PWD=true` | api | `false` | Treats every live session as MFA-fresh, so step-up-gated actions (approve, reveal, role and provider edits) need only a password sign-in | api refuses to boot unless `SB_ENV=dev`; WARN log at boot |
| `SB_INSECURE_TRANSPORT=true` | agent | `false` | Allows a plain `http://` control-plane endpoint, so the agent credential and job traffic cross the network unencrypted | WARN log at boot; the `agent` chart refuses an `http://` endpoint unless `cp.insecureTransport=true` |

The [hardening checklist](index.md#hardening-checklist-before-exposing-to-anyone)
checks each of these before a deployment is exposed.
