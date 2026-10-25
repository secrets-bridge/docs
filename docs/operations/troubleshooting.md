---
description: "Fix common Secrets Bridge problems: login 401s, Google sign-in, failed agent jobs, stale agents, Vault permission errors, Gateway issues and audit queries."
---

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
JAR=...  # a cookie jar from an admin sign-in (see Bootstrap: curl -c "$JAR" on /auth/login)
curl -fsS "http://localhost:18080/api/v1/audit-events?action=auth.login" \
  -b "$JAR" \
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
  -b "$JAR" \
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
  -b "$JAR"
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
   `error_kind=unauthorized`). A revoked agent gets the same answer.
3. **The key matches.** A `409 agent_key_mismatch` on every heartbeat
   means the loaded key isn't the bound one; see
   [Requests fail with `409 agent_key_mismatch`](#requests-fail-with-409-agent_key_mismatch).

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

## Agent

Onboarding steps are in [Agent onboarding](agent-onboarding.md). Start with the
pod log (`kubectl -n secrets-bridge logs deploy/secrets-bridge-agent`) and the
audit log, which records why a request was refused (`error_kind`) without the
token, secret or key.

### The agent exits at start: a credential file is missing

The agent reads `agent_id`, `agent_secret` and `private_key` from
`SB_AGENT_CREDENTIALS_DIR` (`/etc/secrets-bridge/agent` in the chart) and stops
before it contacts the control plane when one is missing, empty or malformed.
`private_key` must be the base64 of exactly 32 bytes.

- `kubectl -n secrets-bridge get secret secrets-bridge-agent` must exist in the
  release namespace. A pod whose Secret doesn't exist stays in
  `ContainerCreating`; `kubectl describe pod` shows the mount error.
- The Secret must have the three keys. List the key names, not the values:
  `kubectl -n secrets-bridge get secret secrets-bridge-agent-identity -o jsonpath='{.data}' | jq 'keys'`.
  When your store uses other names, set `identity.keys.agentId`,
  `identity.keys.agentSecret` and `identity.keys.privateKey`.
- With ESO, check the `ExternalSecret` status
  (`kubectl -n secrets-bridge get externalsecret`). A `SecretSyncedError` means
  ESO couldn't read the store entry, usually a missing `GetSecretValue` or Vault
  `read` grant, or a property name that doesn't match the bundle.

### The agent refuses its credential files as too open

The agent refuses a credential file with group write or any permission for
others (`mode & 0o037 != 0`), checked on the file the symlink resolves to.
Owner and group read (`0440`) is accepted.

The `agent` chart mounts the Secret with `defaultMode: 0400` and requires
`podSecurityContext.fsGroup`; kubelet shows the files as `0440 root:<fsGroup>`,
which passes. A mount that is wider than that usually comes from a pod spec
patched outside the chart (a different `defaultMode`, or a projected volume
with its own mode). Without `fsGroup` the files stay `0400 root:root`, and the
non-root agent can't read them at all: that shows up as a permission error, not
as too open. Outside Kubernetes, `chmod 0400` (or `0600`) the files.

### Requests fail with `409 agent_key_mismatch`

The fingerprint of the key the agent loaded doesn't match the key bound to the
agent on the control plane. The audit log has `agent.key.mismatch`, rate limited
to one event per agent per minute.

- After a [key rotation](agent-onboarding.md#rotate-the-wire-key) the running
  pod still has the old key. Check that the Kubernetes Secret has the new
  `private_key` (ESO synced it), then `kubectl rollout restart` the Deployment.
- The Secret holds another agent's `private_key`, or the bundle from an
  enrollment that was later replaced. Compare the `public_key_fingerprint`
  stored with the bundle (or printed by `enroll` or `rotate-key`) with the one
  the console shows for the agent. If they differ and no rotation is open, write the right bundle to the store, or revoke the agent and
  enroll again.

### Enrollment is refused

`secrets-bridge-agent enroll` gets a generic error, and the audit log
(`agent.enroll` with `denied`) has the reason:

- `401 enrollment_rejected`: the token is wrong, expired, already used or
  revoked, or the challenge didn't match. Tokens expire after 15 minutes by
  default and work once. Create a new one.
- `401 enrollment_rejected` with the right token: `--cluster-name` or
  `--provider-type` doesn't match the token's expected values.
- `400 invalid_public_key`: the key isn't 32 bytes of base64 for `x25519`, or
  is a refused value (all zero or a low-order point). The CLI generates a valid
  key, so this points at a modified client.
- `400 unsupported_schema_version`: the CLI is older than the control plane's
  enrollment API. Use the `secrets-bridge-agent` release that matches the
  control plane.
- `429`: too many attempts. Wait and retry.

When `enroll` reached the control plane but the write to your secret store
failed, the token is spent and the bundle is gone. Revoke the new agent and
enroll again with a new token.

## Gateway

Install steps are in [Gateway](gateway.md). Start with the pod log
(`kubectl -n tenant-a-uat logs deploy/secrets-bridge-gateway`) and the detail
view (`GET /api/v1/admin/gateways/<id>`), which shows each replica's last
heartbeat and each connector's health.

### Gateway pod is not ready, or exits at boot

Check the log for the first error:

- `identity: ... has mode ...`: the identity file can be read by other
  users or written by its group. The Gateway accepts `0400`, `0600` or `0440`.
  The chart mounts the Secret with mode `0440` and `fsGroup`; a hand-written
  manifest with `defaultMode: 0444` is refused. Fix the mode, and rotate the
  Gateway secret (revoke, create, enroll) if other users could read it.
- `identity: ... does not exist`: the Secret uses a key other than
  `identity.key` (default `identity.json`). A pod whose Secret does not exist
  at all stays in `ContainerCreating`.
- `identity: ... is not a valid identity JSON object` or `... is missing
  gateway_id or gateway_secret`: the file must hold exactly
  `{"gateway_id": "...", "gateway_secret": "..."}`. Unknown fields are
  refused, so storing the whole enrollment response does not work. The
  `jq -ce '{gateway_id, gateway_secret}'` step in the install pipeline keeps
  only those two fields.
- `refusing to start: connectors: self-check could not prove the credential
  cannot read secrets: connector "<name>"; failed check <resource> <action>:
  <kind>; ...`: at boot, Argo CD could not be reached, the token check
  (`GET /api/v1/session/userinfo`) was refused, or a can-i question did not
  complete. The pod exits and restarts (`CrashLoopBackOff`). The named check
  says which: `failed check session userinfo: unauthorized` points at the
  token Secret, `unreachable`, `timeout` or `tls` at `base_url`, the
  connector's `egress` peer or the CA, and any other check (for example
  `failed check exec create: bad request`) at that can-i question. Once
  Argo CD answers, the next restart passes; see
  [Release 1: an Argo CD outage at boot is a crash loop](gateway.md#release-1-an-argo-cd-outage-at-boot-is-a-crash-loop).
- After boot, the same failures do not restart the pod. It stays up and not
  ready, stops claiming, and turns ready once a recheck passes.
- `connector kind is not enabled in Release 1`: the connectors file names
  `eso` or `rollout`. Release 1 binds `argocd` only.
- No heartbeat accepted within `SB_GATEWAY_CP_UNREACHABLE_AFTER` (default
  `2m`): the control plane is unreachable. Check `cp.endpoint`, the
  `cp.egress.cidrs` NetworkPolicy peer and, for a private CA,
  `cp.caExistingSecret`.
- `catalog upload failed` with `http 400`, again on every heartbeat: the
  control plane refused the catalog. If the api was not upgraded before the
  Gateway, it does not know the catalog `identity` field that the Gateway
  sends for an Argo CD target whose uid it knows. Upgrade the api; see
  [Application identity](gateway.md#application-identity).
- `invalid connector settings: ... applications.id: must not start with "d-"`:
  a target `id` in the connectors file uses the prefix reserved for
  discovered targets, and the Gateway refuses to start. Rename the target.

### Gateway refuses to start: over-privileged

A log line `refusing to start: connectors: credential is over-privileged:
connector "<name>"; failed check <resource> <action>: can-i yes; ...` for an
`argocd` connector comes from the Argo CD can-i probe: Argo CD answered `yes`
to the question named in the line, one of those in
[Argo CD privilege checks](gateway.md#argo-cd-privilege-checks). For example
`failed check logs get: can-i yes` means the token may read pod logs. The line
names the resource and action, not the AppProject or the object, so check
every policy line that applies to the Gateway's account or role for that right,
on the allowed AppProjects and on each configured Application. Remove the
extra right from the Argo CD policy of the Gateway's account so that only the
[minimal policy](gateway.md#the-minimal-policy) is left, and check
`policy.default` in `argocd-rbac-cm` too: `role:readonly` grants `logs, get`
and trips this check. The pod restarts until the grant is gone. When a recheck
finds a grant on a running Gateway, the replica turns not ready, reports
`over_privileged` in a heartbeat and stops. The control plane then pauses
dispatch for that connector until the report is 10 minutes old, so after the
fix, tasks can wait up to 10 minutes before they are claimed again.

For an `eso` or `rollout` connector, the same message comes from the
Kubernetes self-check. Those Release 2 connectors need
`SB_GATEWAY_ENABLE_R2_CONNECTORS=true`; a Release 1 Gateway built from the
chart has no Kubernetes access and never runs it.

The Kubernetes self-check refuses to start when its service account can use
any verb on `secrets`, or any write verb on a resource a connector reads, or when a review
call fails. There is no override. Remove the grant from the RBAC bound to the
Gateway's service account. When a recheck finds such a grant on a running
Gateway, it reports `over_privileged` in a heartbeat before it stops, and the
api records a `gateway.over_privileged` audit event.

### Connector advertised but nothing is bound

The Gateway reports its connectors and targets in the catalog, but an
advertised connector does nothing until an admin approves it and binds a
target. In the detail view, check the connector's `status`:

- `advertised`: approve it with
  `POST /api/v1/admin/gateways/<id>/connectors/<connector-uuid>/approve`.
- `approved` but no entry under `bindings`: create a binding with
  `POST /api/v1/admin/gateway-bindings`.
- `missing`: the Gateway no longer advertises this connector. Check the
  connector `name` in the chart values.

A binding request that fails answers with a closed code. `target_not_advertised`
means the `argocd_target_id` is not an application `id` in the connectors file,
and `target_stale` means the Gateway advertised it once but no longer does.

### Observation error `target_identity_changed`

The Application under the target's name is not the object the Gateway pinned:
it was deleted and recreated, so it has a new `metadata.uid`. The Gateway
reports nothing about the new object. If the change is expected, read the new
uid (`kubectl get application -n <namespace> <name> -o jsonpath='{.metadata.uid}'`),
set it as `applications[].uid` and upgrade the release. Without a `uid` in the
values, restart the Gateway. The Gateway then advertises the new identity, so
the control plane marks the target `identity_changed` (`identity_status` in
the detail view) and suspends its bindings. A platform admin then re-confirms
it with
`POST /api/v1/admin/gateways/<id>/connectors/<connector-uuid>/targets/<target-id>/confirm-identity`.
Re-confirm only after the Gateway runs with the new uid, because the
re-confirm accepts whatever identity the Gateway advertises at that moment.
See [Application identity](gateway.md#application-identity).

While the target is `identity_changed`, its tasks are not dispatched, a result
for it is refused with `target_identity_changed`, and a new binding on it gets
`409 target_identity_changed`. A result for a pinned target that carries no
`identity_digest`, or another one, is refused with `identity_digest_missing` or
`identity_digest_mismatch`. Each refusal is audited as
`observation.evidence.rejected` with that reason.

### Gateway gets 401 from the control plane

The log shows `control plane refused this gateway; claiming stopped, staying up
and not ready until restarted`. The pod stays up and not ready on purpose, so it
does not restart-loop. The api records `gateway.auth.rejected`.

The usual cause is a revoked Gateway (`status: "revoked"` in
`GET /api/v1/admin/gateways`). There is no rotation in Release 1: create a new
Gateway, mint a token, enroll, replace the identity Secret and restart the
Deployment. A `disabled` Gateway gets the same `401`: enable it again
(**Enable…** on its detail panel, or `PUT /api/v1/admin/gateways/<id>/enabled`)
and restart the Deployment. If the Gateway is still `active`, the Secret holds a credential
that does not belong to it, for example from an earlier enrollment.

### Observation stays pending, or shows "No observation configured"

Check the request's observations first:

```bash
curl -fsS -b "$JAR" "$CP/api/v1/requests/<request-id>/observations" \
  | jq '{observation_source, rollup, tasks: [.tasks[] | {gateway_name, state, verdict, attempt_count, deadline_at}]}'
```

`rollup: "none"` means no task exists. Check `observation_source` and the
audit events with the `correlation_id` of the job that executed the change:

- `observation_source` is `none`: the environment is not set to `gateway`, so
  no task was created. `none` is the default, and environments that used the
  retired control-plane poller were moved to it at the
  [cutover](gateway-cutover.md). With `none`, the audit log has
  `request.observation_skipped` with reason `source_none`. The source is read
  when the request reaches `executed`, so switching it later does not add tasks
  to earlier requests. See
  [Switch the environment](gateway.md#8-switch-the-environment-to-gateway-observation).
- `request.observation_skipped` with reason `no_gateway_binding`: no enabled
  binding covers the secret in that environment, or the binding's Gateway is
  revoked or disabled, or its connector is not approved.
- No skip event and no task: the binding exists, but the Gateway no longer
  advertises its target (`target_stale`), so it was skipped.
- `scope_not_resolved`, `request_type_not_observed` or
  `provider_type_not_supported`: only patch and cross-team requests on
  `aws-sm` or `vault` secrets in an environment are observed.

`rollup: "pending"` with a task in `queued` that never moves:

- **Not yet claimable.** The first claim is allowed 10 seconds after
  `executed`, and a result that left the stage `not_observed` reschedules the
  task 15, 30, 60 and then 120 seconds later. Argo CD that stays
  `Progressing` or `OutOfSync` keeps the task in that loop until the deadline.
- **The Gateway is not claiming.** Check its status in **Admin → Gateways**. A
  `stale` Gateway has missed its heartbeats; check the pods and their route to
  the control plane. A Gateway pauses claiming while the control plane is
  unreachable, its catalog is not accepted or a connector self-check fails
  (see [Runtime behaviour](../components/gateway.md#runtime-behaviour)). A
  Gateway that has never had a heartbeat accepted gets `204` on every claim.
- **The connector or binding changed.** A task is claimable only while its
  binding is enabled, its connector approved, its target not
  `identity_changed`, and no replica of the Gateway seen in the last 10
  minutes last reported the connector, or itself, `over_privileged`.

A pending task never fails the request. At its deadline it ends `timed_out`.

### Observation timed out with `gateway_unavailable`

The deadline passed and the Gateway had not been seen since the task was
created, or was not `active` (stale, disabled or revoked). Check the Gateway's
status and its pod logs. A task is never handed to another Gateway, so the
request stays `timed_out`; the next change to the secret gets a new task.
`deadline_reached` instead means the Gateway was up but the stage was not
observed in time.

`timed_out` is not a failure of the request or of the deployment. Without the
worker sweepers (`SB_WORKER_GATEWAY_SWEEPERS_ENABLED`), an overdue task is
closed only when someone opens the request.

### Result rejected with `attempt_superseded` or `task_closed`

The Gateway log shows `result dropped: attempt superseded`, `result dropped:
lease expired` or `result dropped: task closed`, and the api records
`observation.evidence.rejected` with a `reason`:

- `attempt_superseded` (`stale_attempt`, `unknown_attempt`): the attempt is
  not the task's current one. Its lease ran out and the task was claimed again,
  it was released, or the Gateway was disabled or revoked while it held the
  lease. The newer attempt carries on. Frequent cases mean the Gateway works
  past its 60-second lease; check Argo CD latency.
- `task_closed`: the task is already closed. A later change to the same secret
  (`superseded_by_later_write`), a source change (`source_changed`), a deleted
  binding (`binding_removed`) or the deadline closed it first.

Neither needs action on its own. The verdict comes from the result that was
accepted, or from the reason the task closed.

### Claim answers `429 inflight_limit`

The Gateway already holds `max_inflight_tasks` live leases (default 20), or the
replica asking already holds one, which is the limit per replica. The Gateway
backs off for the `Retry-After` time. Raise `max_inflight_tasks` when you create
the Gateway, or add replicas, if tasks wait too long. The claim rate limit
(2400 a minute per Gateway) answers `429` too.

## Useful queries against the audit log

### Find every action for one request

```bash
curl -fsS "http://localhost:18080/api/v1/audit-events?correlation_id=<uuid>" \
  -b "$JAR" | jq '.[] | {time:.occurred_at, actor, action, resource}'
```

### Find every login failure in the last hour

```bash
SINCE=$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)
curl -fsS "http://localhost:18080/api/v1/audit-events?action=auth.login&since=$SINCE" \
  -b "$JAR" \
  | jq '.[] | select(.status=="denied")'
```

### Find every wrap retrieval (who saw which value when)

```bash
curl -fsS "http://localhost:18080/api/v1/audit-events?action=wrap.retrieve" \
  -b "$JAR" \
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
| `redis_call_timeouts_total{site}` | api Redis calls that hit their deadline: `auth_cache` (agent and Gateway auth, revoke, 300ms) and `rate_limit` (500ms). A rise means Redis is slow before it is down: limiters start failing open, and revokes may answer `503 revoked_cache_unconfirmed` |

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
