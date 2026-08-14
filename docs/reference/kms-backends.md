# KMS backends

Secrets Bridge uses **envelope encryption** for every wrap and
every ArgoCD token: a per-row data key (DEK) wraps the value with
AES-256-GCM; the DEK itself is wrapped by a KMS-managed master
key. The KMS backend is pluggable behind one env var.

| Backend | Status | When to use |
|---|---|---|
| `local` | ✅ ships | **Dev only.** Master key from `SB_WRAP_MASTER_KEY`. Single-machine; not for production. |
| `vault-transit` | ✅ ships | OSS-first production. HashiCorp Vault's `transit` engine. |
| `aws-kms` | ✅ ships | AWS production. Uses standard SDK chain (IRSA / instance role). |
| GCP KMS | placeholder | Slots in via the same interface |
| Azure Key Vault | placeholder | Slots in via the same interface |

Selected via:

```bash
SB_KMS_BACKEND=local         # default - dev only
SB_KMS_BACKEND=vault-transit
SB_KMS_BACKEND=aws-kms
```

## `local`

The dev backend. Master key in an env var.

| Env var | Required | Notes |
|---|---|---|
| `SB_WRAP_MASTER_KEY` | yes | base64 32 bytes (`openssl rand -base64 32`) |

`KeyID` in the audit + row metadata is the SHA-256 of the master,
so operators can spot rotation in the trail without the key
appearing.

!!! danger "Never use in production"
    The master key lives in the same process env as the api. A
    process dump, a logged crash, or a misconfigured `env` command
    surfaces it. The whole point of a KMS is to move the master out
    of the workload. `local` defeats that.

    A future PR will WARN at boot when `SB_KMS_BACKEND=local` is
    set outside a clearly-marked dev profile (tracked as
    [api#29](https://github.com/secrets-bridge/api/issues/29)) and
    the Helm chart will default to `vault-transit` (tracked as
    [charts#2](https://github.com/secrets-bridge/charts/issues/2)).

## `vault-transit`

HashiCorp Vault's
[Transit secrets engine](https://developer.hashicorp.com/vault/docs/secrets/transit).
The master key never leaves Vault; the api receives DEK + DEK-
ciphertext from Vault per `GenerateDataKey` call, uses the
plaintext DEK for AES-GCM, and stores the opaque `vault:v1:...`
envelope as `data_key_ciphertext`.

### Configuration

| Env var | Required | Notes |
|---|---|---|
| `SB_KMS_VAULT_ADDR` | yes | `https://vault.example.com` |
| `SB_KMS_VAULT_TOKEN` | yes | Today; Kubernetes auth lands per follow-up |
| `SB_KMS_VAULT_KEY` | yes | Transit key name |
| `SB_KMS_VAULT_MOUNT` | no (default `transit`) | Mount path |

### Setup

```bash
# In Vault:
vault secrets enable transit
vault write -f transit/keys/sb-wrap

# In the api env:
export SB_KMS_BACKEND=vault-transit
export SB_KMS_VAULT_ADDR=https://vault.example.com
export SB_KMS_VAULT_TOKEN=hvs.CAESI...
export SB_KMS_VAULT_KEY=sb-wrap
```

The api logs the resolved backend at boot:

```
{"msg":"keymgmt backend ready","key_id":"vault-transit:transit/sb-wrap"}
```

### Key rotation

Use Vault's native rotation:

```bash
vault write -f transit/keys/sb-wrap/rotate
```

New rows wrap with the new key version automatically; old rows
decrypt with the original version (Vault retains all versions until
explicitly trimmed). A **tested rotation runbook** (covering both
Vault rotation and a full master swap) is tracked as
[api#31](https://github.com/secrets-bridge/api/issues/31).

## `aws-kms`

AWS KMS. The api calls `kms.GenerateDataKey(KeySpec=AES_256)` for
every wrap and stores the opaque ciphertext blob; on decrypt it
calls `kms.Decrypt`.

### Configuration

| Env var | Required | Notes |
|---|---|---|
| `SB_KMS_AWS_REGION` | yes | `us-east-1` |
| `SB_KMS_AWS_KEY_ID` | yes | CMK ARN, key id, or `alias/<name>` |
| `SB_KMS_AWS_ENDPOINT` | no | LocalStack / VPC endpoint override |

**No new credential env vars.** The standard AWS SDK chain
applies: IRSA in EKS, instance role on EC2, profile in dev.

### Key resolution

`KeyID` stored in `kms_key_id` is the **resolved ARN**, even when
you pass an alias. So if you rotate `alias/sb-wrap` to point at a
new CMK, the old rows still tell you which exact key wrapped them.
Critical for forensic audit.

### Setup

```bash
aws kms create-key --description "Secrets Bridge wrap key"
aws kms create-alias --alias-name alias/sb-wrap --target-key-id <key-id>

export SB_KMS_BACKEND=aws-kms
export SB_KMS_AWS_REGION=us-east-1
export SB_KMS_AWS_KEY_ID=alias/sb-wrap
```

### Key rotation

AWS KMS handles rotation automatically (enable annual rotation on
the CMK):

```bash
aws kms enable-key-rotation --key-id alias/sb-wrap
```

The CMK retains a backing-key version per rotation; AWS picks the
right one on decrypt. Rows wrapped with the old version still
decrypt; new rows use the new version. No app change needed.

## Choosing between `vault-transit` and `aws-kms`

| Question | If yes → `vault-transit` | If yes → `aws-kms` |
|---|---|---|
| Are you already running Vault for other reasons? | ✅ | |
| Is your workload on AWS with IRSA already wired? | | ✅ |
| Do you need multi-cloud or cloud-portable? | ✅ | |
| Are you OK paying per-call (AWS KMS pricing)? | | ✅ |
| Do you want the simplest path on a single AWS account? | | ✅ |

Both back the **same** `KeyManager` interface. Switching is a
**re-wrap** operation, not a code change.

## Per-tenant KMS scoping

Today: one CMK per deployment. **Piece 8c** (tracked) introduces a
scope through `KeyManager` so different rows can be wrapped by
different CMKs (per-project, per-environment, or per-tenant).
Existing single-backend deployments keep working unchanged.
