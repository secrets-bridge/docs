# Architecture

The platform splits into three loosely-coupled tiers and one
metadata index. Each tier holds one type of trust: the Control
Plane decides; the Agent executes; the Providers own the values.
An optional [Gateway](../components/gateway.md) observes: it runs next to
the workloads, reads Argo CD rollout state without changing anything, and
reports metadata to the Control Plane over its own outbound connection.
Release 1 of the Gateway is in progress; see
[Product status](product-status.md#in-progress).

```mermaid
flowchart LR
    subgraph user_plane ["User / Dev plane"]
        UI["UI SPA"]
        Dev["Developer"]
        Approver["Approver"]
        Dev --> UI
        Approver --> UI
    end

    subgraph control_plane ["Control Plane (Secrets Bridge)"]
        API["api (Fiber v3)"]
        Postgres[("Postgres<br/>append-only audit")]
        Redis[("Redis<br/>locks, cache,<br/>rate limit")]
        Worker["worker<br/>sweepers"]
        KMS["KMS backend<br/>local / vault-transit / aws-kms"]
    end

    subgraph workload ["Workload network (per cluster)"]
        Agent["agent<br/>outbound only"]
        Gateway["gateway (optional)<br/>outbound only, read-only"]
        ArgoCD["Argo CD"]
        Vault[("HashiCorp Vault")]
        AWSSM[("AWS Secrets Manager")]
        AzureKV[("Azure Key Vault")]
        GCPSM[("GCP Secret Manager")]
    end

    UI <--> API
    API <--> Postgres
    API <--> Redis
    API <--> KMS
    Worker <--> Postgres
    Worker <--> Redis
    Agent -->|"outbound HTTPS"| API
    Agent --> Vault
    Agent --> AWSSM
    Agent --> AzureKV
    Agent --> GCPSM
    Gateway -->|"outbound HTTPS"| API
    Gateway -->|"GET only"| ArgoCD
```

## Trust boundaries: what holds what

| Component | What it holds | What it must never hold |
|---|---|---|
| **UI** | Nothing that authenticates: the browser holds the HttpOnly `sb_session` cookie, which page scripts can't read | Any provider credential, any plaintext value beyond the reveal-once modal lifetime |
| **API** | KMS-wrapped envelopes (single-shot, TTL'd), audit rows, policy rules, role catalogs | Raw plaintext values, provider master credentials |
| **Postgres** | Hashes + envelopes + metadata + append-only audit | The decryption key, which lives in the KMS backend, *outside* Postgres |
| **Redis** | Idempotency tokens, distributed locks, rate-limit windows, pub/sub messages | Any value-bearing payload (the `runtime` package doesn't even expose a generic `Set()` ) |
| **Worker** | The same Postgres + Redis access as the API | Provider credentials, plaintext values |
| **Agent** | Provider credentials *for its own network boundary*, plaintext values for the duration of one request | Anything from another cluster / account; no inbound listener; no Postgres / Redis client |
| **Gateway** (optional) | Its own credential for the Control Plane and a read-only Argo CD token, both as read-only files in its own boundary | Secret values, provider credentials, Kubernetes RBAC on Secrets, any write access; no inbound listener except loopback health; no Postgres / Redis client; no path to the agent |
| **Providers** | The actual secret values | n/a (these are unchanged systems) |

## The four request lifecycles

=== "Read"

    ```mermaid
    sequenceDiagram
        participant Dev
        participant UI
        participant API
        participant Approver
        participant Agent
        participant Vault

        Dev->>UI: Submit read request<br/>(prod/db/password, justification)
        UI->>API: POST /requests/read
        API->>API: Resolve policy → workflow
        API-->>UI: status: pending
        Approver->>UI: Click Approve
        UI->>API: POST /requests/:id/approve
        API->>API: Enqueue read job
        API-->>UI: status: approved
        Agent->>API: POST /jobs/claim
        API-->>Agent: read job payload
        Agent->>Vault: GetValue prod/db/password
        Vault-->>Agent: bundle with DB_PASSWORD
        Agent->>API: POST /agents/:id/wraps<br/>(envelope-encrypted)
        Agent->>API: POST /jobs/:id/complete (succeeded)
        API-->>Agent: 204
        Dev->>UI: Click Reveal (one-time)
        UI->>API: GET /requests/:id/wraps/:wrap_id<br/>?user_id=dev
        API->>API: Atomic consume + KMS decrypt
        API-->>UI: plaintext (base64, single-shot)
        UI->>UI: Show in modal, clear on close
    ```

=== "Patch"

    ```mermaid
    sequenceDiagram
        participant Dev
        participant UI
        participant API
        participant Approver
        participant Agent
        participant Vault

        Dev->>UI: Submit patch request<br/>prod/db/password = new-value
        UI->>API: POST /requests with key_values
        API->>API: KMS-wrap each value<br/>resolve policy → workflow
        API-->>UI: status: pending
        Approver->>UI: Approve
        UI->>API: POST /requests/:id/approve
        API->>API: Enqueue patch job
        Agent->>API: POST /jobs/claim
        API-->>Agent: patch job +<br/>list of wrap ids
        loop For each wrap
            Agent->>API: GET /agents/:id/wraps/:wrap_id
            API->>API: KMS-decrypt + single-shot consume
            API-->>Agent: plaintext (envelope-sealed if<br/>agent has registered pubkey)
        end
        Agent->>Vault: GetValue(prod/db/password)
        Vault-->>Agent: existing bundle
        Agent->>Vault: PutValue (merged bundle)
        Agent->>API: POST /jobs/:id/complete (succeeded)
        API-->>UI: status: executed
    ```

=== "Discovery"

    ```mermaid
    sequenceDiagram
        participant Admin
        participant API
        participant Agent
        participant Vault

        Admin->>API: POST /jobs job_type=discover
        Agent->>API: POST /jobs/claim
        API-->>Agent: discover job payload
        Agent->>Vault: ListMetadata(scope)
        Vault-->>Agent: 47 secrets with<br/>custom_metadata tags
        Agent->>API: POST /agents/:id/secrets/bulk<br/>cluster + provider + items
        API->>API: Upsert on cluster+provider+ref<br/>preserve first_seen_at<br/>refresh labels jsonb
        Agent->>API: POST /jobs/:id/complete (succeeded)
        Admin->>API: GET /secrets?label=Environment:prod<br/>&label=Team:billing
        API-->>Admin: filtered list (GIN index)
    ```

=== "Gateway observation"

    The Control Plane never connects to Argo CD and holds no Argo CD
    credential. When a change reaches `executed` in an environment whose
    observation source is `gateway`, the api queues a task for each matching
    binding. A [Gateway](../components/gateway.md) inside your boundary
    claims it, reads Argo CD with its own read-only token, and posts the
    result. In an environment set to `none`, the default, nothing observes
    the change. `Healthy` and `Synced` are Argo CD operational state, not
    proof that the workload picked up the new value, so the verdict is at
    most `unverified`.

    ```mermaid
    sequenceDiagram
        participant API
        participant Gateway
        participant ArgoCD

        Note over API: Patch request transitions to executed
        API->>API: Queue one task per binding<br/>that covers this secret
        Gateway->>API: POST /gateways/:id/tasks/claim
        API-->>Gateway: task, attempt_id, lease, deadline
        Gateway->>ArgoCD: GET /api/v1/applications/:name<br/>GET-only transport
        ArgoCD-->>Gateway: sync, health, operation phase, revision
        Gateway->>API: POST /tasks/:task_id/result
        API->>API: Check attempt and binding<br/>recompute stage outcome and verdict
    ```

## Defense-in-depth on the wire

Three layers of encryption protect every value-bearing flow:

```
TLS (mandatory)              - passive sniffers, compromised system CA
  ↓
Wire envelope (Piece 8b)     - TLS-terminating proxies, CP-side log leaks
  ↓
Storage envelope (Piece 8a)  - DB exfiltration, offline backup theft
```

| Direction | Wire envelope scheme |
|---|---|
| **CP → Agent** | X25519 ECDH + HKDF-SHA256 + AES-256-GCM, sealed to the agent's registered public key. Even a TLS-terminating gateway sees only ciphertext. |
| **Agent → CP** | CP issues a KMS-wrapped data-encryption key; agent uses it for AES-256-GCM and zeroes the plaintext DEK immediately. The CP unwraps via the KMS backend. |
| **At rest** | KMS-envelope: per-row data key, wrapped by the configured `KeyManager` (LocalKMS for dev, Vault Transit or AWS KMS for production). |

## Why polyrepo

Nine repositories, one product. The `core` library is infra-free
(no Postgres driver, no Redis client, no Fiber import), so the
`agent` and `controller` can depend on it without pulling in
storage. The `api` and `worker` share Postgres/Redis but the worker
imports `api/pkg/*` only (never `internal/*`), so the dependency
direction is one-way and reviewable.

CI in every repo greps `go.sum` to enforce these boundaries. For
example, the agent's CI fails the build if it ever picks up
`jackc/pgx`, `lib/pq`, `redis/go-redis`, or similar drivers.

Read more: [REFACTOR_PLAN.md §4 polyrepo dependency graph](https://github.com/secrets-bridge/.github/blob/main/REFACTOR_PLAN.md).
