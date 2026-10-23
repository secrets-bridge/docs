# Frequently asked questions

Short answers to common questions about Secrets Bridge. Each answer links to
the page with the full detail.

## What is Secrets Bridge?

Secrets Bridge is a secrets control plane. It governs who may use the secrets
your team already keeps in AWS Secrets Manager or HashiCorp Vault, and adds
access requests, approval workflows, RBAC, audit and agent execution around
them. The control plane makes decisions and keeps metadata, an agent inside
your boundary executes, and the provider holds the values. See the
[Overview](index.md) and the [Architecture](architecture.md).

## Does Secrets Bridge store secret values?

No. The control plane keeps requests, approvals and audit metadata, and the
values stay in your provider. A value in flight exists only as a
KMS-encrypted wrap that is consumed once and has a short TTL. Values never
appear in Redis, audit metadata, control-plane logs or browser storage, and
request responses carry key names only. The one response that returns a
value is the reveal itself, once, to the person who asked. See the
[Threat model & hard rules](threat-model.md) and
[Product status](product-status.md).

## Does it replace HashiCorp Vault or AWS Secrets Manager?

No. Your provider stays the source of truth for secret values, and Secrets
Bridge governs access, approvals, audit and agent execution around it. The
agent uses only the credentials configured inside its own network boundary,
and the control plane never holds provider master credentials. See
[What's intentionally out of scope](index.md#whats-intentionally-out-of-scope).

## Which secret providers does it support?

HashiCorp Vault (KV v2, with token or Kubernetes auth) and AWS Secrets Manager
(the standard AWS SDK credential chain, such as IRSA or an instance role) work
today through the agent. Azure Key Vault and GCP Secret Manager are on the
roadmap: their agent resolvers are placeholders, as is the Kubernetes Secret
resolver. See [Providers supported](../reference/providers.md) and
[Product status](product-status.md).

## Does the agent need an inbound port?

No. The agent only opens outbound connections, to the control plane and to
its local provider, and has no Postgres, Redis or Kubernetes API access to
Secrets. Its only listener serves `/healthz`, `/readyz` and `/metrics`; the
`agent` Helm chart binds it on the pod IP for kubelet probes, creates no
Service for it and denies all ingress with its default NetworkPolicy. See the
[Agent](../components/agent.md) page and
[Network posture](threat-model.md#network-posture).

## How does an agent get its credentials?

An admin creates a one-time enrollment token bound to one provider
connection. The token is short-lived, stored only as a hash and returned
once; the agent exchanges it at `POST /api/v1/agents/enroll` for a persistent
identity that it stores and reuses on restart. An admin can revoke the agent
at any time, and its heartbeats and job polls stop being accepted
immediately. See [Agent onboarding](../operations/agent-onboarding.md).

## How do approvals work?

When you submit a request, the policy rules are matched in priority order and
the first match picks a workflow. The workflow sets the approval ceremony:
the minimum number of approvers, whether a justification is required, and the
TTLs. Approvers with `secret.approve` approve or reject from the Requests
page, which needs a fresh second factor, and a requester can never approve
their own request (the api answers `403 separation_of_duties_violated` and
audits the attempt). See [Policy templates](../operations/policy-templates.md),
the [Glossary](glossary.md#workflow) and
[Bootstrap & first sign-in](../operations/bootstrap.md#submitting-your-first-read-request).

## Can a secret be revealed directly in production?

No. Direct reveal needs the caller to hold `secret.reveal.direct`, a matched
policy rule with `direct_reveal_allowed=true`, and an environment whose `kind`
is `non_prod`. The PolicyEngine zeroes `direct_reveal_allowed` for `prod`
environments whatever the policy says, and the refusal is audited. See
[Project environments](../operations/project-environments.md) and
[Direct reveal permission](../operations/authentication.md#direct-reveal-permission-slice-l4).

## How is a secret value delivered to the person who asked for it?

After approval, the agent claims the read job, fetches the value from the
provider and posts it to the control plane as an encrypted wrap, one per key.
When you click Reveal, the api consumes the wrap atomically and decrypts it
with the KMS backend, so a second fetch of the same wrap gets `410 Gone`. The console shows the
value once and clears it when the reveal closes; a
[reveal session](../operations/reveal-sessions.md) also ends after a TTL of 10
to 300 seconds set by the matched policy rule. See the read flow in the
[Architecture](architecture.md).

## What is a cross-team request?

It is a value handoff between two teams that don't share access to each
other's secrets. Team A submits the request, a Team B member with
`secret.value.provide` fills in the values, a Team A approver (and a security
approver when the workflow requires one) verifies, and the agent writes the
value into Team A's provider. No user can play more than one of these roles on
the same request. See [Cross-team requests](../operations/cross-team-requests.md).

## What is audited?

Audit events record actions, IDs, statuses, reasons and timestamps, and a
correlation ID links every event in one request's lifecycle. They never carry
plaintext values, tokens or wrap bodies. The `audit_events` table is
append-only: Postgres triggers reject UPDATE and DELETE. See the
[Glossary](glossary.md#audit_event) and
[Append-only audit](threat-model.md#append-only-audit).

## Does it support SSO, OIDC and MFA?

Yes. You can sign in through an OIDC provider set with the `SB_OIDC_*`
variables (PKCE, group-claim to role mapping, back-channel logout), through
Google configured from the console (merged, not yet through QA), or with a
local password kept as break-glass. MFA uses TOTP authenticator apps or
WebAuthn security keys: approve, reject and reveal need a fresh second
factor, and login-time MFA is on by default outside `SB_ENV=dev`. See
[Authentication](../operations/authentication.md) and
[OIDC with Authentik](../operations/oidc-authentik.md).

## How do I try it locally?

Clone the `api` repo, start Postgres and Redis with
`docker compose up -d postgres redis`, and run the api with `SB_ENV=dev` and
the `local` KMS backend; the UI runs from the `ui` repo with `npm run dev`. On first boot
against an empty database the api seeds three dev users and logs their
passwords once, and the guide then enrolls an agent against a HashiCorp Vault
dev server. The setup uses dev-only switches, so keep it on your machine and
never load real secrets into it. See
[Running locally with docker compose](../operations/docker-compose.md).

## How do I deploy it in production?

Install the Helm charts published on GHCR: `secrets-bridge` for the api, ui,
worker and controller, and `secrets-bridge-agent` for one agent per workload
cluster or account. You provide Postgres and Redis on a private network, a
real KMS backend (`vault-transit` or `aws-kms`) and an ingress with TLS. The
chart refuses `kms.backend=local` with `env=production`, and
[Operations](../operations/index.md) has the hardening checklist to work
through before you expose the install.

## How mature is it?

Secrets Bridge is open source and pre-1.0, and the first release has not been
tagged yet. [Product status](product-status.md) keeps what is implemented,
what is QA-certified (such as project access, direct reveal with TTL, prod
reveal refusal and the cross-team flow), what is in progress and what is on
the roadmap apart. Features listed as in progress, such as the Gateway and
Google sign-in, have not passed QA.
