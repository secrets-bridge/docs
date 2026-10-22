---
title: Reference
seo_title: "Secrets Bridge reference: API, providers, KMS, permissions"
description: "Reference pages for Secrets Bridge: every HTTP API endpoint, the supported secret providers, the KMS backends and the RBAC permission catalog."
---

# Reference

Catalogues + tables. Look here when you need the exact name of an
endpoint, a permission, a provider, or a KMS backend.

These pages list what the control plane and the agent accept today: the
routes the api serves, the secret providers the agent can reach, the KMS
backends behind envelope encryption, and the permission strings that
RBAC checks. The [Operations](../operations/index.md) pages explain how to
use them, and the [Configuration reference](../operations/config.md) lists
every environment variable.

- **[HTTP API endpoints](api-endpoints.md)**: every route grouped by area
  (probes, sign-in, agents, Gateways, access requests, cross-team requests,
  reveal sessions, admin, audit, provider connections and policy rules),
  with the auth each one needs, such as `public`, a session, a session
  plus a permission, or an agent's or Gateway's own secret header.
- **[Providers supported](providers.md)**: the provider types the agent
  dispatches to. HashiCorp Vault (KV v2, token or Kubernetes auth) and AWS
  Secrets Manager (the standard AWS SDK credential chain) ship. The
  `gcp-sm`, `azure-kv` and `kubernetes` resolvers are placeholders, and
  Azure Key Vault and GCP Secret Manager are on the
  [roadmap](../overview/product-status.md). The page also lists the
  credential-shaped keys each resolver refuses and how a new provider is
  added.
- **[KMS backends](kms-backends.md)**: the envelope-encryption backends
  selected with `SB_KMS_BACKEND`. `local` is for dev only; `vault-transit`
  and `aws-kms` are for production. Covers their settings, setup, key
  rotation and how to choose between them.
- **[Permissions catalog](permissions.md)**: the permission strings that
  `auth.Require(perm)` checks, the seed roles that carry them, which
  permissions are meant to be narrowed by scope, and how to add a new one. The
  api also serves the live catalog at `GET /api/v1/permissions`.
