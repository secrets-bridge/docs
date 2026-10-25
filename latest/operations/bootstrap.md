# Bootstrap & first sign-in

After the api starts for the first time, the platform has to be
**bootstrapped** with a usable admin identity. Otherwise nothing
can be done: every write endpoint is gated by
`auth.Require(perm)` and there are no role assignments yet.

## What "bootstrapped" means

Two things happen on first boot when `local_users` is empty and
the bootstrap env vars are set:

1. **A local admin user is created**, bcrypt-hashed password
   stored in `local_users` (idempotent: a second boot with the
   same env vars is a no-op once any user exists).
2. **The new user is bound to the seed `admin` role** with global
   scope, via the existing user_roles flow.

The api logs both actions at INFO in its JSON log output:

```
{"msg":"bootstrap local admin created","user_id":"<uuid>","email":"admin@example.com"}
{"msg":"bootstrap admin assignment created","user_id":"<uuid>","role":"admin","scope":"global"}
```

## Configuration

| Env var | Required | Default | Notes |
|---|---|---|---|
| `SB_BOOTSTRAP_ADMIN_EMAIL` | recommended on first boot |  | Becomes the local-admin email |
| `SB_BOOTSTRAP_ADMIN_PASSWORD` | recommended on first boot |  | **Rotate immediately after first sign-in** |
| `SB_BOOTSTRAP_ADMIN_USER_ID` | optional |  | Pre-OIDC escape hatch: assigns the admin role to a specific opaque `user_id` (matches the future OIDC `sub` claim). Use this alongside `_EMAIL`/`_PASSWORD` if you want both the local-admin login and a pre-arranged OIDC identity to hold admin. |

## First sign-in

1. Open the UI (`http://localhost:5173/` for the
   [local docker compose setup](docker-compose.md)).
