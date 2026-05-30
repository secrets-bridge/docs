---
title: Secrets Bridge
# Quoted because the value contains a `:` (after "plane") which YAML
# would otherwise interpret as a second mapping. An unquoted colon
# silently kills the whole frontmatter — page.meta becomes empty, the
# nav config wins page.title, and SEO tags fall back to site defaults.
seo_title: "Secrets Bridge — Unified Secrets Control Plane"
description: "Unified secrets control plane: approvals, RBAC, audit, and least-privilege agent execution across Vault, AWS, Azure, GCP, and Kubernetes."
hide:
  - navigation
  - toc
---


# Secrets Bridge

<div class="sb-landing" markdown>

<div class="sb-hero" markdown>

<span class="sb-hero__eyebrow">Unified secrets control plane</span>

<div class="sb-hero__wordmark">SecretsBridge</div>

<h2 class="sb-hero__tagline">The brain behind your secrets.</h2>

<p class="sb-hero__subhead">
A distributed secrets control plane that connects and governs
secrets across every provider — without replacing the tools your
teams already use. One brain, every provider. Values stay home.
</p>

<div class="sb-hero__ctas" markdown>
[:material-rocket-launch: Try it locally](operations/docker-compose.md){ .md-button .md-button--primary }
[:material-book-open-variant: Read the architecture](overview/architecture.md){ .md-button }
[:material-github: Star on GitHub](https://github.com/secrets-bridge){ .md-button }
</div>

</div>

<h2 class="sb-section-heading">Why Secrets Bridge</h2>

<div class="grid cards sb-pillars" markdown>

-   :material-shield-key:{ .lg .middle .sb-pillar-icon } &nbsp;**Workflow-gated reads & writes**

    ---

    Developers request access through configurable workflows.
    Approvers vote. Agents fetch (or write) values. **Every
    value is single-shot, audited, and KMS-wrapped at rest.**

-   :material-archive-eye:{ .lg .middle .sb-pillar-icon } &nbsp;**SOC2-ready audit**

    ---

    The `audit_events` table is append-only at the schema
    layer — `BEFORE UPDATE` / `BEFORE DELETE` triggers reject
    mutations. Every action emits a correlation ID you can
    drill into.

-   :material-cloud-key-outline:{ .lg .middle .sb-pillar-icon } &nbsp;**No KMS lock-in**

    ---

    Three backends ship today behind one `SB_KMS_BACKEND`
    knob: `local` (dev), `vault-transit` (OSS production),
    `aws-kms` (AWS production). Bring your own. No cloud lock-in.

-   :material-shield-lock-open:{ .lg .middle .sb-pillar-icon } &nbsp;**Plaintext never on the wire**

    ---

    TLS + per-direction wire-envelope encryption (X25519 for
    CP→Agent, KMS-DEK + AES-GCM for Agent→CP). Even a
    TLS-terminating proxy in your mesh sees only ciphertext.

</div>

<h2 class="sb-section-heading">Who this is for</h2>

- **Regulated teams** (fintech, healthtech, defence-adjacent)
  where "everyone has full Vault read access" is no longer an
  answer your auditor will accept.
- **Platform teams** standing up multi-cluster / multi-account
  secrets governance from scratch.
- **Compliance engineers** who need a real audit trail
  (correlation IDs, immutable rows, value-free metadata) without
  reaching for an SIEM bolt-on.

<h2 class="sb-section-heading">How it's different</h2>

| | Secrets Bridge | Direct Vault | AWS Secrets Manager + IAM | Most "secrets SaaS" |
|---|---|---|---|---|
| Multi-provider | ✅ Vault + AWS + Azure + GCP | Vault only | AWS only | Varies |
| Workflow approval per read | ✅ Built-in | Plugin / RFC | ❌ | Some |
| Single-shot reveal-once UX | ✅ Built-in | ❌ | ❌ | Some |
| Append-only audit at schema | ✅ Postgres triggers | ❌ application-layer | CloudTrail (not append-only) | Varies |
| Self-hostable | ✅ OSS, no SaaS dependency | ✅ | n/a | ❌ |
| KMS choice | ✅ Vault Transit / AWS KMS / local | n/a | AWS KMS only | Provider-controlled |
| Agent uses **only** outbound traffic | ✅ Loopback probes; no inbound | n/a | n/a | Varies |

<h2 class="sb-section-heading">What it doesn't do (yet)</h2>

- **OIDC SSO** lands as a follow-up — today the api ships with a
  local-admin email/password flow plus a JWT issued via HS256.
- **Per-tenant KMS scoping** — one CMK per deployment for now;
  multi-tenant scoping is the next major slice.
- **Slack / PagerDuty notifications** — webhook is in; native
  sinks are stubs.
- **GCP Secret Manager + Azure Key Vault** discovery — the agent's
  resolvers ship Vault + AWS-SM today; the others land per
  design partner request.

<div class="sb-status" markdown>
<p class="sb-status__title">🚧 Pre-v1.0</p>
<p>
The architectural foundation is solid (BRD-aligned, polyrepo,
infra-free <code>core</code>, type-safe Go), but several P0
items from the
<a href="https://github.com/secrets-bridge/.github/blob/main/SECURITY.md">SECURITY_REVIEW</a>
are still open: real OIDC, agent workload identity, rate
limiting, key-rotation runbook. We're tracking them on the
<a href="https://github.com/orgs/secrets-bridge/projects/1">org project board</a>.
</p>
<p>
If you'd like to be a <strong>design partner</strong> —
particularly if you're in financial services, healthcare, or
government-adjacent — please open an issue at
<a href="https://github.com/secrets-bridge/.github">secrets-bridge/.github</a>.
</p>
</div>

</div>
