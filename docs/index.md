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

<span class="sb-tag">Open source · pre-1.0</span>

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

<p class="sb-note"><a href="overview/product-status/">See what is live today</a> and what is still on the roadmap.</p>

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

<section class="sb-section" aria-labelledby="sb-people" markdown>

<h2 id="sb-people" class="sb-section-title">Three people touch every request</h2>

<p class="sb-lede sb-lede--small">Each sees what they need to do their part, and nobody sees a value they didn't ask for.</p>

<div class="sb-cards">
<div class="sb-card">
<svg class="sb-icon" viewBox="0 0 24 24" aria-hidden="true"><g fill="none" stroke="currentColor" stroke-width="1.75"><rect x="3.5" y="4" width="11" height="16"/><path d="M10 12H20.5M17 8.5L20.5 12L17 15.5"/></g></svg>
<h3>Developers ask</h3>
<p>Name the secret, the exact keys and why. Once it's approved, reveal each value once with your second factor. No value travels through chat or tickets.</p>
</div>
<div class="sb-card">
<svg class="sb-icon" viewBox="0 0 24 24" aria-hidden="true"><g fill="none" stroke="currentColor" stroke-width="1.75"><path d="M5 3.5V20.5"/><path d="M9.5 12.5L13 16L20 8"/></g></svg>
<h3>Approvers decide</h3>
<p>Approve or reject with who, what, where and why in front of you. Production is marked on every screen. Approving records a decision; it never shows you the value.</p>
</div>
<div class="sb-card">
<svg class="sb-icon" viewBox="0 0 24 24" aria-hidden="true"><g fill="none" stroke="currentColor" stroke-width="1.75"><path d="M3.5 11H20.5V20.5H3.5Z"/><path d="M12 16V3.5M8.5 7L12 3.5L15.5 7"/></g></svg>
<h3>Platform teams run it</h3>
<p>Keep Vault and AWS Secrets Manager as they are. Agents run in your clusters with their own credentials, and every step lands in an append-only audit log.</p>
</div>
</div>

</section>

<section class="sb-section sb-section--flow" aria-labelledby="sb-flow-title" markdown>

<h2 id="sb-flow-title" class="sb-section-title">Where your secrets go, and where they don't</h2>

<p class="sb-lede sb-lede--small">Values stay in your provider until an approved request needs them. Then they travel once, sealed, and only to the person who asked. Pick a step to follow it.</p>

--8<-- "includes/flow.html"

</section>

<section class="sb-section" aria-labelledby="sb-holds" markdown>

<h2 id="sb-holds" class="sb-section-title">What it holds to</h2>

<p class="sb-lede sb-lede--small">These are enforced in code, not left to policy. The <a href="overview/threat-model/">threat model</a> shows how each boundary is kept.</p>

<div class="sb-cards">
<div class="sb-card"><span class="sb-num">01</span><h3>No plaintext values in the control plane</h3><p>Not in Postgres, Redis, logs, audit events or the browser. In transit, values are KMS-wrapped.</p></div>
<div class="sb-card"><span class="sb-num">02</span><h3>The agent only calls out</h3><p>No inbound port, no database, no Kubernetes API access to Secrets.</p></div>
<div class="sb-card"><span class="sb-num">03</span><h3>Production never allows direct reveal</h3><p>The refusal is enforced in code and audited.</p></div>
<div class="sb-card"><span class="sb-num">04</span><h3>Values move once</h3><p>KMS-wrapped, single-use, short-lived, and opened only by the right person.</p></div>
<div class="sb-card"><span class="sb-num">05</span><h3>Audit is append-only and metadata-only</h3><p>Who, what, when and why, never the value.</p></div>
<div class="sb-card"><span class="sb-num">06</span><h3>Agents are bound and revocable</h3><p>One-time enrollment tokens, one provider connection per agent, revoked at once.</p></div>
</div>

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

<div class="sb-start" markdown>

<div markdown>

<h2 id="sb-start" class="sb-section-title">Start on your laptop</h2>

<p class="sb-lede sb-lede--small">The local guide starts Postgres and Redis from the api repo's compose file, which can also run the api in a container. The console and the agent run from their own repos, and the guide walks through the whole flow against a dev Vault.</p>

<div class="sb-actions" markdown>
[Run it locally](operations/docker-compose.md){ .md-button .md-button--primary }
[Operations guide](operations/index.md){ .md-button }
</div>

<p class="sb-note">Local development only. Never load real secrets into it.</p>

</div>

<div markdown>

<p class="sb-note sb-note--label">Step 1 of the local guide</p>

```bash
git clone https://github.com/secrets-bridge/api.git
cd api
docker compose up -d postgres redis
```

</div>

</div>

</section>

</div>
