---
title: Secrets Bridge
description: The brain behind your secrets.
hide:
  - navigation
---

# Secrets Bridge

> **The brain behind your secrets.**

A unified secrets **control plane** for cloud-native teams. Approvals, RBAC, audit, and least-privilege agent execution across HashiCorp Vault, AWS Secrets Manager, Azure Key Vault, GCP Secret Manager, and Kubernetes / GitOps — without your developers ever holding raw provider credentials.

<div class="grid cards" markdown>

-   :material-shield-key: **Workflow-gated reads & writes**

    Developers request access through configurable workflows. Approvers vote. Agents fetch (or write) values. **Every value is single-shot, audited, and KMS-wrapped at rest.**

-   :material-archive-eye: **Audit you can actually use in a SOC2 review**

    The `audit_events` table is append-only at the schema layer
    (`BEFORE UPDATE` / `BEFORE DELETE` triggers reject mutations).
    The repository interface deliberately omits Update / Delete.

-   :material-cloud-key-outline: **No KMS lock-in**

    Three backends ship today behind one `SB_KMS_BACKEND` knob:
    `local` (dev), `vault-transit` (OSS production), `aws-kms`
    (AWS production). Bring your own — no cloud lock-in.

-   :material-shield-lock-open: **Plaintext never on the wire**

    TLS + per-direction wire-envelope encryption (X25519 for
    CP→Agent, KMS-DEK + AES-GCM for Agent→CP) means even a
    TLS-terminating proxy in your mesh sees only ciphertext.

</div>

## Who this is for

- **Regulated teams** (fintech, healthtech, defence-adjacent) where
  "everyone has full Vault read access" is no longer an answer your
  auditor will accept.
- **Platform teams** standing up multi-cluster / multi-account
  secrets governance from scratch.
- **Compliance engineers** who need a real audit trail
  (correlation IDs, immutable rows, value-free metadata) without
  reaching for an SIEM bolt-on.

## How it's different

| | Secrets Bridge | Direct Vault | AWS Secrets Manager + IAM | Most "secrets SaaS" |
|---|---|---|---|---|
| Multi-provider | ✅ Vault + AWS + Azure + GCP | Vault only | AWS only | Varies |
| Workflow approval per read | ✅ Built-in | Plugin / RFC | ❌ | Some |
| Single-shot reveal-once UX | ✅ Built-in | ❌ | ❌ | Some |
| Append-only audit at schema | ✅ Postgres triggers | ❌ application-layer | CloudTrail (not append-only) | Varies |
| Self-hostable | ✅ OSS, no SaaS dependency | ✅ | n/a | ❌ |
| KMS choice | ✅ Vault Transit / AWS KMS / local | n/a | AWS KMS only | Provider-controlled |
| Agent uses **only** outbound traffic | ✅ Loopback probes; no inbound | n/a | n/a | Varies |

## What it doesn't do (yet)

- **OIDC SSO** lands as a follow-up — today the api ships with a
  local-admin email/password flow plus a JWT issued via HS256.
- **Per-tenant KMS scoping** — one CMK per deployment for now;
  multi-tenant scoping is the next major slice.
- **Slack / PagerDuty notifications** — webhook is in; native
  sinks are stubs.
- **GCP Secret Manager + Azure Key Vault** discovery — works at the
  metadata interface level; the agent's resolvers ship Vault +
  AWS-SM today and the others land per design partner request.

## Get started

[:material-rocket-launch: **Try it locally with docker-compose**](operations/docker-compose.md){ .md-button .md-button--primary }
[:material-book-open-variant: **Read the architecture**](overview/architecture.md){ .md-button }

## Project status

This is a **pre-v1.0** project. The architectural foundation is
solid (BRD-aligned, polyrepo, infra-free `core`, type-safe Go), but
several P0 items from the [SECURITY_REVIEW](https://github.com/secrets-bridge/.github/blob/main/SECURITY.md) are still open:
real OIDC, agent workload identity, rate limiting, key-rotation
runbook. We're tracking them on the
[org project board](https://github.com/orgs/secrets-bridge/projects/1).

If you'd like to be a design partner — particularly if you're in
financial services, healthcare, or government-adjacent — please
open an issue at [secrets-bridge/.github](https://github.com/secrets-bridge/.github).
