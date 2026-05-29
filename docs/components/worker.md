# Worker

Repo: [`secrets-bridge/worker`](https://github.com/secrets-bridge/worker)
· Stack: Go 1.25 + `api/pkg/storage` + `api/pkg/runtime` (via local
`replace` directive) + Prometheus client
· Container: `golang:1.25-alpine` → `distroless/static:nonroot`

Background workhorse for the platform's lifecycle hygiene + the
read-only ArgoCD observation poller (BRD §26).

## Sweepers shipped today

| Name | Cadence | Job |
|---|---|---|
| `wraps-expired` | 60s | Delete `secret_wraps` past `expires_at` |
| `secrets-stale` | 5m | Flip discovered `secrets` rows whose `last_seen_at < cutoff` to `status='missing'` |
| `agents-stale` | 60s | Flip agents whose `last_seen_at < cutoff` to `status='stale'` |
| `jobs-recovery` | 30s | Mark `sync_jobs` rows whose claim lease expired without a complete as `status='expired'` |
| `discover-scheduler` | 5m | Enqueue one discover job per configured target (env var today; admin API tracked) |
| `gitops-poller` | 15s | Claim a queued observation → call ArgoCD → record `observed_state` → transition |
| `gitops-timeout` | 60s | Flip observations past their `timeout_at` to `applied_unverified` |

## Multi-replica safety

Every sweeper acquires a Redis lock before running:

```go
lock := scheduler.AcquireLock("worker:sweeper:" + name)
if errors.Is(err, runtime.ErrLockHeld) { /* metric, return */ }
// run + StartRenewal + Release on tick end
```

So you can scale the worker deployment to N replicas; exactly one
runs each sweeper per tick, the others record `worker_scheduler_lock_skipped_total`
(a metric, not a warn-level log — N-1 of N replicas always skip).

## Notification sinks

| Sink | Status | Notes |
|---|---|---|
| `NoOp` | default | Logs at the event's severity |
| `Webhook` | ships | JSON POST; `FormatSlack=true` switches to `{text: ...}` envelope. 4xx is permanent (no retry); 5xx is transient (with backoff). |
| `Fanout` | ships | `errors.Join` across N sinks; one bad sink doesn't block siblings |
| Native Slack | placeholder | Tracked as a follow-up |
| Email / SMTP | placeholder | |
| PagerDuty | placeholder | |

## Hard rules

- Stateless (NFR-08) — all state in Postgres + Redis
- No secret values logged or notified — sweeper errors carry
  counts + cutoffs + sweeper names, never row contents
- No provider SDKs imported (worker doesn't fetch values; the
  agent does)
- Multi-replica safe by construction
- Fails loud on misconfig at boot (e.g. `SB_DISCOVER_TARGETS_JSON`
  parse error → exit 1)

## Configuration

| Env var | Required | Default | Notes |
|---|---|---|---|
| `DATABASE_URL` | yes | — | Same Postgres as the api |
| `REDIS_URL` | yes | — | Same Redis as the api |
| `SB_WORKER_GITOPS_ENABLED` | no | `false` | Must match the api's `SB_GITOPS_ENABLED` for §26 to be active |
| `SB_DISCOVER_TARGETS_JSON` | no | — | Array of `{agent_id, provider, config, scope}`; admin API replaces this |
| Sweeper interval overrides | no | per-sweeper defaults | `SB_SWEEP_WRAPS_INTERVAL`, etc. |
