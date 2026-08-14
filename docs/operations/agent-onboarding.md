---
title: Agent onboarding
description: How an agent is enrolled with a one-time token, receives a persistent identity once, heartbeats outbound, and can be revoked, no inbound ports, no cluster-API access.
---

# Agent onboarding

An agent runs **inside your boundary** (a Kubernetes cluster, a VPC, an account)
and talks **outbound only** to the control plane and its local provider. Onboarding
is **self-enrollment**: an admin issues a short-lived, one-time token; the agent
exchanges it for a persistent credential exactly once.

## The flow

```mermaid
sequenceDiagram
    autonumber
    participant Admin
    participant CP as Control Plane
    participant Agent
    Admin->>CP: Create one-time enrollment token<br/>(bound to a provider connection)
    CP-->>Admin: enrollment_token (returned once, hash-only at rest)
    Admin->>Agent: deliver enrollment_token (via a Secret)
    Agent->>CP: POST /agents/enroll { enrollment_token, ... }
    CP-->>Agent: agent_token (returned ONCE) + agent_id
    Note over Agent: persist {agent_id, agent_token} safely;<br/>token is spent, never reused
    loop heartbeat
        Agent->>CP: POST /agents/:id/heartbeat (X-Agent-Secret)
        CP-->>Agent: 200 { next_heartbeat_seconds }
    end
    Admin->>CP: Revoke agent (when needed)
    CP-->>Agent: subsequent heartbeats / job polls rejected
```

## What happens, step by step

1. **Admin creates a one-time enrollment token**, bound to a specific provider
   connection. The token is short-lived, stored **hash-only**, and returned
   exactly once.
2. **The agent calls `POST /agents/enroll`** with the token (the token travels in
   the request body, never a header, never a log line).
3. **The control plane returns a persistent `agent_token` once** and creates the
   agent, bound to that provider connection.
4. **The agent stores its identity safely** and, on restart, reuses it, it never
   spends a second enrollment token.
5. **The agent heartbeats** using the `X-Agent-Secret` header; the control plane
   drives the cadence.
6. **An admin can revoke the agent** at any time; its heartbeats and job polling
   stop being accepted immediately.

## Safety properties

- **One-time tokens**, hash-only at rest, short TTL, returned once, consumed
  once. Reuse is refused (`409`).
- **Provider-bound**, an enrolled agent is tied to a single provider connection.
- **Outbound-only**, no inbound ports; no Postgres / Redis / Kubernetes-API
  dependency.
- **Metadata-only audit**, enrollment, rejection, and revocation events record
  IDs, reasons, and timestamps; never the token or the agent credential.
- **Legacy direct mint is disabled by default**, the older direct
  agent-mint endpoint is off unless explicitly enabled as a break-glass admin
  action; enrollment is the standard path.

!!! warning "Never expose credential material"
    Enrollment tokens and agent credentials are secrets. Deliver them through a
    Kubernetes Secret (or your secret-distribution mechanism), never as a
    plaintext value in configuration, a log line, a screenshot, or a commit.

See the [agent component reference](../components/agent.md) and the
[HTTP API endpoints](../reference/api-endpoints.md#agents) for the exact contract.
