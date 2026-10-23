# Govern who uses your secrets.

Secrets Bridge adds access requests, approvals, audit and agent execution
around the secrets you already keep in AWS Secrets Manager and HashiCorp
Vault. We keep requests, approvals and audit metadata. Your secret values
stay in your provider.

[Run it locally](operations/docker-compose.md)
[Read the architecture](overview/architecture.md)
Source on GitHub

Open source and pre-1.0. See what is live today and what is still on the roadmap.

## We keep

- Requests, and who approved them
- The audit trail: who, what, when and why
- Which secret paths and key names a project may use

## We never keep

- Secret values in plain text. In transit a value exists only as an encrypted, single-use wrap with a short lifetime.
- Provider credentials. The agent uses its own, inside your infrastructure.

The agent runs inside your infrastructure and only calls out, so you open no inbound port.

## Where your secrets go, and where they don't

Values stay in your provider until an approved request needs them. Then they travel once, sealed, and only to the person who asked. Pick a step to follow it.

## What it holds to
These are enforced in code, not left to policy. The threat model shows how each boundary is kept.

- No plaintext values in the control plane. Not in Postgres, Redis, logs, audit events or the browser. In transit, values are KMS-wrapped.
- The agent only calls out. No inbound port, no database, no Kubernetes API access to Secrets.
- Production never allows direct reveal. The refusal is enforced in code and audited.
- Values move once. KMS-wrapped, single-use, short-lived, and opened only by the right person.
- Audit is append-only and metadata-only. Who, what, when and why, never the value.
- Agents are bound and revocable. One-time enrollment tokens, one provider connection per agent, revoked at once.

## What works today

### Implemented

- AWS Secrets Manager and HashiCorp Vault through the agent
- Read requests with policy-driven approval
- Direct reveal in non-production, behind a second factor
- Cross-team requests: another team supplies the values
- Agent enrollment, status and revoke
- Append-only audit trail

### Roadmap

- Azure Key Vault and GCP Secret Manager providers
- Deeper Kubernetes External Secrets integration
- Flux integration
- Agents that claim only their own connection's jobs

Not shipped. Don't plan around these yet.

Full product status, with what is QA-certified and what is in progress.

## Start on your laptop

The api repo's compose file starts Postgres, Redis and the control plane; the console and the agent run from their own repos. The local guide walks through the whole flow against a dev Vault.

[Run it locally](operations/docker-compose.md)
[Operations guide](operations/index.md)
