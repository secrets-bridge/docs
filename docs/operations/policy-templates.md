# Policy templates

Slice L2 moved access decisions onto `policy_rules`. Workflows now
describe the **approval ceremony only**; policies decide **whether to
require approval**, whether to require fresh MFA, and how long a
reveal stays visible.

This page is a copy-pasteable reference for the three most common
shapes.

## Anatomy of a policy rule

```json
{
  "name": "non-prod direct reveal",
  "selector": {
    "project_id": "<uuid>",
    "environment": "uat"
  },
  "workflow_id": "<uuid>",
  "priority": 100,
  "enabled": true,
  "direct_reveal_allowed": true,
  "requires_mfa": false,
  "reveal_ttl_seconds": 120
}
```

| Field | Purpose |
|---|---|
| `selector` | Keys present must match the incoming request's scope. Absent keys are wildcards. `project_id`, `environment`, `provider_type`, and `secret_ref_prefix` are the documented dimensions. |
| `workflow_id` | Approval ceremony this scope uses (min_approvers, TTLs, …). |
| `priority` | Higher wins on overlap. The seed `match-all` rule lives at priority `0`. |
| `direct_reveal_allowed` | **Access decision** — when true AND the env is `non_prod`, the dev endpoint can bypass `access_requests` and auto-execute. The PolicyEngine zeroes this against `prod` envs regardless. |
| `requires_mfa` | When true, the matched route attaches `RequireFreshMFA` (Slice K/H5) so the user must have a recent MFA stamp. |
| `reveal_ttl_seconds` | Server-enforced reveal-session / wrap TTL. `[10, 300]` range. See [Reveal sessions](reveal-sessions.md#ttl-reveal_ttl_seconds) for the full lifecycle this knob anchors. |

## Template 1 — Non-prod direct reveal

For a `uat` environment where authorized developers can click
"Reveal" and skip approval:

```json
{
  "name": "uat-direct-reveal",
  "selector": {
    "environment": "uat"
  },
  "workflow_id": "<uat-fast-track-workflow-uuid>",
  "priority": 100,
  "enabled": true,
  "direct_reveal_allowed": true,
  "requires_mfa": false,
  "reveal_ttl_seconds": 120
}
```

Matching workflow (`min_approvers: 0`):

```json
{
  "name": "uat-fast-track",
  "min_approvers": 0,
  "allow_self_approval": true,
  "wrap_ttl_created_seconds": 86400,
  "wrap_ttl_approved_seconds": 3600,
  "wrap_ttl_claimed_seconds": 300,
  "request_ttl_seconds": 604800,
  "require_justification": true,
  "enabled": true
}
```

Notes:

- The dev endpoint `POST /projects/:id/environments/:env_id/direct-reveal`
  checks `environment.kind != 'prod'` BEFORE the policy lookup.
  Setting `direct_reveal_allowed=true` on a rule whose selector
  matches a `kind='prod'` env is harmless: the engine zeroes the
  flag in the decision and emits a `policy.invariant.violated`
  audit event.
- The user still needs the `secret.reveal.direct` permission
  (seeded onto the `developer` role by migration `0026`).
- `reveal_ttl_seconds` is the upper bound for the wrap's lifetime
  on disk. Tighter is safer; PRD §15 recommends 120 s for non-prod.

## Template 2 — Production single-approver

For a `prod` environment where any one approver can sign off:

```json
{
  "name": "prod-single-approver",
  "selector": {
    "environment": "prod"
  },
  "workflow_id": "<prod-single-workflow-uuid>",
  "priority": 200,
  "enabled": true,
  "direct_reveal_allowed": false,
  "requires_mfa": true,
  "reveal_ttl_seconds": 60
}
```

Matching workflow:

```json
{
  "name": "prod-single",
  "min_approvers": 1,
  "allow_self_approval": false,
  "wrap_ttl_created_seconds": 86400,
  "wrap_ttl_approved_seconds": 1800,
  "wrap_ttl_claimed_seconds": 120,
  "request_ttl_seconds": 259200,
  "require_justification": true,
  "enabled": true
}
```

Notes:

- `requires_mfa: true` means the api attaches the
  `RequireFreshMFA` middleware (Slice H5/K) to the submit + reveal
  routes — the SPA's step-up modal opens automatically when the
  user's MFA stamp is stale.
- `reveal_ttl_seconds: 60` matches the PRD default for production.

## Template 3 — Production multi-approver chain

For a high-risk env that needs source-team head + security:

```json
{
  "name": "prod-multi-approver",
  "selector": {
    "environment": "prod",
    "secret_ref_prefix": "billing/"
  },
  "workflow_id": "<prod-multi-workflow-uuid>",
  "priority": 300,
  "enabled": true,
  "direct_reveal_allowed": false,
  "requires_mfa": true,
  "reveal_ttl_seconds": 60
}
```

Matching workflow:

```json
{
  "name": "prod-multi",
  "min_approvers": 2,
  "allow_self_approval": false,
  "wrap_ttl_created_seconds": 86400,
  "wrap_ttl_approved_seconds": 1800,
  "wrap_ttl_claimed_seconds": 120,
  "request_ttl_seconds": 172800,
  "require_justification": true,
  "enabled": true
}
```

The `secret_ref_prefix` selector key is a **prefix match** — every
ref starting with `billing/` falls into this rule. Combine with
`environment: "prod"` to scope it tightly.

Slice N (cross-team integration workflow) adds an explicit
"Security approval" step as the third approver in this chain via the
new `workflow_definitions.requires_security_approval` knob — see
[Cross-team workflows](#template-4-cross-team-workflows) below.

## Template 4 — Cross-team workflows

Cross-team requests carry their own workflow shape: Team B fills, an
optional security approver verifies, then the agent writes. Two new
`workflow_definitions` knobs configure this:

| Knob | Default | Use |
|---|---|---|
| `fill_ttl_seconds` | `86400` (24h) | How long Team B has to fill before the request expires. |
| `requires_security_approval` | `false` | When `true`, a `secret.security.approve` vote is needed in addition to source approval. |

`min_approvers` for cross-team workflows is constrained to `{0, 1}`
in v1; the submit endpoint refuses `≥ 2` with
`cross_team_min_approvers_unsupported`.

### Non-prod cross-team template

```sql
INSERT INTO workflow_definitions (name, min_approvers, fill_ttl_seconds, requires_security_approval, ...)
VALUES ('cross-team-non-prod', 1, 86400, false, ...);

INSERT INTO policy_rules (selector, workflow_id, priority)
VALUES (
  '{"environment_kind":"non_prod","type":"cross_team"}'::jsonb,
  (SELECT id FROM workflow_definitions WHERE name = 'cross-team-non-prod'),
  100
);
```

### PROD cross-team template

```sql
INSERT INTO workflow_definitions (name, min_approvers, fill_ttl_seconds, requires_security_approval, ...)
VALUES ('cross-team-prod', 1, 43200, true, ...);

INSERT INTO policy_rules (selector, workflow_id, priority)
VALUES (
  '{"environment_kind":"prod","type":"cross_team"}'::jsonb,
  (SELECT id FROM workflow_definitions WHERE name = 'cross-team-prod'),
  100
);
```

The 12h fill window is intentional: PROD requests should not sit in
limbo overnight; the shorter TTL forces escalation rather than silent
expiry.

See [Cross-team requests](cross-team-requests.md) for the full state
machine, SoD matrix, and triage SQL.

## Hard rules

| Rule | Where enforced |
|---|---|
| **PROD direct reveal is impossible.** | PolicyEngine zeroes `direct_reveal_allowed=true` when scope's `environment.kind == 'prod'`. Audit event `policy.invariant.violated` records the misconfig. |
| **`reveal_ttl_seconds` ∈ [10, 300].** | Schema CHECK constraint + handler-level validation. |
| **`kind` and `name` on environments are immutable post-creation.** | See [Project environments](project-environments.md#why-kind-and-name-are-immutable). |
| **The `secret.reveal.direct` permission is necessary but not sufficient.** | The matched policy must also have `direct_reveal_allowed=true` AND the env's `kind` must be `non_prod`. |

## Related

- [Project environments](project-environments.md) — the
  `kind`/`risk_level`/`description` model these policies key off.
- [Authentication](authentication.md) — `secret.reveal.direct`
  permission and the dev endpoints that consume policy decisions.
- [Cross-team requests](cross-team-requests.md) — the Slice N flow
  the cross-team templates above target.
