Open source · pre-1.0

# Govern who uses your secrets.

Secrets Bridge adds access requests, approvals, audit and agent execution
around the secrets you already keep in AWS Secrets Manager and HashiCorp
Vault. We keep requests, approvals and audit metadata. Your secret values
stay in your provider.

[Run it locally](operations/docker-compose.md)
[Read the architecture](overview/architecture.md)
Source on GitHub

See what is live today and what is still on the roadmap.

## We keep

- Requests, and who approved them
- The audit trail: who, what, when and why
- Which secret paths and key names a project may use

## We never keep

- Secret values in plain text. In transit a value exists only as an encrypted, single-use wrap with a short lifetime.
- Provider credentials. The agent uses its own, inside your infrastructure.

The agent runs inside your infrastructure and only calls out, so you open no inbound port.

## Three people touch every request

Each sees what they need to do their part, and nobody sees a value they didn't ask for.

<rect x="3.5" y="4" width="11" height="16"/>
### Developers ask
Name the secret, the exact keys and why. Once it's approved, reveal each value once with your second factor. No value travels through chat or tickets.

### Approvers decide
Approve or reject with who, what, where and why in front of you. Production is marked on every screen. Approving records a decision; it never shows you the value.

### Platform teams run it
Keep Vault and AWS Secrets Manager as they are. Agents run in your clusters with their own credentials, and every step lands in an append-only audit log.

## Where your secrets go, and where they don't

Values stay in your provider until an approved request needs them. Then they travel once, sealed, and only to the person who asked. Pick a step to follow it.

## What it holds to

These are enforced in code, not left to policy. The threat model shows how each boundary is kept.

01### No plaintext values in the control planeNot in Postgres, Redis, logs, audit events or the browser. In transit, values are KMS-wrapped.
02### The agent only calls outNo inbound port, no database, no Kubernetes API access to Secrets.
03### Production never allows direct revealThe refusal is enforced in code and audited.
04### Values move onceKMS-wrapped, single-use, short-lived, and opened only by the right person.
05### Audit is append-only and metadata-onlyWho, what, when and why, never the value.
06### Agents are bound and revocableOne-time enrollment tokens, one provider connection per agent, revoked at once.

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

The local guide starts Postgres and Redis from the api repo's compose file, which can also run the api in a container. The console and the agent run from their own repos, and the guide walks through the whole flow against a dev Vault.

[Run it locally](operations/docker-compose.md)
[Operations guide](operations/index.md)

Local development only. Never load real secrets into it.

Step 1 of the local guide

```bash
git clone https://github.com/secrets-bridge/api.git
cd api
docker compose up -d postgres redis
```
