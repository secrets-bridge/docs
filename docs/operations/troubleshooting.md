# Troubleshooting

## Common failure modes

### "Failed to load …" on every page

Likely the api isn't reachable. Check:

```bash
curl -fsS http://localhost:18080/readyz
```

If 503, the api can see Postgres or Redis but one of them isn't
ready — the response body lists which:

```json
{"status":"unready","checks":{"postgres":"ping failed: dial tcp ..."}}
```

### Login returns 401 with a valid password

Check the audit log:

```bash
TOKEN=...  # need an admin token from another session
curl -fsS "http://localhost:18080/api/v1/audit-events?action=auth.login" \
  -H "Authorization: Bearer $TOKEN" \
  | jq '.[] | select(.status=="denied")'
```

The `metadata.error_kind` tells you what's wrong:

| `error_kind` | Meaning |
|---|---|
| `user_not_found` | Email doesn't exist (case-insensitive). Check `SB_BOOTSTRAP_ADMIN_EMAIL` |
| `wrong_password` | Password mismatch |
| `user_disabled` | `local_users.disabled = TRUE` |
| `missing_fields` | Body shape wrong |

### Agent job fails immediately ("agent reported failure")

Read the agent's log:

```bash
docker logs secrets-bridge-agent-1 | grep -iE "job|error|fail" | tail
```

The most common cause is **provider config missing**. For Vault:
leave the Provider config field blank in the Submit drawer (the UI
defaults to `kvMount=secret`). For AWS Secrets Manager: the
`region` is required.

For a deeper trace, set the agent's log level to debug:

```bash
SB_LOG_LEVEL=debug docker compose up -d agent
```

### "Wraps card shows 'No wraps issued yet'" after the agent ran

Two possibilities:

1. **You're signed in as the wrong user.** The Wraps card only
   fetches when the viewer is the requester. Sign in as the user
   who submitted the request.
2. **The agent failed before posting the wrap.** Check
   `GET /audit-events?correlation_id=<request-uuid>` for the full
   chain — you should see `wrap.create` events on success.

### "Failed to load audit events"

Likely `audit.read` permission missing. The seed admin role has
it; if you're a different user, an admin needs to grant you the
`audit.read` permission via a role.

```bash
# As admin:
curl -fsS http://localhost:18080/api/v1/audit-events \
  -H "Authorization: Bearer $TOKEN"
```

Expected: 200 with an array. If 403, your role doesn't carry
`audit.read`.

### Agent stays "stale" forever

Two things to check:

1. **The agent's heartbeat is reaching the CP.** From the agent's
   network, run:
   ```bash
   docker exec secrets-bridge-agent-1 wget -qO- http://api:8080/healthz
   ```
2. **The agent secret is correct.** A wrong secret returns 401 on
   heartbeat (generic message; the audit log records
   `error_kind=unauthorized`).

### Vault read returns "permission denied"

The agent uses the credentials in `SB_VAULT_TOKEN` or via the
configured Kubernetes auth role. Check that they have read access
to the secret path:

```bash
docker exec secrets-bridge-vault-1 sh -c \
  'VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN=devroot \
   vault kv get secret/<path>'
```

If that works but the agent gets denied, the agent token has less
scope than the dev token. Adjust the policy in Vault.

## Useful queries against the audit log

### Find every action for one request

```bash
curl -fsS "http://localhost:18080/api/v1/audit-events?correlation_id=<uuid>" \
  -H "Authorization: Bearer $TOKEN" | jq '.[] | {time:.occurred_at, actor, action, resource}'
```

### Find every login failure in the last hour

```bash
SINCE=$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)
curl -fsS "http://localhost:18080/api/v1/audit-events?action=auth.login&since=$SINCE" \
  -H "Authorization: Bearer $TOKEN" \
  | jq '.[] | select(.status=="denied")'
```

### Find every wrap retrieval (who saw which value when)

```bash
curl -fsS "http://localhost:18080/api/v1/audit-events?action=wrap.retrieve" \
  -H "Authorization: Bearer $TOKEN" \
  | jq '.[] | {time:.occurred_at, actor, resource, status}'
```

This is the SOC2-friendly query — every plaintext reveal across
the platform, append-only, with the actor and timestamp.

## Reading the metrics

The api and worker both expose Prometheus metrics at `/metrics`.
The interesting ones:

| Metric | What |
|---|---|
| `worker_scheduler_runs_total{task,outcome}` | Per-sweeper success / failure / skipped_lock counter |
| `worker_scheduler_run_duration_seconds{task}` | Sweeper latency histogram |
| `worker_scheduler_lock_skipped_total{task}` | Leader-election losses (expected for N-1 of N replicas) |

For HTTP-side latency, log-derived metrics are the source today;
a future PR adds explicit histograms.

## When in doubt

- Check the audit log first (`GET /audit-events`)
- Then the api logs (`docker logs secrets-bridge-api-1`)
- Then the agent logs (`docker logs secrets-bridge-agent-1`)
- Then Postgres (`docker exec -it secrets-bridge-postgres-1 psql -U secrets_bridge`)
- File an issue at
  [`secrets-bridge/.github`](https://github.com/secrets-bridge/.github)
  with the correlation_id and the audit chain
