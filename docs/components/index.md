---
title: Components
description: Eight repositories, one product — what each repo holds, what it deliberately doesn't, and the one-way dependency graph that keeps the agent infra-free.
---

# Components

The project is split into eight repositories under the
[`secrets-bridge`](https://github.com/secrets-bridge) GitHub
organisation. Each one has a single responsibility; the dependency
direction is one-way and reviewable.

| Repo | Language | Holds |
|---|---|---|
| [`core`](core.md) | Go | Provider interface + connectors, shared types. **Infra-free: no Postgres, no Redis.** |
| [`api`](api.md) | Go (Fiber v3) | Control Plane API. Owns Postgres + Redis + the workflow/RBAC domain. |
| [`worker`](worker.md) | Go | Background sweepers, the GitOps observation poller, periodic discovery scheduler. |
| [`agent`](agent.md) | Go | Outbound-only execution agent. **No Postgres / Redis dependency.** |
| [`controller`](controller.md) | Go (kubebuilder) | Kubernetes CRD reconciler. Receives the v0.1.0 operator. |
| [`ui`](ui.md) | React + TS + Vite | SPA dashboard. No SSR. |
| `charts` | Helm / YAML | Deploy manifests for all components (in progress). |
| `docs` | mkdocs-material | This site. |

## Dependency graph

```mermaid
flowchart LR
    core["core<br/>provider interface +<br/>shared types"]
    api["api<br/>Postgres + Redis<br/>workflow + audit"]
    worker["worker<br/>sweepers + gitops"]
    agent["agent<br/>outbound only"]
    controller["controller<br/>K8s reconciler"]
    ui["ui<br/>React SPA"]
    charts["charts<br/>Helm bundle"]

    api -->|"imports"| core
    worker -->|"imports"| api
    worker -->|"imports via pkg"| core
    agent -->|"imports"| core
    agent -.->|"HTTPS only"| api
    controller -->|"imports"| core
    ui -.->|"HTTPS only"| api
    charts -.->|"deploys"| api
    charts -.->|"deploys"| worker
    charts -.->|"deploys"| agent
    charts -.->|"deploys"| controller
    charts -.->|"deploys"| ui
```

The forbidden edges:

- `agent` → `api/internal/storage` (would pull Postgres into the
  workload network)
- `agent` → `api/internal/runtime` (would pull Redis)
- `controller` → `api/pkg/storage` (same reasoning)
- `core` → anything that imports `database/sql` / `redis/*`

CI in each repo greps `go.sum` to enforce these directions; the
build fails if a forbidden module path appears.
