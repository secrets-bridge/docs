---
title: Reference
description: Tables and catalogues. Every HTTP endpoint, every provider, every KMS backend, every permission string used by `auth.Require(perm)`.
---

# Reference

Catalogues + tables. Look here when you need the exact name of an
endpoint, a permission, a provider, or a KMS backend.

| Page | What |
|---|---|
| [HTTP API endpoints](api-endpoints.md) | Every route the api exposes today, the auth gate, and the response shape |
| [Providers supported](providers.md) | Vault / AWS SM / GCP SM / Azure Key Vault: auth + config shape per provider |
| [KMS backends](kms-backends.md) | `local` / `vault-transit` / `aws-kms`: when to use each, env vars |
| [Permissions catalog](permissions.md) | The canonical list of permission strings used by `auth.Require(perm)` |
