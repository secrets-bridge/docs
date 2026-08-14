# Glossary

Terms used across the docs, the code, and the BRD.

#### `access_request`
The first-class object the workflow flows around. A request to view
(`type=read`) or update (`type=patch`) one or more keys at a
specific provider reference. Carries a status (`pending`,
`approved`, `rejected`, `cancelled`, `executed`, `failed`,
`expired`).

#### Agent
The outbound-only worker process that runs inside the
target account / cluster. Holds provider credentials *for its own
boundary only*; never accepts inbound connections except loopback
probes; never imports a database or Redis driver. One agent per
cluster identity (`SB_CLUSTER_NAME`).

#### `audit_event`
An append-only row in the `audit_events` table. Carries `actor`,
`action`, `resource`, `status`, `correlation_id`, `metadata` (jsonb,
never carries plaintext), `occurred_at`. Schema-level triggers
reject UPDATE and DELETE.

#### `correlation_id`
The chain identifier propagated through every audit event for one
request lifecycle. Click any `corr` chip in the UI's Audit page to
filter the whole table to that chain.

#### Control Plane (CP)
The collection of `api` + `worker` + `Postgres` + `Redis` + a `KMS`
backend. Makes decisions, holds metadata, never holds plaintext
values.

#### KMS backend
The pluggable envelope-encryption layer. Three implementations ship:
`local` (dev only, master key in `SB_WRAP_MASTER_KEY`),
`vault-transit` (production with HashiCorp Vault), `aws-kms`
(production on AWS with IRSA / instance role). Selected by
`SB_KMS_BACKEND`.

#### Provider
A third-party secrets store: HashiCorp Vault, AWS Secrets Manager,
GCP Secret Manager, Azure Key Vault, Kubernetes Secret. Secrets
Bridge augments providers; it doesn't replace them.

#### `policy_rule`
Selector-based mapping from `(project, environment, secret_ref,
provider)` to a workflow. Walked in priority order; first match
wins. The seed `match-all` rule at priority 0 is the fallback.

#### `secret_wrap`
A KMS-encrypted envelope holding one key's plaintext for the
duration of one request. TTL'd, single-shot, atomic-consume.
Auditing tracks `content_hash` + `byte_length` but never the
value.

#### Single-shot
A consume-once semantic for wraps. The `consumed_at` column flips
atomically under a row-level lock; a second caller gets `410 Gone`.
The platform uses this for both the agent path (patch flow) and
the user path (read flow).

#### Wire envelope
The defense-in-depth layer above TLS. CP→Agent uses X25519 sealing
to the agent's registered public key; Agent→CP uses a KMS-issued
data-encryption key the agent zeroes after one AES-GCM operation.
Even a TLS-terminating proxy sees only ciphertext.

#### Workflow
A reusable approval template: minimum approver count, justification
required, self-approval allowed, TTLs for the various wrap
lifecycle phases. Captured at request submit time so policy edits
don't retroactively change in-flight requests.

#### Wrap summary
The value-free metadata projection of a wrap (id, key_name,
consumed flag, expires_at). Lets the UI render the Wraps card on
the request detail page without ever fetching plaintext until the
user clicks Reveal.
