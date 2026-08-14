---
title: Overview
description: How Secrets Bridge fits between developers, agents, and the actual secret providers, without ever holding raw values in the Control Plane.
---

# Overview

Secrets Bridge is a **secrets control plane**: the layer that sits
between developers / operators and the actual secret stores. The
mental model the project never violates:

```
Control Plane = decisions, workflow, metadata, audit, RBAC, jobs, status
Agent         = execution inside the target account/cluster, least privilege
Providers     = the actual secret values (source of truth)
```

The Control Plane never holds raw secret values. The Agent holds
them for the duration of one request and then drops them. The
Providers are unchanged. Secrets Bridge augments them, it doesn't
replace them.

## The flows the platform supports today

| Flow | Direction | What happens |
|---|---|---|
| **Read** | provider → user | Developer requests a value; workflow approves; agent fetches; CP stores a single-use KMS-wrapped envelope; UI reveals it once. |
| **Patch** | user → provider | Developer submits a new value through the form; workflow approves; agent GET-merge-PUTs to the provider so untouched keys survive. |
| **Discovery** | provider → CP catalog | Admin enqueues a discover job; agent calls `ListMetadata`; CP upserts to the `secrets` table with native provider labels preserved verbatim (Vault `custom_metadata`, AWS Tags, GCP labels, Azure tags). |
| **GitOps observation** (BRD §26) | ArgoCD → CP | After an approved patch reaches the provider, the worker polls ArgoCD to confirm whether the workload actually picked up the new value. Strictly read-only. Off by default. |

## What ships today

| Repo | Status | Notes |
|---|---|---|
| [`core`](../components/core.md) | Shipped | Provider interface, Vault + AWS SM connectors, type-safe value redaction |
| [`api`](../components/api.md) | Shipped | Fiber v3 Control Plane API, Postgres + Redis, RBAC catalog, JWT login |
| [`agent`](../components/agent.md) | Shipped | Outbound-only, claim → wrap → execute → complete loop, X25519 wire envelope |
| [`worker`](../components/worker.md) | Shipped | Sweepers, scheduler, notifications, GitOps poller |
| [`controller`](../components/controller.md) | Shipped | Kubernetes CRD reconciler ported from v0.1.0 |
| [`ui`](../components/ui.md) | Shipped | React SPA: dashboard, requests, agents, admin, audit, secrets |
| [`charts`](https://github.com/secrets-bridge/charts) | In progress | Helm bundle |
| [`docs`](https://github.com/secrets-bridge/docs) | You're reading it | mkdocs-material |

## What's intentionally out of scope

- **Replacing your secrets provider.** Vault, AWS SM, etc. stay
  authoritative. Secrets Bridge is a governance + access plane, not
  a value store.
- **Storing secret values.** The `secret_wraps` table holds
  KMS-encrypted envelopes for the duration of one request only
  (TTL in minutes/hours, single-shot consumption).
- **Writing K8s secrets from the CP.** The `controller` does
  GitOps-style sync; the CP itself never reaches into a cluster.
- **Providing a "central admin password" for every provider.** The
  agent uses **only** the credentials configured inside its own
  network boundary. The CP never holds provider master credentials.

## Next steps

- [The architecture in detail](architecture.md)
- [Threat model and the hard rules we never break](threat-model.md)
- [Try the local docker-compose stack](../operations/docker-compose.md)
