# Troubleshooting

## Common failure modes

### "Failed to load …" on every page

Likely the api isn't reachable. Check:

```bash
curl -fsS http://localhost:18080/readyz
```

If 503, the api can see Postgres or Redis but one of them isn't
ready, the response body lists which:

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

### Google sign-in refused

A refused Google sign-in always lands on `/login?error=sso` with "You
couldn't be signed in with that account.", whatever the reason, so the page
can't reveal which emails have accounts. An admin with `audit.read` finds
the reason in the audit log:

```bash
curl -fsS "http://localhost:18080/api/v1/audit-events?action=auth.sso.callback" \
  -H "Authorization: Bearer $TOKEN" \
  | jq '.[] | select(.status=="denied") | {time:.occurred_at, kind:.metadata.error_kind, purpose:.metadata.purpose}'
```

The browser isn't signed in yet, so these events have the actor
`anonymous` and no email. Match them to a person by time.

| `error_kind` | Meaning | Fix |
|---|---|---|
| `hd_not_allowed` | The ID token has no `hd` claim (a personal Google account) or a Workspace domain that isn't allowed | Use a Workspace account, or add its domain under Admin → Sign-in |
| `email_domain_not_allowed` | `hd` is allowed but the email's domain isn't | Add the email's domain too |
| `email_unverified` | Google didn't mark the email as verified | Verify it at Google |
| `email_has_account` | The email already belongs to an account here, which hasn't connected Google | The person signs in with their password and uses Connect Google on their profile |
| `account_disabled` | The account was declined or disabled | A declined account can't be re-enabled from the console |
| `provider_disabled` | Google is turned off, or `SB_OIDC_ISSUER` is Google | Turn it on, or use the env-var provider |
| `no_public_url` | No public address is set | Set `SB_PUBLIC_URL` or save one under Admin → Sign-in |
| `exchange_failed` | Google refused the code exchange, usually a wrong client ID or secret | Check the client in Google Cloud Console, replace the secret, run Test |
| `id_token_invalid`, `claims_invalid`, `nonce_mismatch`, `missing_sub` | Google's answer couldn't be verified | Check the client ID, then Test |
| `iat_invalid` | The ID token was too old or dated in the future | Check the api server's clock |
| `no_code` | The person cancelled at Google, or Google returned an error | Try again |
| `state_cookie`, `state_unknown`, `state_mismatch` | The round trip took longer than 5 minutes, or finished in another browser | Try again in one browser |

Two other events explain refusals that aren't in `auth.sso.callback`:

- **`user.pending_refused`**: the [waiting limit](google-sign-in.md#the-waiting-limit)
  was reached. Approve or decline waiting accounts, or raise the limit. The
  events are aggregated per 10-minute window, with `count`, `first` and
  `last`.
- **`sso_provider.default_role_refused`**: approval is off, but the default
  role now holds a privileged permission, so the account was created
  waiting for approval instead. Fix the role or pick another default.

**Test** runs the same checks and shows the reason to the admin who ran it,
which is the quickest way to check a setup.

### Google shows "redirect_uri_mismatch"

Google stops on its own error page and never comes back, so nothing is
audited. The redirect URI registered on the OAuth client must match the one
Secrets Bridge sends exactly:

```text
https://secrets.example.com/api/v1/auth/sso/google/callback
```

Copy it from **Admin → Sign-in → Google → Redirect URL**, and add it under
**Authorized redirect URIs** in Google Cloud Console. The scheme, host,
port and path must all match. If you change the public address, update the
redirect URI at Google too.

### No "Sign in with Google" button, or Turn on fails

- **No public address.** The login page doesn't offer Google while neither
  `SB_PUBLIC_URL` nor a saved address is set, and Turn on answers
  `409 provider_not_ready` with `missing: ["public_url"]`. Set one of them.
- **Missing secret or domains.** `missing` also lists `client_secret` or
  `allowed_domains`.
- **The env-var provider is Google.** With `SB_OIDC_ISSUER` set to
  `https://accounts.google.com`, the console provider is never offered
  (`409 env_provider_is_google`). Use one or the other.
- **The api won't start** after setting `SB_PUBLIC_URL`: the value is
  invalid. It must be `https`, with no user info, query or fragment, and
  plain `http` only for `localhost` with `SB_ENV=dev`.

### Agent job fails immediately ("agent reported failure")

Read the agent's log:

```bash
docker logs secrets-bridge-agent-1 | grep -iE "job|error|fail" | tail
```

The most common cause is **agent provider settings**. For Vault:
the agent's `SB_VAULT_KV_MOUNT` (default `kv`) has to match the
provider connection's `mount`, otherwise the job fails with a
`kvMount` error. For AWS Secrets Manager: the agent needs
`SB_AWS_REGION`.

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
   chain, you should see `wrap.create` events on success.

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

This is the SOC2-friendly query, every plaintext reveal across
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
