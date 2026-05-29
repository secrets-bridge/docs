# Configuration reference

Every environment variable across `api` / `agent` / `worker` /
`controller`. Defaults shown match the source tree as of v0.X.

## api

| Env var | Required | Default | Notes |
|---|---|---|---|
| `API_ADDR` | no | `:8080` | Listen address |
| `API_SHUTDOWN_GRACE` | no | `15s` | SIGTERM grace period |
| `LOG_LEVEL` | no | `info` | `debug` / `info` / `warn` / `error` |
| `DATABASE_URL` | **yes** | — | `postgres://user:pass@host:5432/db` |
| `DATABASE_MAX_CONNS` | no | `10` | pgxpool size |
| `DATABASE_CONN_LIFETIME` | no | `1h` | |
| `REDIS_URL` | **yes** | — | `redis://host:6379/0` |
| `REDIS_POOL_SIZE` | no | `10` | |
| `REDIS_DIAL_TIMEOUT` | no | `5s` | |
| `REDIS_NAMESPACE` | no | `secrets-bridge` | Key prefix |
| `SB_JWT_SECRET` | **yes** | — | 32+ bytes, base64 or raw. Fails boot if too short. |
| `SB_JWT_TOKEN_TTL` | no | `8h` | Login session lifetime |
| `SB_WRAP_MASTER_KEY` | yes when `SB_KMS_BACKEND=local` | — | base64 32 bytes |
| `SB_KMS_BACKEND` | no | `local` | `local` / `vault-transit` / `aws-kms` |
| `SB_KMS_VAULT_ADDR` | yes for `vault-transit` | — | |
| `SB_KMS_VAULT_TOKEN` | yes for `vault-transit` | — | |
| `SB_KMS_VAULT_KEY` | yes for `vault-transit` | — | Transit key name |
| `SB_KMS_VAULT_MOUNT` | no | `transit` | |
| `SB_KMS_AWS_REGION` | yes for `aws-kms` | — | |
| `SB_KMS_AWS_KEY_ID` | yes for `aws-kms` | — | Alias / ARN / key id |
| `SB_KMS_AWS_ENDPOINT` | no | — | LocalStack / VPC endpoint override |
| `SB_BOOTSTRAP_ADMIN_EMAIL` | recommended on first boot | — | See [Bootstrap](bootstrap.md) |
| `SB_BOOTSTRAP_ADMIN_PASSWORD` | recommended on first boot | — | |
| `SB_BOOTSTRAP_ADMIN_USER_ID` | optional | — | Opaque user_id for pre-OIDC role assignment |
| `SB_GITOPS_ENABLED` | no | `false` | BRD §26 ArgoCD endpoints + observation fan-out |

## agent

| Env var | Required | Default | Notes |
|---|---|---|---|
| `SB_CP_ENDPOINT` | **yes** | — | `https://api.example.com` |
| `SB_INSECURE_TRANSPORT` | no | `false` | Set `true` ONLY for local-dev `http://` |
| `SB_CP_CA_FILE` | no | — | Pin a private CA (replaces system roots) |
| `SB_CP_TLS_SERVER_NAME` | no | — | SNI override for private DNS |
| `SB_AGENT_ID` | **yes** | — | UUID from `POST /agents` |
| `SB_AGENT_SECRET` | **yes** | — | Returned once at mint |
| `SB_BOOTSTRAP_FILE` | optional | — | JSON `{agent_id, agent_secret}` alternative to env vars |
| `SB_CLUSTER_NAME` | **yes** for discovery | — | Stamped on every discovered secret |
| `SB_HEARTBEAT_INTERVAL` | no | `30s` | |
| `SB_CLAIM_INTERVAL` | no | `5s` | |
| `SB_CLAIM_CONCURRENCY` | no | `4` | Worker pool size |
| `SB_LOCAL_ADDR` | no | `127.0.0.1:8090` | Loopback probes |
| `SB_AGENT_PRIVATE_KEY` | no | — | base64 X25519 private key (wire envelope) |
| `SB_AGENT_PRIVATE_KEY_FILE` | no | — | File path alternative |
| `SB_VAULT_ADDR` | yes for Vault | — | |
| `SB_VAULT_TOKEN` | yes for Vault token auth | — | |
| `SB_VAULT_KUBERNETES_ROLE` | yes for Vault k8s auth | — | Alternative to token |
| `SB_VAULT_NAMESPACE` | no | — | Vault Enterprise namespace |
| `SB_AWS_REGION` | yes for AWS SM | — | |
| `SB_AWS_ROLE_ARN` | no | — | Cross-account AssumeRole |
| `SB_AWS_ENDPOINT` | no | — | LocalStack / VPC endpoint override |

