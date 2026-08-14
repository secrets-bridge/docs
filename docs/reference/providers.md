# Providers supported

The agent's `ResolverByType` dispatches to one resolver per
`target_provider_type` string. The CP's metadata layer is provider-
agnostic; every provider implements the same `core.Provider`
interface.

| `target_provider_type` | Resolver status | Auth options | Config keys |
|---|---|---|---|
| `vault` | ✅ ships | Token (`SB_VAULT_TOKEN`) or Kubernetes (`SB_VAULT_KUBERNETES_ROLE`) | `address`, `kvMount` (default `secret`), `kvPrefix`, `namespace` |
| `aws-sm` | ✅ ships | Standard AWS SDK chain (IRSA / instance role / `AWS_*` env / shared profile) | `region` (required), `roleArn` (cross-account), `endpoint` (LocalStack) |
| `gcp-sm` | placeholder | - | - |
| `azure-kv` | placeholder | - | - |
| `kubernetes` | placeholder | - | - |

## HashiCorp Vault

**KV v2 only.** Path layout depends on the `kvMount` config (default
`secret`). The agent reads via `{mount}/data/{ref}` and writes the
KV v2 `{"data": {...}}` envelope.

### Authentication

| Method | Required env | When |
|---|---|---|
| Token | `SB_VAULT_TOKEN` | Local dev, dev profile in docker-compose (`vault dev`) |
| Kubernetes | `SB_VAULT_KUBERNETES_ROLE` | Production on K8s. Uses the projected SA token, lease-tracked + refresh |

The token method auto-renews within `tokenRefreshMargin = 30s`
of expiry. The Kubernetes method re-authenticates from the SA
token on lease expiry.

### Refused payload keys

The Vault resolver refuses these keys in the request's
`target_provider_config` (defends against an api PR that
accidentally tries to ship credentials):

- `token`

A future PR will refuse more.

### Tag preservation

Vault `custom_metadata` is surfaced verbatim into the CP's
`secrets.labels` jsonb on discovery, so a `Team: billing` tag in
Vault becomes a filterable label in the UI's Secrets page.

## AWS Secrets Manager

The agent uses the AWS SDK Go v2 client. All credential resolution
goes through the standard SDK chain: **no new credential env vars
are introduced**. This is deliberate: adding `SB_AWS_*_KEY` would
duplicate the chain and invite operators to mix sources.

### Authentication

| Method | What |
|---|---|
| IRSA | Recommended for EKS deployments |
| Instance role | EC2 / Fargate |
| `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` | Local dev / non-AWS hosts |
| Shared profile (`~/.aws/credentials`) | Developer machine |

Cross-account access via `SB_AWS_ROLE_ARN` triggers an
`AssumeRole` through STS.

### Refused payload keys

The AWS SM resolver refuses **seven** credential-shaped keys in
the request's `target_provider_config` (table-driven check):

```
awsAccessKeyID
awsSecretAccessKey
awsSessionToken
accessKeyID
secretAccessKey
sessionToken
credentials
```

### Tag preservation

AWS Tags are surfaced as labels on discovery, same pattern as
Vault `custom_metadata`.

## What "supported" actually means

A provider ships when **three things** are true:

1. The `core.Provider` interface is implemented in `core/providers/<kind>`
2. The agent's `ResolverByType` registers the kind
3. There's a live e2e against a real instance of the provider (or
   LocalStack), verified plaintext round-trip end-to-end, canary
   scan returns zero matches

GCP SM, Azure Key Vault, and Kubernetes Secret are at step (1)
partially: the metadata interface stubs are written; the
resolver + e2e land per design partner request.

## Adding a new provider

The pattern is established. The next provider lands as:

1. New package `core/providers/<kind>/<kind>.go` implementing
   `Provider`. Take the SDK client as an interface (subset
   interface so unit tests inject a fake).
2. `Register(*providers.Registry)` function, no `init()`.
3. Unit tests in `<kind>_test.go` covering: registration,
   pagination if applicable, `NotFound` mapping to
   `providers.ErrNotFound`, no-leak assertion on error messages.
4. Agent: add to `internal/executor/resolvers.go` under
   `ResolverByType`. Refuse credential-shaped keys in the payload.
5. Live e2e: bring up a real (or LocalStack) instance, mint an
   agent, submit a patch + read, verify round-trip.
6. Open one PR per repo (`core` for the connector, `agent` for the
   resolver). Cross-link them.
