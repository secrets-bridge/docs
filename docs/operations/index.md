---
title: Operations
description: Deploy, bootstrap, troubleshoot. The pre-production hardening checklist plus the audit-log queries you'll lean on day two.
---

# Operations

Everything you need to run Secrets Bridge.

| Page | When you'd read it |
|---|---|
| [Deploying with docker-compose](docker-compose.md) | First time trying it locally; smoke tests in CI |
| [Bootstrap & first sign-in](bootstrap.md) | After the stack is up, how to sign in, mint your first agent, run your first request |
| [Configuration reference](config.md) | Exhaustive env-var table for `api` / `agent` / `worker` / `controller` |
| [Troubleshooting](troubleshooting.md) | When things go wrong, common pitfalls + how to read the audit log |

## Production deployment

The Helm chart bundle (`charts` repo) is **in progress**. See the
[org project board](https://github.com/orgs/secrets-bridge/projects/1).
Until it ships, production deployments work via:

- A `Deployment` per component (the published Docker images
  publish to GHCR under `ghcr.io/secrets-bridge/`)
- A managed Postgres + Redis (we test against Postgres 17 +
  Redis 7)
- A real KMS backend (`vault-transit` or `aws-kms`, **never**
  `local` outside dev)
- A `Secret` per component holding the env-var triplet (JWT
  secret, KMS config, bootstrap admin)
- An ingress (we recommend nginx-ingress or AWS ALB) wiring `/`
  to the UI container and `/api/v1/*` to the api

## Hardening checklist (before exposing to anyone)

- [ ] `SB_JWT_SECRET` is from `crypto/rand` (32+ bytes), not
  a memorable string
- [ ] `SB_KMS_BACKEND` is `vault-transit` or `aws-kms`
  (**never** `local`)
- [ ] `SB_INSECURE_TRANSPORT` on the agent is **unset** (default
  is to refuse `http://`)
- [ ] TLS terminator (ingress) configured with HSTS + a real
  certificate
- [ ] `SB_BOOTSTRAP_ADMIN_PASSWORD` is **rotated** immediately
  after first login
- [ ] The admin user has a real OIDC identity assigned (once
  api#26 ships) and the local admin is disabled
- [ ] Postgres is on a private network: the api is the only
  client
- [ ] Redis is on a private network: the api + worker are the
  only clients
- [ ] Audit-event shipping is configured (the schema-level
  append-only triggers are a defense, not a substitute for
  off-host log shipping)
- [ ] Backup the KMS master key / Vault Transit key / AWS CMK:
  it's the only thing that can unwrap your envelopes

See the [Threat model](../overview/threat-model.md) for the
attacker postures these defend against.
