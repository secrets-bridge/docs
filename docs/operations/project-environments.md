# Project environments

Slice L introduced first-class environments to the Secrets Bridge data
model. This page explains what they are, the `non_prod` / `prod`
distinction that gates direct reveal, and how to wire them up
operationally.

## What an environment is

An **environment** is a lifecycle boundary inside a project — `dev`,
`staging`, `uat`, `prod`, or any other name your team uses. The
schema (`api/pkg/storage/migrations/0001_initial_schema.up.sql`) has
carried environments since v0.1; Slice L1 added three classifying
fields:

| Column | Purpose |
|---|---|
| `kind` | **Hard safety boundary**. `non_prod` or `prod`. The PolicyEngine refuses to honour `direct_reveal_allowed=true` against `kind='prod'` regardless of policy or permission. PROD direct-reveal is impossible by construction. |
| `risk_level` | `SMALLINT 0-4`. Future fine-grain policy knob; today it drives a UI badge intensity only. |
| `description` | Operator notes. No semantic load. |

The existing `type` column (dev / staging / uat / prod / other) stays —
operators use it as a free lifecycle label that doesn't have to
agree with `kind`. The two are independently mutable for the case
where a staging-labelled env actually carries prod data: set
`type='staging'` but `kind='prod'` and the PROD invariant fires.

## kind vs type — why both

The free-string `type` was useful as a lifecycle label, but it was
also doing double duty as the implicit risk signal. Operators
naturally write `type='uat'` for non-production environments — and a
single typo or rename can silently un-gate a sensitive flow. `kind`
is the hard, two-value classifier that the engine actually consults.

A reasonable mental model:

- `type` is what the env is called.
- `kind` is what the engine treats it as.

Operators who want to demote a prod-looking environment (e.g. a load
test env that mirrors prod schema but holds dummy data) can set
`type='prod'` and `kind='non_prod'`. The PolicyEngine then permits
direct reveal there even though the lifecycle label says prod.

## Backfill rule

Migration `0022_environments_kind_classification` runs the only safe
automatic mapping on existing rows:

```sql
UPDATE environments SET kind = CASE
    WHEN type = 'prod' THEN 'prod' ELSE 'non_prod'
END WHERE kind IS NULL;
```

Anything labelled `type='prod'` becomes `kind='prod'`; everything
else lands in `non_prod`. Operators who labelled a true-prod
environment with a non-prod `type` MUST correct via
`PUT /api/v1/environments/:id` after running the migration.

## API surface

| Endpoint | Auth | Purpose |
|---|---|---|
| `POST /api/v1/environments` | admin | Create an env. `kind` derives from `type` when omitted. |
| `GET /api/v1/environments` | session | Flat list across projects. |
| `GET /api/v1/environments/:id` | session | Single env. |
| `PUT /api/v1/environments/:id` | admin | Update `description` + `risk_level` ONLY. `kind` and `name` are immutable post-creation. |
| `DELETE /api/v1/environments/:id` | admin | Hard delete. Cascades through env_id FKs. |
| `GET /api/v1/projects/:id/environments` | session | List per project. |

### Why kind and name are immutable

Once an environment row exists, `kind` and `name` are pinned. Two
reasons:

1. The PolicyEngine caches resolution results keyed by environment;
   flipping `kind` after a policy decision has been audited would
   create a discrepancy between the audit log and the live
   classification.
2. An operator who can flip a `prod` env to `non_prod` after grants
   exist could un-gate the direct-reveal path without anyone
   noticing. `kind` immutability + the PolicyEngine PROD invariant
   are belt-and-braces for the same threat.

Operators who need to change `kind` must DELETE + recreate. The FK
cascade through `access_requests` / `secret_wraps` / `project_secrets`
ensures no orphaned bindings survive.

## Operational checklist for new environments

1. Create the env via `POST /environments`:
   ```json
   {
     "project_id": "<uuid>",
     "name": "uat",
     "type": "uat",
     "kind": "non_prod",
     "risk_level": 1,
     "description": "Pre-production staging for the billing team."
   }
   ```
2. Bind the secrets the env should expose via
   `POST /projects/:project_id/secrets` with the new
   `environment_id` field set (Slice L3). The legacy
   `secrets.labels.Env` label is no longer the authorization key —
   `project_secrets.environment_id` is.
3. Add a `policy_rules` row scoped to this env that picks the right
   workflow. See [Policy templates](policy-templates.md) for the
   canonical shapes.
4. (Optional) Grant the `secret.reveal.direct` permission to the
   `developer` role (it's seeded by default; revoke if you want a
   stricter baseline). See
   [Authentication — direct reveal permission](authentication.md#direct-reveal-permission-slice-l4).

## Related

- [Policy templates](policy-templates.md) — non_prod / prod policy
  rule examples.
- [Authentication](authentication.md) — `secret.reveal.direct`
  permission + the L4 dev endpoints.
- API reference: `GET /users/me/projects` returns each project with
  its environments inline (Slice L4).
- [Cross-team requests](cross-team-requests.md) — Slice N split between
  the **target** (team / project / environment that provides the value)
  and the **destination** (provider connection + secret_ref where the
  value lands). Both reference the project / environment model defined
  here.
