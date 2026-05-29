# Deploying with docker-compose

The fastest way to try Secrets Bridge end-to-end. Brings up
Postgres + Redis + api + ui + ingress in one command; optional
profiles add `worker`, `vault`, `agent`, or `full` (all of them).

## Quick start

```bash
git clone https://github.com/secrets-bridge/secrets-bridge.git
cd secrets-bridge

# Default profile: postgres + redis + api + ui + ingress.
docker compose up -d --build

# Wait a few seconds, then check:
curl -fsS http://localhost:18080/readyz
# → {"status":"ready"}
```

Open **http://localhost:18080/** in your browser. The seed
admin credentials are:

| Field | Value |
|---|---|
| Email | `admin@example.com` |
| Password | `admin` |

You should land on the Dashboard.

!!! warning "Rotate these immediately for any non-toy use"
    The seed password lives in `docker-compose.yml` and is
    intended **only** for local development. Override via shell env:

    ```bash
    SB_BOOTSTRAP_ADMIN_EMAIL=alice@example.com \
    SB_BOOTSTRAP_ADMIN_PASSWORD="$(openssl rand -base64 24)" \
    docker compose up -d
    ```

    The bootstrap step is idempotent — once `local_users` has any
    row, the env vars are ignored. To re-seed, wipe the volume:

    ```bash
    docker compose down -v
    ```

## Optional profiles

```bash
# Worker (sweepers + GitOps observation poller stub)
docker compose --profile worker up -d

# Vault dev container (needed for the agent to read/write real values)
docker compose --profile vault up -d

# Agent — REQUIRES a manual mint step first; see below
docker compose --profile agent up -d

# Everything at once
docker compose --profile full up -d
```

## Wiring an agent end-to-end (Vault example)

```bash
# 1. Mint an agent from the UI (Sidebar → Agents → + Mint agent)
#    OR via curl:
TOKEN=$(curl -fsS -X POST http://localhost:18080/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"admin"}' \
  | jq -r .token)

MINT=$(curl -fsS -X POST http://localhost:18080/api/v1/agents \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"name":"local-vault","scope":{"cluster":"local"}}')
AGENT_ID=$(echo "$MINT" | jq -r .id)
AGENT_SECRET=$(echo "$MINT" | jq -r .agent_secret)

# 2. Bring up Vault + agent with those creds
SB_AGENT_ID=$AGENT_ID SB_AGENT_SECRET=$AGENT_SECRET \
  docker compose --profile vault --profile agent up -d

# 3. Seed a secret in Vault
docker exec secrets-bridge-vault-1 sh -c \
  'VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN=devroot \
   vault kv put secret/prod/db/password \
   DB_PASSWORD=hunter2-the-actual-prod-password'

# 4. From the UI: Requests → + New request → Read flow against
#    target_ref=prod/db/password, leave provider config blank
#    (defaults to kvMount=secret for Vault).

# 5. Sign in as a second user (or from another browser as the
#    same user with allow_self_approval enabled on the workflow)
#    and approve.

# 6. The agent claims, fetches from Vault, posts the wrap. Back as
#    the requester, click Reveal → see the plaintext exactly once.
```

## Ports

| Host port | Container | What |
|---|---|---|
| `18080` | ingress (nginx shim) | Front door. UI on `/`, api on `/api/v1/*`, probes on `/healthz` / `/readyz` |
| `5432` (only if exposed) | postgres | Postgres — **not exposed by default** |
| `6379` (only if exposed) | redis | Redis — **not exposed by default** |
| `8200` (`--profile vault`) | vault | Vault dev mode |

Override the host port via `INGRESS_HOST_PORT`:

```bash
INGRESS_HOST_PORT=19090 docker compose up -d
```

## Resetting state

```bash
# Stop everything and drop the Postgres volume (wipes all data,
# including the bootstrapped admin)
docker compose down -v
```

## What docker-compose is good for, what it's not

| Use it for | Don't use it for |
|---|---|
| Local development | Production |
| Smoke tests + e2e in CI | Multi-replica deployments |
| Following along with this docs site | Anything internet-exposed |
| Demoing to a colleague | Storing real secrets |

For production, use the Helm chart (when `charts` ships) on a
real Kubernetes cluster with a managed Postgres + Redis + a real
KMS backend.