**AWS credentials** are read from the standard AWS SDK chain
(IRSA, instance role, `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`,
shared profile). The agent deliberately does **not** add new env
vars for AWS credentials — that would invite operators to mix
sources.

## worker

| Env var | Required | Default | Notes |
|---|---|---|---|
| `DATABASE_URL` | **yes** | — | Same Postgres as the api |
| `REDIS_URL` | **yes** | — | Same Redis as the api |
| `SB_WORKER_GITOPS_ENABLED` | no | `false` | Must match api's `SB_GITOPS_ENABLED` |
| `SB_DISCOVER_TARGETS_JSON` | no | — | Periodic discovery targets (admin API tracked) |
| `SB_SWEEP_WRAPS_INTERVAL` | no | `60s` | |
| `SB_SWEEP_SECRETS_INTERVAL` | no | `5m` | |
| `SB_SWEEP_SECRETS_STALE_AFTER` | no | `24h` | |
| `SB_SWEEP_AGENTS_INTERVAL` | no | `60s` | |
| `SB_SWEEP_AGENTS_STALE_AFTER` | no | `5m` | |
| `SB_SWEEP_JOBS_INTERVAL` | no | `30s` | |
| `SB_SWEEP_GITOPS_POLL_INTERVAL` | no | `15s` | |
| `SB_SWEEP_GITOPS_TIMEOUT_INTERVAL` | no | `60s` | |
| `SB_NOTIFICATION_WEBHOOK_URL` | no | — | Generic webhook |
| `SB_NOTIFICATION_WEBHOOK_FORMAT_SLACK` | no | `false` | Wraps payload in `{text: ...}` |

## controller

| Env var | Required | Default | Notes |
|---|---|---|---|
| `KUBECONFIG` | for out-of-cluster runs | — | In-cluster uses the projected SA |
| `LEADER_ELECTION_NAMESPACE` | no | controller's own | |
| `METRICS_ADDR` | no | `:8080` | Prometheus exposition |
| `WATCH_NAMESPACE` | no | "" (all) | Limit reconciliation scope |

## Secret material — naming convention

| Material | What it is | Where it lives | Rotation |
|---|---|---|---|
| `SB_JWT_SECRET` | HMAC key for HS256 login tokens | api env / K8s Secret | Operator-rotated (no rotation runbook yet — tracked) |
| `SB_WRAP_MASTER_KEY` | Master key for the `local` KMS backend | api env / K8s Secret | **Don't use in production** — use Vault Transit or AWS KMS |
| `SB_KMS_VAULT_TOKEN` | Vault token for the `vault-transit` backend | api env / K8s Secret | Lease-tracked; refresh via Vault rotation |
| `SB_AGENT_SECRET` | Per-agent bearer secret | agent env / K8s Secret | Revoke + mint to rotate |
| `SB_BOOTSTRAP_ADMIN_PASSWORD` | Seed admin password | api env at first boot | **Rotate immediately after first sign-in** |

None of these should ever appear in:

- Git history (use a K8s Secret, sealed-secret, or external-secrets-operator binding)
- CI logs (mask via the CI's secret-masking facility)
- Docker images (env vars in `Dockerfile ENV` are baked into layers)
- Application logs (the api strips them from all log lines)
