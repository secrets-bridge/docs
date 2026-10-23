---
title: Secrets Bridge
# Quoted: the value contains a `:`, which YAML would otherwise read as a
# second mapping and drop the whole frontmatter.
seo_title: "Secrets Bridge: access control for secrets you already keep"
description: "Secrets Bridge adds access requests, approvals and audit around secrets you keep in AWS Secrets Manager and HashiCorp Vault. Values stay in your provider."
hide:
  - navigation
  - toc
---

<div class="sb-home" markdown>

<section class="sb-hero" aria-labelledby="sb-hero-title" markdown>

<div class="sb-hero__copy" markdown>

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

</div>

<aside class="sb-keep" aria-label="What Secrets Bridge keeps and never keeps">
<div class="sb-keep__col">
<h2 class="sb-keep__title sb-keep__title--ok">We keep</h2>
<ul>
<li>Requests, and who approved them</li>
<li>The audit trail: who, what, when and why</li>
<li>Which secret paths and key names a project may use</li>
</ul>
</div>
<div class="sb-keep__col">
<h2 class="sb-keep__title sb-keep__title--never">We never keep</h2>
<ul>
<li>Secret values in plain text. In transit a value exists only as an encrypted, single-use wrap with a short lifetime.</li>
<li>Provider credentials. The agent uses its own, inside your infrastructure.</li>
</ul>
</div>
<p class="sb-keep__foot">The agent runs inside your infrastructure and only calls out, so you open no inbound port.</p>
</aside>

</section>

<section class="sb-section sb-section--flow" aria-labelledby="sb-flow-title" markdown>

<h2 id="sb-flow-title" class="sb-section-title">Where your secrets go, and where they don't</h2>

<p class="sb-lede sb-lede--small">Values stay in your provider until an approved request needs them. Then they travel once, sealed, and only to the person who asked. Pick a step to follow it.</p>

--8<-- "includes/flow.html"

</section>

<section class="sb-section sb-split" aria-labelledby="sb-holds" markdown>

<div markdown>
<h2 id="sb-holds" class="sb-section-title">What it holds to</h2>
<p class="sb-lede sb-lede--small">These are enforced in code, not left to policy. The <a href="overview/threat-model/">threat model</a> shows how each boundary is kept.</p>
</div>

<ul class="sb-rules">
<li><strong>No plaintext values in the control plane.</strong> Not in Postgres, Redis, logs, audit events or the browser. In transit, values are KMS-wrapped.</li>
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
