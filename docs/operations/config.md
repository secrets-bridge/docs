# Configuration reference

Every environment variable across `api` / `agent` / `worker` /
`controller` / `gateway`. Defaults shown match the source tree as of v0.X.

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
| `SB_PUBLIC_URL` | no |  | The install's public address, for example `https://secrets.example.com`. Sign-in redirect URIs are built from it, never from request headers. When set, the console shows it read-only; unset, an admin saves it under Admin → Sign-in. Must be `https`, with no user info, query or fragment; plain `http` only for `localhost` or a loopback address with `SB_ENV=dev`. An invalid value stops the api at boot. See [Sign in with Google](google-sign-in.md#1-set-the-public-address) |
| `SB_OBJECTSTORE_BUCKET` | no |  | Bucket for media (logos). Unset, with no other `SB_OBJECTSTORE_*` set, turns object storage off. See [Object storage](object-storage.md) |
| `SB_OBJECTSTORE_REGION` | yes with a bucket |  | Bucket region |
| `SB_OBJECTSTORE_ENDPOINT` | no |  | `http://` or `https://` endpoint override for S3-compatible servers such as MinIO, or a VPC endpoint (`https://s3.example.com`). Unset for AWS S3. |
| `SB_OBJECTSTORE_FORCE_PATH_STYLE` | no | `false` | `true` or `false`. `true` for path-style addressing (MinIO) |
| `SB_OBJECTSTORE_PREFIX` | no |  | Key prefix inside the bucket. Slashes at either end are trimmed |
| `SB_OBJECTSTORE_SSE` | no |  | Unset or empty sends no SSE header. Otherwise exactly `AES256` (SSE-S3) or `aws:kms` (SSE-KMS) |
| `SB_OBJECTSTORE_KMS_KEY_ID` | yes for `aws:kms` |  | KMS key id, ARN or alias. Refused with any other SSE mode |
| `SB_OBJECTSTORE_LOGO_BACKFILL` | no | `true` | Move logos still stored in Postgres to the bucket at start. `false` for the first step of a rolling upgrade |