2. You'll be redirected to `/login`.
3. Enter the email + password from the env vars (or a dev user from
   the api's first-boot log when it runs with `SB_ENV=dev`).
4. With `SB_ENV=dev` you land on the Dashboard with the `Agents Online`
   KPI showing `0 / 0`. On a production install, where login-time MFA
   is on by default, you land on **Second factor** first: add an
   authenticator app or a security key, then **Continue** asks for it
   once and opens the Dashboard
   ([Step-up vs login-time MFA](authentication.md#step-up-vs-login-time-mfa)).

The api keeps you signed in with an HttpOnly session cookie, which
the SPA's scripts can't read. Sign out from the console to end the
session.

## Rotating the admin password

There's no UI surface for this in the current slice. For now, use
`psql` directly against the api's Postgres:

```bash
# Generate a bcrypt hash for the new password
NEW_HASH=$(htpasswd -bnBC 12 "" "your-new-password" | tr -d ':\n' | sed 's/^.\$2y/$2y/')

# Update the row (local docker compose setup; use your own psql
# connection elsewhere)
docker compose exec -T postgres \
  psql -U secrets_bridge -d secrets_bridge \
  -c "UPDATE local_users SET password_hash = decode('$(echo "$NEW_HASH" | xxd -p)', 'hex') WHERE email = 'admin@example.com';"
```

A real password-change endpoint + UI page lands as a follow-up.

## Disabling the local admin (after OIDC ships)

Once you've added a real OIDC identity with the admin role, you
can disable the local-admin row so brute-force attempts against
its bcrypt hash are pointless:

```sql
UPDATE local_users SET disabled = TRUE WHERE email = 'admin@example.com';
```

A disabled user's login attempts return the same generic
`401 invalid credentials`; the audit log records
`error_kind=user_disabled`.

## Enrolling your first agent

An admin creates a one-time token bound to a provider connection. An operator
then runs `secrets-bridge-agent enroll` on a trusted workstation: it generates
the agent's X25519 key locally, exchanges the token for `agent_id` and
`agent_secret`, and prints the bundle once, to be stored in your secret store or
a Kubernetes Secret. The agent pod only reads that Secret. See
[Agent onboarding](agent-onboarding.md) for the model, the AWS Secrets Manager
and Vault variants, and key custody.

Create the token in the console or through the API, as below. You need
`agent.mint` (the seed `admin` role has it), an active
[provider connection](provider-connections.md) and, on a production install,
a second factor on your account: login-time MFA is on by default outside
`SB_ENV=dev`, so add an authenticator app under **Second factor** in the
console first ([Step-up vs login-time MFA](authentication.md#step-up-vs-login-time-mfa)).

```bash
CP=https://secrets-bridge.example.com   # http://localhost:8080 for the local setup

# Sign in. The password is read from the terminal and handed to jq on
# stdin (printf is a shell builtin), so it is never in a command line,
# the shell history or the process list. The session cookie goes into a
# private cookie jar.
JAR=$(mktemp) && chmod 600 "$JAR"
read -rp 'Admin email: ' SB_ADMIN_EMAIL
IFS= read -rsp 'Admin password: ' SB_ADMIN_PASSWORD; echo
printf '%s\n%s\n' "$SB_ADMIN_EMAIL" "$SB_ADMIN_PASSWORD" | jq -Rn '{email: input, password: input}' \
  | curl -fsS -c "$JAR" -o /dev/null -X POST "$CP/api/v1/auth/login" \
      -H 'Content-Type: application/json' --data-binary @-
unset SB_ADMIN_PASSWORD

# Step up with your TOTP factor (production: login-time MFA is on; skip
# this block on the local SB_ENV=dev setup). Fresh for 15 minutes.
FACTOR_ID=$(curl -fsS -b "$JAR" "$CP/api/v1/users/me/mfa/factors" \
  | jq -r 'map(select(.kind == "totp"))[0].id')
CHALLENGE_ID=$(curl -fsS -b "$JAR" -X POST "$CP/api/v1/auth/mfa/challenge" \
  -H 'Content-Type: application/json' -d '{"kind":"totp"}' | jq -r .challenge_id)
IFS= read -rsp 'TOTP code: ' SB_TOTP_CODE; echo
printf '%s\n%s\n%s\n' "$CHALLENGE_ID" "$FACTOR_ID" "$SB_TOTP_CODE" \
  | jq -Rn '{challenge_id: input, factor_id: input, code: input}' \
  | curl -fsS -b "$JAR" -o /dev/null -X POST "$CP/api/v1/auth/mfa/verify" \
      -H 'Content-Type: application/json' --data-binary @-
unset SB_TOTP_CODE

# Pick the provider connection the agent will serve.
curl -fsS -b "$JAR" "$CP/api/v1/provider-connections" \
  | jq '.[] | {id, name, type, cluster_name, status}'
CONN_ID=<provider-connection-id>

# Create the one-time token and hand it straight to enroll on stdin, then
# write the bundle into a Kubernetes Secret in the workload cluster. The
# token, agent_secret and private_key are never printed, never in argv and
# never on disk.
kubectl create namespace secrets-bridge   # skip if it already exists
curl -fsS -b "$JAR" -X POST "$CP/api/v1/provider-connections/$CONN_ID/agent-enrollment-token" \
  -H 'Content-Type: application/json' \
  -d '{"name":"cluster-a-agent","expected_cluster_name":"cluster-a","expected_provider_type":"vault"}' \
  | jq -j .enrollment_token \
  | secrets-bridge-agent enroll --cp-endpoint "$CP" --token-file - \
      --name cluster-a-agent --cluster-name cluster-a --provider-type vault \
      --format env --output - \
  | kubectl -n secrets-bridge create secret generic secrets-bridge-agent-identity \
      --from-env-file=/dev/stdin
rm -f "$JAR"
```

All body fields are optional. `expires_in_seconds` defaults to 900 (15
minutes) and is clamped to 60 to 86400. When `expected_cluster_name` or
`expected_provider_type` is set, an enrollment that reports anything else is
refused. The response carries the token exactly once, so don't log or paste
the whole response.

Then install the `agent` chart with the Secret's name (see
[Production deployment](index.md#production-deployment) for the chart
source):

```bash
helm install secrets-bridge-agent oci://ghcr.io/secrets-bridge/charts/secrets-bridge-agent \
  --version <chart-version> \
  --namespace secrets-bridge \
  --set clusterName=cluster-a \
  --set cp.endpoint=https://secrets-bridge.example.com \
  --set image.digest=sha256:<agent-digest> \
  --set identity.existingSecret=secrets-bridge-agent-identity \
  --set providers.vault.enabled=true \
  --set providers.vault.addr=https://vault.example.com \
  --set providers.vault.kubernetesRole=secrets-bridge-agent
```

The agent reads `agent_id`, `agent_secret` and `private_key` from the Secret,
mounted read-only at `/etc/secrets-bridge/agent`, and starts heartbeating.
Restarts read the same Secret. The agent shows up under
`GET /api/v1/provider-connections/<id>/agents` and turns `active` on its
first heartbeat.

If enrollment is refused (expired token, wrong cluster name or provider
type), fix the cause and create a new token. An unused token stops working
when it expires, so keep `expires_in_seconds` short. See
[Troubleshooting: agent](troubleshooting.md#agent).

!!! warning "Direct agent mint is a dev-only break-glass"
    `POST /api/v1/agents` is the legacy direct mint, which hands back a
    long-lived `agent_secret` and also requires a public key. The api refuses it with
    `403 direct_agent_mint_disabled` unless it runs with
    `SB_ALLOW_DIRECT_AGENT_MINT=true`. Leave that switch off outside a
    local dev loop; see [Insecure switches](config.md#insecure-switches-dev-only).

## Submitting your first read request

Once you have an agent running and `provider creds`
configured for it:

1. **Sidebar → Requests → + New request**
2. **Read** type
3. **Provider**: Vault (or AWS Secrets Manager)
4. **Project** and **Environment**: the project and environment the
   secret is bound to. Environment is required when the binding is
   scoped to one
5. **Secret reference**: e.g. `prod/db/password`
6. **Keys**: e.g. `DB_PASSWORD` (or leave one empty row for "all
   keys in the bundle")
7. **Justification**: required, typically an incident or ticket
   number
8. **Submit** → you're navigated to the request detail page

Then sign in as a second user with the `secret.approve` permission
and approve from the Requests page's Approver queue. The requester
can never approve or reject their own request, whatever their role
(admin included) or the workflow says: the api answers
`403 separation_of_duties_violated` and audits the attempt.

Once approved → agent claims → fetches → posts wrap → request →
`executed`. Refresh the detail page; the Wraps card now shows
`DB_PASSWORD` with the **Reveal (one-time)** button. Click it,
confirm, see the value, copy it, close.

That's the whole read flow.
