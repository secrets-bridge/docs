---
title: Operations
description: Deploy, bootstrap, troubleshoot. The pre-production hardening checklist plus the audit-log queries you'll lean on day two.
---

# Operations

Everything you need to run Secrets Bridge.

| Page | When you'd read it |
|---|---|
| [Running locally with docker compose](docker-compose.md) | First time trying it locally; smoke tests in CI |
| [Bootstrap & first sign-in](bootstrap.md) | After the stack is up, how to sign in, enroll your first agent, run your first request |
| [Configuration reference](config.md) | Exhaustive env-var table for `api` / `agent` / `worker` / `controller`, plus the dev-only insecure switches |
| [Troubleshooting](troubleshooting.md) | When things go wrong, common pitfalls + how to read the audit log |

## Production deployment

Install with the two Helm charts from the
[`charts`](https://github.com/secrets-bridge/charts) repo. Both publish as
OCI artifacts on GHCR:

| Chart | OCI reference | What it installs |
|---|---|---|
| `secrets-bridge` | `oci://ghcr.io/secrets-bridge/charts/secrets-bridge` | api, ui, worker and controller behind one Ingress, in the control-plane cluster |
| `secrets-bridge-agent` | `oci://ghcr.io/secrets-bridge/charts/secrets-bridge-agent` | One outbound-only agent per workload cluster or account |

Images publish to `ghcr.io/secrets-bridge/` as well. Until the first
`v0.1.0` release, chart versions look like `0.0.1-dev.<sha>`; pin an exact
version from the [package list](https://github.com/orgs/secrets-bridge/packages).

The chart defaults are the hardened baseline, so keep them rather than
writing your own Deployments: non-root pods with read-only root
filesystems, NetworkPolicies on by default, minimal RBAC, and render-time
guards. `helm install` fails before anything starts when `kms.backend=local`
is combined with `env=production`, when `env` or `kms.backend` is unknown,
when a production image resolves to a mutable `:dev` or `:latest` tag
without a digest, or when the agent's control-plane endpoint is plain
`http://`.

```bash
# 1. Pre-create the env Secret the chart reads (secrets.existingSecret,
#    default name secrets-bridge-env): SB_JWT_SECRET, DATABASE_URL,
#    REDIS_URL and the SB_KMS_* settings for your backend. Deliver it with
#    External Secrets, sealed-secrets or similar; never commit it.

# 2. Install the control plane. Production needs every image pinned.
helm install secrets-bridge oci://ghcr.io/secrets-bridge/charts/secrets-bridge \
  --version <chart-version> \
  --namespace secrets-bridge --create-namespace \
  --set ingress.host=secrets-bridge.example.com \
  --set kms.backend=aws-kms \
  --set kms.awsKms.region=us-east-1 \
  --set kms.awsKms.keyId=alias/sb-wrap \
  --set api.image.digest=sha256:<digest> \
  --set ui.image.digest=sha256:<digest> \
  --set worker.image.digest=sha256:<digest> \
  --set controller.image.digest=sha256:<digest>
```

Then onboard agents with the `secrets-bridge-agent` chart in enrollment
mode; see [Enrolling your first agent](bootstrap.md#enrolling-your-first-agent).
Each chart's README in the `charts` repo documents every value.

Around the charts you provide:

- A managed Postgres + Redis on a private network (we test against
  Postgres 17 + Redis 7)
- A real KMS backend (`vault-transit` or `aws-kms`, **never** `local`
  outside dev)
- An ingress controller with TLS and a real certificate

## Hardening checklist (before exposing to anyone)

- [ ] `SB_JWT_SECRET` is from `crypto/rand` (32+ bytes), not
  a memorable string
- [ ] `SB_ENV` is `production` (the default), never `dev`
- [ ] `SB_KMS_BACKEND` is `vault-transit` or `aws-kms`
  (**never** `local`)
- [ ] None of the api's
  [insecure switches](config.md#insecure-switches-dev-only) are set:
  `SB_ALLOW_INSECURE_HEADER_AUTH`, `SB_ALLOW_DIRECT_AGENT_MINT`,
  `SB_ALLOW_INSECURE_VAULT_ADDR`, `SB_MFA_DEV_ALLOW_PWD` are unset or
  `false`, and `SB_PROVIDER_CONN_REJECT_SECRETS` is unset or `true`
- [ ] `SB_INSECURE_TRANSPORT` on the agent is **unset** (default
  is to refuse `http://`), and the chart's `cp.insecureTransport` is
  `false`
- [ ] Agents are onboarded with one-time enrollment tokens, and their
  identity file sits on a persistent volume that only the agent mounts
- [ ] TLS terminator (ingress) configured with HSTS + a real
  certificate
- [ ] `SB_BOOTSTRAP_ADMIN_PASSWORD` is **rotated** immediately
  after first login
- [ ] The admin user has a real OIDC identity assigned and the local
  admin is disabled (see [Authentication](authentication.md))
- [ ] Postgres is on a private network: the api + worker are the
  only clients
- [ ] Redis is on a private network: the api + worker are the
  only clients
- [ ] Audit-event shipping is configured (the schema-level
  append-only triggers are a defense, not a substitute for
  off-host log shipping)
- [ ] Backup the KMS master key / Vault Transit key / AWS CMK:
  it's the only thing that can unwrap your envelopes

See the [Threat model](../overview/threat-model.md) for the
attacker postures these defend against.