!!! note "Object storage behaviour"
    Without object storage the api boots, but logo uploads and deletes
    return `503 logo storage is not configured`, and logos still stored in
    Postgres are served. With any setting invalid, or a bucket that fails
    `HeadBucket` within 15 seconds, the api refuses to boot. Credentials
    come from the standard AWS SDK chain, as for `aws-kms`; there are no
    object-storage credential variables. Object storage has not passed QA
    yet. See [Object storage](object-storage.md).

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
| `SB_WORKER_LOCAL_ADDR` | no | `127.0.0.1:8091` | Local listen address |
| `SB_WORKER_SHUTDOWN_GRACE` | no | `15s` | |
| `SB_WORKER_WRAPS_EXPIRED_INTERVAL` | no | `1m` | |
| `SB_WORKER_SECRETS_STALE_INTERVAL` | no | `5m` | |
| `SB_WORKER_SECRETS_STALE_AFTER` | no | `24h` | |
| `SB_WORKER_AGENTS_STALE_INTERVAL` | no | `1m` | |
| `SB_WORKER_AGENTS_STALE_AFTER` | no | `5m` | |
| `SB_WORKER_JOBS_RECOVERY_INTERVAL` | no | `30s` | |
| `SB_WORKER_DISCOVER_INTERVAL` | no | `1h` | |
| `SB_WORKER_REVEAL_SESSIONS_EXPIRED_INTERVAL` | no | `5s` | |
| `SB_WORKER_CROSS_TEAM_FILL_EXPIRED_INTERVAL` | no | `30s` | |
| `SB_WORKER_GITOPS_POLL_INTERVAL` | no | `15s` | |
| `SB_WORKER_GITOPS_TIMEOUT_INTERVAL` | no | `1m` | |
| `SB_WORKER_GITOPS_HTTP_TIMEOUT` | no | `15s` | Per-call ceiling for ArgoCD requests |
| `SB_WORKER_GITOPS_BATCH_SIZE` | no | `20` | Observations per poll. At least `1` |
| `SB_WORKER_WEBHOOK_URL` | no |  | Generic webhook. Also turns on the waiting-account message, which goes to this webhook only |
| `SB_WORKER_WEBHOOK_SLACK_FORMAT` | no | `false` | Wraps payload in `{text: ...}` |
| `SB_WORKER_USERS_PENDING_INTERVAL` | no | `1m` | How often the `users-pending` sweeper posts about accounts waiting for approval, at most one message per run. At least `30s`, or the worker refuses to start. See [Sign in with Google](google-sign-in.md#notify-admins-from-the-worker) |
| `SB_PUBLIC_URL` | no |  | Same variable as the api's, used for the link in the waiting-account message. Unset, the address saved in the console is used. An invalid value stops the worker at boot |

Every duration is a Go duration (`30s`, `5m`, `1h`) and must be greater than zero, or the worker refuses to start.

## controller

| Env var | Required | Default | Notes |
|---|---|---|---|
| `KUBECONFIG` | for out-of-cluster runs |  | In-cluster uses the projected SA |
| `LEADER_ELECTION_NAMESPACE` | no | controller's own | |
| `METRICS_ADDR` | no | `:8080` | Prometheus exposition |
| `WATCH_NAMESPACE` | no | "" (all) | Limit reconciliation scope |

## gateway

The [Gateway](../components/gateway.md) binary. Each variable also has a flag
(`gateway -h`); a flag overrides its variable. A malformed value stops the boot
instead of falling back to the default. The
[`secrets-bridge-gateway` chart](https://github.com/secrets-bridge/charts/blob/main/gateway/README.md)
sets these from its values, and the
[gateway README](https://github.com/secrets-bridge/gateway#configuration) is the
source for this table.

| Env var | Required | Default | Notes |
|---|---|---|---|
| `SB_CP_ENDPOINT` | **yes** |  | `https://cp.example.com`. `https://` only, unless `SB_INSECURE_TRANSPORT=true`. No userinfo |
| `SB_INSECURE_TRANSPORT` | no | `false` | Dev only: allows `http://` to the control plane and to every Argo CD `base_url`. See [Insecure switches](#insecure-switches-dev-only) |
| `SB_CP_CA_FILE` | no |  | PEM bundle that replaces the system roots for the control plane |
| `SB_CP_TLS_SERVER_NAME` | no |  | TLS server name override |
| `SB_GATEWAY_IDENTITY_FILE` | no | `/etc/secrets-bridge/gateway/identity.json` | `{"gateway_id": "...", "gateway_secret": "..."}` from enrollment. Mode `0400`, `0600` or `0440` (what a Secret volume with `fsGroup` produces). Any bit for other users, or group write, is refused at boot |
| `SB_GATEWAY_ID` / `SB_GATEWAY_SECRET` | no |  | Credential pair as env vars. When both are unset the identity file is read. The chart does not use them |
| `SB_GATEWAY_LOCAL_ADDR` | no | `127.0.0.1:8091` | `/healthz`, `/readyz` and `/metrics`. Must be a literal loopback IP; `localhost` is refused |
| `SB_GATEWAY_CONNECTORS_FILE` | no |  | JSON list of locally bound connectors. Empty binds none. The chart renders it into a ConfigMap |
| `SB_GATEWAY_ENABLE_R2_CONNECTORS` | no | `false` | Binds the Release 2 `eso` and `rollout` kinds. Not supported for production: the Gateway logs a WARN at boot while it is on. When off, a connectors file that names either kind is refused. The chart never sets it |
| `SB_GATEWAY_SHUTDOWN_GRACE` | no | `15s` | Half is spent waiting for passes in flight, then unfinished tasks are released |
| `SB_GATEWAY_HEARTBEAT_INTERVAL` | no | `30s` | Used until the control plane suggests an interval |
| `SB_GATEWAY_CLAIM_INTERVAL` | no | `5s` | Base claim interval, jittered between half and one and a half times |
| `SB_GATEWAY_CLAIM_IDLE_MAX` | no | `30s` | Longest claim interval after empty polls. Not shorter than the claim interval |
| `SB_GATEWAY_CLAIM_CONCURRENCY` | no | `1` | Observation passes in flight per replica, 1 to 16 |
| `SB_GATEWAY_LEASE_MARGIN` | no | `3s` | A pass stops this long before its lease expires |
| `SB_GATEWAY_PASS_TIMEOUT` | no | `30s` | Upper bound for one pass |
| `SB_GATEWAY_CP_UNREACHABLE_AFTER` | no | `2m` | The Gateway turns not ready when no heartbeat has been accepted for this long |
| `SB_LOG_LEVEL` | no | `info` | `debug`, `info`, `warn` or `error` |

The Gateway ignores `HTTP_PROXY` and `HTTPS_PROXY` for every connection, so a
bearer credential never reaches a proxy.

Each entry in the connectors file has a `name` (a DNS label the control plane
binds to), a `kind` and `settings`. For `argocd` the settings are `base_url`,
`token_file` (an absolute path), optional `ca_file`, `tls_server_name` and
`timeout` (1s to 60s, default 10s), `allowed_projects` (at least one AppProject)
and `applications` (at least one `{id, name, app_namespace?}`). Unknown fields,
unknown kinds and duplicate names are refused at load.

## Secret material, naming convention

| Material | What it is | Where it lives | Rotation |
|---|---|---|---|
| `SB_WRAP_MASTER_KEY` | Master key for the `local` KMS backend | api env / K8s Secret | **Don't use in production**, use Vault Transit or AWS KMS |
| `SB_KMS_VAULT_TOKEN` | Vault token for the `vault-transit` backend | api env / K8s Secret | Lease-tracked; refresh via Vault rotation |
| Agent identity (`agent_id` + `agent_secret`) | Per-agent credential, sent as `X-Agent-Secret` | `SB_IDENTITY_FILE` on a persistent volume (or `SB_AGENT_ID` / `SB_AGENT_SECRET`) | Revoke the agent, create a new enrollment token, re-enroll with an empty identity file |
| `SB_ENROLLMENT_TOKEN` | One-time enrollment token | K8s Secret, read on first boot | Single use; expires after 15 minutes by default |
| Gateway identity (`gateway_id` + `gateway_secret`) | Per-Gateway credential, sent as `X-Gateway-Secret` | An existing K8s Secret, mounted read-only as `SB_GATEWAY_IDENTITY_FILE` | No rotation in Release 1: revoke the Gateway, create a new one, enroll it and update the Secret |
| Gateway enrollment token | One-time token from `POST /api/v1/admin/gateways/:id/enrollment-token` | Used once from the operator's workstation, never stored in the cluster | Single use; expires after 15 minutes by default |
| Argo CD token for the Gateway | Read-only token of a local Argo CD account (`applications, get`) | An existing K8s Secret, mounted as a file per connector | Update the Secret; the Gateway re-reads the file |
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
| `SB_ALLOW_INSECURE_HEADER_AUTH=true` | api | `false` | Accepts an `X-User-Id` header as the caller's identity when there is no session cookie. Anyone who can reach the api can act as any user. | Not tied to `SB_ENV`; WARN log at boot |
| `SB_ALLOW_DIRECT_AGENT_MINT=true` | api | `false` | Re-enables `POST /api/v1/agents`, which creates an agent and returns a long-lived `agent_secret` outside the enrollment flow | No boot-time WARN. While off, the route answers `403 direct_agent_mint_disabled` |
| `SB_ALLOW_INSECURE_VAULT_ADDR=true` | api | `false` | Accepts `http://` Vault addresses on provider connections | WARN log at boot |
| `SB_ALLOW_UNSEALED_WRAPS=true` | api | `false` | Hands wraps to an agent with no X25519 public key on file as plaintext over TLS, and accepts a plaintext `value` when an agent posts a wrap. Only for an agent that predates wire-envelope sealing. | WARN log at boot. While off, a keyless agent gets `409 agent_public_key_required` before the wrap is consumed and a `value` post gets `400 envelope_required`; both are audited |
| `SB_PROVIDER_CONN_REJECT_SECRETS=false` | api | `true` | Turns off the check that rejects secret-shaped values (AWS keys, Vault tokens, JWTs, OAuth tokens) in provider-connection scope. Credential-shaped key names are still refused. | WARN log at boot |
| `SB_MFA_DEV_ALLOW_PWD=true` | api | `false` | Treats every live session as MFA-fresh, so step-up-gated actions (approve, reveal, role and provider edits) need only a password sign-in | api refuses to boot unless `SB_ENV=dev`; WARN log at boot |
| `SB_INSECURE_TRANSPORT=true` | agent | `false` | Allows a plain `http://` control-plane endpoint, so the agent credential and job traffic cross the network unencrypted | WARN log at boot; the `agent` chart refuses an `http://` endpoint unless `cp.insecureTransport=true` |
| `SB_INSECURE_TRANSPORT=true` | gateway | `false` | Allows plain `http://` to the control plane and to every Argo CD endpoint, so the Gateway credential and the Argo CD token cross the network unencrypted | WARN log at boot; the `secrets-bridge-gateway` chart refuses an `http://` URL unless `insecureTransport=true` |
| `SB_GATEWAY_ENABLE_R2_CONNECTORS=true` | gateway | `false` | Binds the Release 2 `eso` and `rollout` connectors, which read the Kubernetes API. Not supported for production | WARN log at boot. The Kubernetes self-check still refuses any access to Secrets. The gateway chart never sets it |

The [hardening checklist](index.md#hardening-checklist-before-exposing-to-anyone)
checks each of these before a deployment is exposed.
