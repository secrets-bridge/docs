---
title: Secrets Bridge
# Quoted because the value contains a `:` (after "plane") which YAML
# would otherwise interpret as a second mapping. An unquoted colon
# silently kills the whole frontmatter (page.meta becomes empty, the
# nav config wins page.title, and SEO tags fall back to site defaults.
seo_title: "Secrets Bridge: Unified Secrets Control Plane"
description: "Unified secrets control plane for approvals, RBAC, audit, and least-privilege agent execution across your secrets providers. AWS/Vault live today; Azure/GCP roadmap."
hide:
  - navigation
  - toc
---


# Secrets Bridge

<div class="sb-landing" markdown>

<div class="sb-hero" markdown>

<span class="sb-hero__eyebrow">Unified secrets control plane</span>

<div class="sb-hero__wordmark">SecretsBridge</div>

<h2 class="sb-hero__tagline">The control plane for secrets governance.</h2>

<p class="sb-hero__subhead">
Keep secrets in Vault, AWS Secrets Manager, Azure Key Vault, GCP
Secret Manager, or Kubernetes. Secrets Bridge governs who can
request, approve, reveal, patch, and audit access, without storing
plaintext secrets in the control plane.
</p>

<div class="sb-hero__ctas" markdown>
[:material-rocket-launch: Try it locally](operations/docker-compose.md){ .md-button .md-button--primary }
[:material-book-open-variant: Read the architecture](overview/architecture.md){ .md-button }
[:material-github: Star on GitHub](https://github.com/secrets-bridge){ .md-button }
</div>

</div>

<h2 class="sb-section-heading">What is Secrets Bridge?</h2>

Secrets Bridge is a **unified secrets control plane** for governing secrets
across external providers **without storing secret values in the control
plane**.

It **does not replace** HashiCorp Vault, AWS Secrets Manager, Azure Key Vault,
GCP Secret Manager, or Kubernetes External Secrets. It governs **access,
workflows, approvals, audit, and agent execution** around them. The values stay
in your provider.

[:material-check-decagram: See what's live, QA-certified, and on the roadmap](overview/product-status.md){ .md-button .md-button--primary }

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
    layer: `BEFORE UPDATE` / `BEFORE DELETE` triggers reject
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
| Multi-provider | ✅ Vault + AWS today; Azure + GCP on roadmap | Vault only | AWS only | Varies |
| Workflow approval per read | ✅ Built-in | Plugin / RFC | ❌ | Some |
| Single-shot reveal-once UX | ✅ Built-in | ❌ | ❌ | Some |
| Append-only audit at schema | ✅ Postgres triggers | ❌ application-layer | CloudTrail (not append-only) | Varies |
| Self-hostable | ✅ OSS, no SaaS dependency | ✅ | n/a | ❌ |
| KMS choice | ✅ Vault Transit / AWS KMS / local | n/a | AWS KMS only | Provider-controlled |
| Agent uses **only** outbound traffic | ✅ Loopback probes; no inbound | n/a | n/a | Varies |

<h2 class="sb-section-heading">On the roadmap (not live yet)</h2>

Listed here because they are **not** shipped. See the
[product status page](overview/product-status.md) for the exact
Live / QA-certified / In-progress / Roadmap split.

- **Azure Key Vault** and **GCP Secret Manager** providers. The agent's
  resolvers ship Vault + AWS Secrets Manager today; the others are next.
- **HashiCorp Vault advanced flows** and deeper **Kubernetes External Secrets**
  integration.
- **Flux** integration (read-only ArgoCD observation ships today).
- **Per-tenant KMS scoping**: one CMK per deployment for now.
- **Agent connection-scoped job claim** and a **richer agent fleet dashboard**.
- **Native Slack / PagerDuty** notification sinks: webhook is in; native
  sinks are next.

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
If you'd like to be a <strong>design partner</strong>,
particularly if you're in financial services, healthcare, or
government-adjacent, please open an issue at
<a href="https://github.com/secrets-bridge/.github">secrets-bridge/.github</a>.
</p>
</div>

</div>
