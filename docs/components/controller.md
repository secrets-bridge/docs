# Controller

Repo: [`secrets-bridge/controller`](https://github.com/secrets-bridge/controller)
· Stack: Go 1.26 + [controller-runtime](https://sigs.k8s.io/controller-runtime)
· Container: `golang:1.26-alpine` → `distroless/static:nonroot`

The Kubernetes operator. Receives the v0.1.0 CRD reconciler and is
the GitOps consumer for cluster-internal sync.

## What ships

- `api/v1alpha1` group with the `SecretsSync` CRD (ported verbatim
  from v0.1.0; only the module-path import changed)
- The reconciler validates the CR by calling
  `Providers.Build()` for both refs and reports `Ready=Validated`
  / `Ready=ProviderError`. It does **not** run the sync loop
  itself
- Provider registry injected on the Reconciler struct (matches the
  `Register(r)` pattern in `core/providers/*`)

## Key behavioural change from v0.1.0

The v0.1.0 reconciler embedded the sync engine. The new
architecture moves execution to the **agent** (BRD §12.4):

| What the new reconciler does | What it deliberately doesn't |
|---|---|
| Loads the CR | Run a `for name in source` loop |
| Validates refs via `Providers.Build()` | Skip-if-unchanged content-hash comparison |
| Sets `Ready=Validated` on success | Read `GetValue` from any provider |
| Sets `Ready=ProviderError` with the factory's text | Write `PutValue` to any provider |
| Re-queues every `spec.refreshInterval` | Delete orphans |

The sync work is dispatched to the agent via the CP's job queue.
The controller is a **GitOps gate** for the cluster, not the
executor.

## Configuration

| Env var | Required | Default | Notes |
|---|---|---|---|
| `KUBECONFIG` | for out-of-cluster runs | - | In-cluster uses the projected SA token |
| `LEADER_ELECTION_NAMESPACE` | no | the controller's own namespace | |
| `METRICS_ADDR` | no | `:8080` | Prometheus exposition |

See the controller's `config/` kustomize tree for the CRD + RBAC +
sample CR.
