# Running locally with docker compose

A local loop for trying Secrets Bridge on one machine. The compose file
lives in the [`api`](https://github.com/secrets-bridge/api) repo. It starts
Postgres 17 and Redis 7, and can also build and run the api. The UI and the
agent run from their own repos.

!!! danger "Local development only"
    This setup uses dev-only switches: `SB_ENV=dev`, the `local` KMS backend,
    and for the agent walkthrough `SB_ALLOW_INSECURE_VAULT_ADDR` and
    `SB_INSECURE_TRANSPORT`. They are listed under
    [Insecure switches](config.md#insecure-switches-dev-only). Never expose
    this stack beyond your machine and never load real secrets into it.

## Quick start

### 1. Start Postgres and Redis

```bash
git clone https://github.com/secrets-bridge/api.git
cd api
docker compose up -d postgres redis
```

### 2. Generate dev keys

Generate fresh keys for every new environment. Never reuse a value from
these docs, an old compose file or another environment.

```bash
export SB_WRAP_MASTER_KEY="$(openssl rand -base64 32)"   # master key for the local KMS backend
```

The `local` KMS backend refuses to start without `SB_WRAP_MASTER_KEY`.

### 3. Run the api

From the `api` checkout (Go 1.25 or newer):

```bash
export SB_ENV=dev   # allows the local KMS backend and seeds three dev users
export DATABASE_URL="postgres://secrets_bridge:devpass@localhost:5432/secrets_bridge?sslmode=disable"
export REDIS_URL="redis://localhost:6379/0"
go run ./cmd/api
```

In another terminal:

```bash
curl -fsS http://localhost:8080/readyz
# → {"status":"ready"}
```

On its first boot against an empty database the api seeds three dev users
(an admin, an approver and a requester) and logs each user's email and
password **once**. Copy them from that log output. Set `SB_DEV_SEED_PASSWORD`
before the first boot if you want one shared password instead of a random
one per user.

!!! note "Running the api in a container instead"
    `docker compose up -d --build` also builds the `api` service from the
    repo's Dockerfile and runs it on port 8080. Export the keys from step 2
    in the same shell first: the api container reads `SB_WRAP_MASTER_KEY`
    from your environment and exits with an error when it is unset. Older
    copies of the compose file shipped a fixed dev master key instead; pull
    the latest `main` rather than reusing it.

### 4. Run the UI

From a checkout of the [`ui`](https://github.com/secrets-bridge/ui) repo
(Node 22 or newer):

```bash
npm ci
npm run dev
```

Open **http://localhost:5173/**. The Vite dev server proxies `/api` to
`http://localhost:8080`. Sign in with the admin user from the api's boot
log. `SB_ENV=dev` is what lets the session cookie work over plain
`http://localhost`.

## Wiring an agent end to end (Vault example)

An admin creates a one-time token for a provider connection,
`secrets-bridge-agent enroll` exchanges it for the agent credential and
generates the X25519 key locally, and the agent reads both from a read-only
directory. The steps below run everything locally. See
[Agent onboarding](agent-onboarding.md) for the model.

```bash
# 1. A throwaway Vault dev server on localhost, with a fake value in it.
export VAULT_DEV_TOKEN="$(openssl rand -hex 16)"
docker run -d --name sb-vault-dev -p 127.0.0.1:8200:8200 \
  -e VAULT_DEV_ROOT_TOKEN_ID="$VAULT_DEV_TOKEN" hashicorp/vault:2.2
docker exec -e VAULT_ADDR=http://127.0.0.1:8200 -e VAULT_TOKEN="$VAULT_DEV_TOKEN" \
  sb-vault-dev vault kv put secret/team-alpha/dev/db DB_PASSWORD=not-a-real-password

# 2. Restart the api with SB_ALLOW_INSECURE_VAULT_ADDR=true (dev only):
#    the dev Vault listens on http://, which provider connections refuse
#    by default.

# 3. Sign in as the seeded admin. The password goes to jq on stdin, so
#    it never shows in the process list. The session cookie goes into a
#    private cookie jar; every call below sends it with -b.
CP=http://localhost:8080
JAR=$(mktemp) && chmod 600 "$JAR"
read -rp 'Admin email: ' SB_ADMIN_EMAIL
IFS= read -rsp 'Admin password: ' SB_ADMIN_PASSWORD; echo
printf '%s\n%s\n' "$SB_ADMIN_EMAIL" "$SB_ADMIN_PASSWORD" | jq -Rn '{email: input, password: input}' \
  | curl -fsS -c "$JAR" -o /dev/null -X POST "$CP/api/v1/auth/login" \
      -H 'Content-Type: application/json' --data-binary @-

# 4. Register the Vault provider connection.
CONN_ID=$(curl -fsS -b "$JAR" -X POST "$CP/api/v1/provider-connections" \
  -H 'Content-Type: application/json' \
  -d '{"name":"local-vault","type":"vault","auth_method":"token","cluster_name":"local",
       "scope":{"address":"http://127.0.0.1:8200","mount":"secret"},
       "discover_interval_seconds":3600}' \
  | jq -r .id)

# 5. From a checkout of the agent repo: create a one-time enrollment token
#    for that connection (15 minutes by default) and hand it to enroll on
#    stdin. The bundle lands in a shell variable, then in three owner-only
#    files. Dev only: in a real install it goes to your secret store.
#    SB_INSECURE_TRANSPORT=true lets enroll and the agent use the local
#    http:// endpoint, the same dev-only switch as the runtime.
cd ../agent   # wherever you cloned github.com/secrets-bridge/agent
mkdir -p -m 700 .local/credentials
SB_BUNDLE=$(curl -fsS -b "$JAR" -X POST "$CP/api/v1/provider-connections/$CONN_ID/agent-enrollment-token" \
  -H 'Content-Type: application/json' \
  -d '{"name":"local-agent","expected_cluster_name":"local","expected_provider_type":"vault"}' \
  | jq -j .enrollment_token \
  | SB_INSECURE_TRANSPORT=true go run ./cmd/agent enroll --cp-endpoint "$CP" --token-file - \
      --name local-agent --cluster-name local --provider-type vault \
      --format json --output -)
for k in agent_id agent_secret private_key; do
  (umask 077 && jq -j ".$k" <<<"$SB_BUNDLE" > ".local/credentials/$k")
done
unset SB_BUNDLE

# 6. Run the agent against that directory. It runs in the background;
#    `kill %1` stops it. SB_VAULT_KV_MOUNT has to be the connection's mount
#    from step 4. The agent defaults to `kv`; with a mismatch it refuses
#    discovery and points reads and patches at the wrong mount.
SB_CP_ENDPOINT="$CP" SB_INSECURE_TRANSPORT=true \
SB_AGENT_CREDENTIALS_DIR="$PWD/.local/credentials" SB_CLUSTER_NAME=local \
SB_VAULT_ADDR=http://127.0.0.1:8200 SB_VAULT_TOKEN="$VAULT_DEV_TOKEN" \
SB_VAULT_KV_MOUNT=secret \
  go run ./cmd/agent > .local/agent.log 2>&1 &

# 7. After a few seconds the agent is listed, `active`, against the connection.
curl -fsS -b "$JAR" "$CP/api/v1/provider-connections/$CONN_ID/agents" | jq
```

The token is spent by step 5. The agent only reads `.local/credentials` and
writes nothing, so a restart reuses the same files. The files must stay
owner-only: the agent refuses a file with group write or any bit for others.
To start over, revoke the agent, delete `.local/credentials` and create a new
token.

## Ports

| Host port | Service | What |
|---|---|---|
| `8080` | api | Control Plane API: `/api/v1/*`, `/healthz`, `/readyz`, `/metrics`. Change it with `API_HOST_PORT` when the api runs in compose. |
| `5432` | postgres | Postgres 17 (`secrets_bridge` / `devpass`) |
| `6379` | redis | Redis 7 |
| `4566` | localstack (`--profile awskms`) | LocalStack KMS, for trying the `aws-kms` backend |
| `5173` | Vite dev server | The UI, from the `ui` repo |
| `8200` | Vault dev server | Only if you started it for the agent walkthrough |

The compose file publishes its ports on `127.0.0.1` only, so nothing is
reachable from other machines. Older copies of the compose file published
Postgres and Redis on every interface with fixed dev credentials; if yours
still does, pull the latest `main` before you start it on a shared network.

## Resetting state

```bash
# Stop everything and drop the Postgres volume (wipes all data,
# including the seeded users)
docker compose down -v
docker rm -f sb-vault-dev   # if you started it
rm -rf .local/credentials  # in the agent checkout
```

## What docker compose is good for, what it's not

| Use it for | Don't use it for |
|---|---|
| Local development | Production |
| Smoke tests and e2e in CI | Multi-replica deployments |
| Following along with this docs site | Anything internet-exposed |
| Demoing to a colleague | Storing real secrets |

For production, install the hardened Helm charts on a real Kubernetes
cluster with managed Postgres and Redis and a real KMS backend. See
[Production deployment](index.md#production-deployment).
