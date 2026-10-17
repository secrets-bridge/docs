---
title: Secrets Bridge
# Quoted: the value contains a `:`, which YAML would otherwise read as a
# second mapping and drop the whole frontmatter.
seo_title: "Secrets Bridge: access control for the secrets you already keep"
description: "Secrets Bridge adds access requests, approvals, audit and agent execution around the secrets you keep in AWS Secrets Manager and HashiCorp Vault. Values stay in your provider."
hide:
  - navigation
  - toc
---

<div class="sb-home" markdown>

<section class="sb-hero" aria-labelledby="sb-hero-title" markdown>

<h1 id="sb-hero-title" class="sb-display">Govern who uses your secrets.</h1>

<p class="sb-lede">
Secrets Bridge adds access requests, approvals, audit and agent execution
around the secrets you already keep in AWS Secrets Manager and HashiCorp
Vault. We keep requests, approvals and audit metadata. Your secret values
stay in your provider.
</p>

<div class="sb-actions" markdown>
[Run it locally](operations/docker-compose.md){ .md-button .md-button--primary }
[Read the architecture](overview/architecture.md){ .md-button }
<a class="sb-textlink" href="https://github.com/secrets-bridge">Source on GitHub</a>
</div>

<p class="sb-note">Open source and pre-1.0. <a href="overview/product-status/">See what is live today</a> and what is still on the roadmap.</p>

</section>

<figure class="sb-figure" tabindex="0" role="region" aria-label="Architecture diagram">
<img src="assets/architecture-light.svg#only-light" width="1100" height="400" alt="People use the console and API. The control plane holds workflow, policy, audit and metadata. An agent inside your boundary calls out to it and reads the provider. Providers connect only to the agent.">
<img src="assets/architecture-dark.svg#only-dark" width="1100" height="400" alt="People use the console and API. The control plane holds workflow, policy, audit and metadata. An agent inside your boundary calls out to it and reads the provider. Providers connect only to the agent.">
</figure>

<section class="sb-section" aria-labelledby="sb-how" markdown>

<h2 id="sb-how" class="sb-section-title">How a request works</h2>

<ol class="sb-steps">
<li>
<svg class="sb-icon" viewBox="0 0 24 24" aria-hidden="true"><g fill="none" stroke="currentColor" stroke-width="1.75" stroke-linejoin="miter" stroke-linecap="butt"><rect x="3.5" y="4" width="11" height="16"/><path d="M10 12H20.5M17 8.5L20.5 12L17 15.5"/></g></svg>
<h3>Ask for access</h3>
<p>Name the secret, the keys you need and why. A request carries key names, never a value.</p>
</li>
<li>
<svg class="sb-icon" viewBox="0 0 24 24" aria-hidden="true"><g fill="none" stroke="currentColor" stroke-width="1.75" stroke-linejoin="miter" stroke-linecap="butt"><path d="M5 3.5V20.5"/><path d="M9.5 12.5L13 16L20 8"/></g></svg>
<h3>Someone approves</h3>
<p>The policy for the project and environment decides how many approvals it needs and from whom. By default, nobody approves their own request.</p>
</li>
<li>
<svg class="sb-icon" viewBox="0 0 24 24" aria-hidden="true"><g fill="none" stroke="currentColor" stroke-width="1.75" stroke-linejoin="miter" stroke-linecap="butt"><path d="M3.5 11H20.5V20.5H3.5Z"/><path d="M12 16V3.5M8.5 7L12 3.5L15.5 7"/></g></svg>
<h3>The agent reads it</h3>
<p>An agent inside your boundary claims the job, reads the provider and seals the values into a single-use wrap. It only ever calls out.</p>
</li>
<li>
<svg class="sb-icon" viewBox="0 0 24 24" aria-hidden="true"><g fill="none" stroke="currentColor" stroke-width="1.75" stroke-linejoin="miter" stroke-linecap="butt"><path d="M9 6H20.5M9 12H20.5M9 18H16"/><path d="M4 5H6.5V7.5H4ZM4 11H6.5V13.5H4ZM4 17H6.5V19.5H4Z"/></g></svg>
<h3>Reveal once, on the record</h3>
<p>The requester reveals each value once, behind a second factor. Every step lands in the audit log under one correlation ID.</p>
</li>
</ol>

</section>

<section class="sb-section sb-split" aria-labelledby="sb-holds" markdown>

<div markdown>
<h2 id="sb-holds" class="sb-section-title">What it holds to</h2>
<p class="sb-lede sb-lede--small">These are enforced in code, not left to policy. The <a href="overview/threat-model/">threat model</a> shows how each boundary is kept.</p>
</div>

<ul class="sb-rules">
<li><strong>No values at rest in the control plane.</strong> Not in Postgres, Redis, logs, audit events or the browser.</li>
<li><strong>The agent only calls out.</strong> No inbound port, no database, no Kubernetes API access to Secrets.</li>
<li><strong>Production never allows direct reveal.</strong> The refusal is enforced in code and audited.</li>
<li><strong>Values move once.</strong> KMS-wrapped, single-use, short-lived, and opened only by the right person.</li>
<li><strong>Audit is append-only and metadata-only.</strong> Who, what, when and why, never the value.</li>
<li><strong>Agents are bound and revocable.</strong> One-time enrollment tokens, one provider connection per agent, revoked at once.</li>
</ul>

</section>

<section class="sb-section" aria-labelledby="sb-today" markdown>

<h2 id="sb-today" class="sb-section-title">What works today</h2>

<div class="sb-status">
<div>
<h3>Implemented</h3>
<ul>
<li>AWS Secrets Manager and HashiCorp Vault through the agent</li>
<li>Read requests with policy-driven approval</li>
<li>Direct reveal in non-production, behind a second factor</li>
<li>Cross-team requests: another team supplies the values</li>
<li>Agent enrollment, status and revoke</li>
<li>Append-only audit trail</li>
</ul>
</div>
<div>
<h3>Roadmap</h3>
<ul>
<li>Azure Key Vault and GCP Secret Manager providers</li>
<li>Deeper Kubernetes External Secrets integration</li>
<li>Flux integration</li>
<li>Agents that claim only their own connection's jobs</li>
</ul>
<p class="sb-muted">Not shipped. Don't plan around these yet.</p>
</div>
</div>

<p><a href="overview/product-status/">Full product status</a>, with what is QA-certified and what is in progress.</p>

</section>

<section class="sb-section sb-end" aria-labelledby="sb-start" markdown>

<h2 id="sb-start" class="sb-section-title">Start on your laptop</h2>

<p class="sb-lede sb-lede--small">The api repo's compose file starts Postgres, Redis and the control plane; the console and the agent run from their own repos. The local guide walks through the whole flow against a dev Vault.</p>

<div class="sb-actions" markdown>
[Run it locally](operations/docker-compose.md){ .md-button }
[Operations guide](operations/index.md){ .md-button }
</div>

</section>

</div>
