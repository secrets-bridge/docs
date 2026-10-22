---
description: "The Secrets Bridge worker: sweepers for expired wraps, stale agents, stuck jobs and Gateway tasks, Redis locks for multiple replicas, and webhook sinks."
---

# Worker

Repo: [`secrets-bridge/worker`](https://github.com/secrets-bridge/worker)
· Stack: Go 1.25 + `api/pkg/storage` + `api/pkg/runtime` (via local
`replace` directive) + Prometheus client
· Container: `golang:1.25-alpine` → `distroless/static:nonroot`

Background workhorse for the platform's lifecycle hygiene and the Gateway
observation sweepers. The worker never talks to Argo CD and holds no KMS
access; Argo CD state comes only from a [Gateway](gateway.md).

## Sweepers shipped today

| Name | Cadence | Job |
|---|---|---|
| `wraps-expired` | 60s | Delete `secret_wraps` past `expires_at` |
| `secrets-stale` | 5m | Flip discovered `secrets` rows whose `last_seen_at < cutoff` to `status='missing'` |
| `agents-stale` | 60s | Flip agents whose `last_seen_at < cutoff` to `status='stale'` |
| `jobs-recovery` | 30s | Mark `sync_jobs` rows whose claim lease expired without a complete as `status='expired'` |
| `discover-scheduler` | 5m | Enqueue one discover job per configured target (env var today; admin API tracked) |
| `observation-leases` | 30s | Put Gateway observation tasks whose lease ran out back to `queued`. Opt-in with `SB_WORKER_GATEWAY_SWEEPERS_ENABLED` |
| `observation-deadlines` | 30s | Close open observation tasks past their deadline as `timed_out` (`deadline_reached` or `gateway_unavailable`), never failed. Opt-in |
| `gateways-stale` | 1m | Flip Gateways with no heartbeat for `SB_WORKER_GATEWAYS_STALE_AFTER` (2m) from `active` to `stale`. Opt-in |
| `gateway-replicas-prune` | 1h | Delete Gateway replica rows not seen for 24h. Opt-in |
| `users-pending` | 1m | Post one webhook message about accounts newly [waiting for approval](../operations/google-sign-in.md#notify-admins-from-the-worker), by email only. Registered only when `SB_WORKER_WEBHOOK_URL` is set |

## Multi-replica safety

Every sweeper acquires a Redis lock before running:

```go
lock := scheduler.AcquireLock("worker:sweeper:" + name)
if errors.Is(err, runtime.ErrLockHeld) { /* metric, return */ }
// run + StartRenewal + Release on tick end
```

So you can scale the worker deployment to N replicas; exactly one
runs each sweeper per tick, the others record `worker_scheduler_lock_skipped_total`
(a metric, not a warn-level log, because N-1 of N replicas always skip).

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

- Stateless (NFR-08): all state in Postgres + Redis
- No secret values logged or notified. Sweeper errors carry
  counts + cutoffs + sweeper names, never row contents. The one
  exception is `users-pending`, whose message lists the emails of
  waiting accounts. It goes to the webhook only, and the worker logs
  counts only
- No provider SDKs imported (worker doesn't fetch values; the
  agent does)
- No Argo CD client and no KMS backend. The `internal/archguard` test fails
  the build if non-test code imports a package path containing `argocd`,
  `argoproj` or `argo-cd`, or builds an Argo CD API path
- Multi-replica safe by construction
- Fails loud on misconfig at boot (e.g. `SB_DISCOVER_TARGETS_JSON`
  parse error → exit 1)

## Configuration

| Env var | Required | Default | Notes |
|---|---|---|---|
| `DATABASE_URL` | yes | - | Same Postgres as the api |
| `REDIS_URL` | yes | - | Same Redis as the api |
| `SB_WORKER_GATEWAY_SWEEPERS_ENABLED` | no | `false` | Turns on the four Gateway observation sweepers. Their intervals are in the [Configuration reference](../operations/config.md#worker) |
| `SB_DISCOVER_TARGETS_JSON` | no | - | Array of `{agent_id, provider, config, scope}`; admin API replaces this |
| Sweeper interval overrides | no | per-sweeper defaults | `SB_WORKER_WRAPS_EXPIRED_INTERVAL`, etc. See [Configuration reference](../operations/config.md#worker) |

The `SB_WORKER_GITOPS_*` settings are retired: if set, the worker logs their
names once at startup and ignores them. See
[Retired settings](../operations/config.md#retired-settings).
