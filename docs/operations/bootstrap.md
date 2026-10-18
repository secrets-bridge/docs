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
4. You land on the Dashboard with the `Agents Online` KPI showing
   `0 / 0`.

The token is stored in React state only, **closing the tab
signs you out** by design (BRD §15).

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

Agents onboard by **enrollment**. An admin creates a one-time token bound to
a provider connection; the agent exchanges it once for a persistent
identity and stores that identity itself. See
[Agent onboarding](agent-onboarding.md) for the model.

The UI has no enrollment screen yet, so create the token through the API.
You need `agent.mint` (the seed `admin` role has it) and an active
[provider connection](provider-connections.md).

```bash
CP=https://secrets-bridge.example.com   # http://localhost:8080 for the local setup

# Sign in. The password is read from the terminal, not typed on the command line.
read -rp 'Admin email: ' SB_ADMIN_EMAIL
read -rsp 'Admin password: ' SB_ADMIN_PASSWORD; echo
TOKEN=$(jq -n --arg e "$SB_ADMIN_EMAIL" --arg p "$SB_ADMIN_PASSWORD" '{email:$e,password:$p}' \
  | curl -fsS -X POST "$CP/api/v1/auth/login" -H 'Content-Type: application/json' --data-binary @- \
  | jq -r .token)

# Pick the provider connection the agent will serve.
curl -fsS "$CP/api/v1/provider-connections" -H "Authorization: Bearer $TOKEN" \
  | jq '.[] | {id, name, type, cluster_name, status}'
CONN_ID=<provider-connection-id>

# Create the one-time token and put it straight into a Kubernetes Secret
# in the workload cluster, without printing it.
kubectl create namespace secrets-bridge   # skip if it already exists
curl -fsS -X POST "$CP/api/v1/provider-connections/$CONN_ID/agent-enrollment-token" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"cluster-a-agent","expected_cluster_name":"cluster-a","expected_provider_type":"vault"}' \
  | jq -j .enrollment_token \
  | kubectl -n secrets-bridge create secret generic secrets-bridge-agent-enrollment \
      --from-file=enrollment_token=/dev/stdin
```

All body fields are optional. `expires_in_seconds` defaults to 900 (15
minutes) and is clamped to 60 to 86400. When `expected_cluster_name` or
`expected_provider_type` is set, an agent that reports anything else is
refused. The response carries the token exactly once, so don't log or
paste the whole response. Its `install_hint` commands don't contain the
token: they read it at a silent prompt.

Then install the `agent` chart in enrollment mode (see
[Production deployment](index.md#production-deployment) for the chart
source):

```bash
helm install secrets-bridge-agent oci://ghcr.io/secrets-bridge/charts/secrets-bridge-agent \
  --version <chart-version> \
  --namespace secrets-bridge \
  --set clusterName=cluster-a \
  --set cp.endpoint=https://secrets-bridge.example.com \
  --set enrollment.enabled=true \
  --set enrollment.tokenSecretName=secrets-bridge-agent-enrollment \
  --set identity.mode=file \
  --set identity.persistence.enabled=true \
  --set agent.providerType=vault \
  --set providers.vault.enabled=true \
  --set providers.vault.addr=https://vault.example.com \
  --set providers.vault.kubernetesRole=secrets-bridge-agent
```

On first boot the agent calls `POST /api/v1/agents/enroll` with the token,
writes `{agent_id, agent_secret}` to `SB_IDENTITY_FILE` on the persistent
volume and starts heartbeating. Restarts reuse that file; the token is
never spent twice. The agent shows up under
`GET /api/v1/provider-connections/<id>/agents` and turns `active` on its
first heartbeat.

If the agent fails to enroll (expired token, wrong cluster name or provider
type), fix the cause and create a new token. An unused token stops working
when it expires, so keep `expires_in_seconds` short.

!!! warning "Direct agent mint is a dev-only break-glass"
    The **+ Mint agent** drawer on the Agents page and
    `POST /api/v1/agents` use the legacy direct mint, which hands back a
    long-lived `agent_secret`. The api refuses it with
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

Then either:

- Sign in as a second user (with `secret.approve` permission)
  and approve from the Requests page's Approver queue, or
- Enable `allow_self_approval` on the workflow used by the request
  and approve from the detail page's Approver actions card.

Once approved → agent claims → fetches → posts wrap → request →
`executed`. Refresh the detail page; the Wraps card now shows
`DB_PASSWORD` with the **Reveal (one-time)** button. Click it,
confirm, see the value, copy it, close.

That's the whole read flow.
