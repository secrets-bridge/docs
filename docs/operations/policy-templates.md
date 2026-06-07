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

## Scoped policy authoring (`policy.author`)

EPIC R (api#108) splits policy authoring along the same line EPIC Q
split provider-connection binding. Platform retains full control via
the existing `policy.edit` permission + the `/admin/policies` URL
family. Section heads grant their teams scoped authority to write
**non-prod** policy rules for their **own projects** without ever
holding `policy.edit`.

The two permissions are deliberately disjoint — neither auto-covers
the other, server-side or in the SPA. Operators grant `policy.author`
explicitly via the seeded `policy_author` role.

### `policy_rules.project_id` — the scoping column

Migration 0033 adds a nullable scoping column:

```sql
ALTER TABLE policy_rules
    ADD COLUMN project_id UUID NULL REFERENCES projects(id) ON DELETE CASCADE;
```

- **`project_id IS NULL`** → platform-owned rule. Only `policy.edit`
  can write it via `/admin/policies`. Survives across every project.
- **`project_id = <uuid>`** → scoped rule. Authored by a `policy.author`
  holder via `/api/v1/projects/:projectID/policy-rules`. Visible only
  to that project's resolution path.

Two CHECK constraints back the contract:

```sql
-- selector.project_id, when present, must equal the row's column
policy_rules_selector_project_matches_column

-- scoped rules MUST carry an env constraint that resolves non-prod
policy_rules_scoped_requires_env
```

The DB rejects scoped rows that don't carry either
`selector.environment_kind='non_prod'` or `selector.environment_id`.
Service-layer validation runs ahead of the CHECK and adds the
`environment_id → env.kind = non_prod` JOIN check that a constraint
can't express.

### Hard rules for scoped authors

| Rule | What rejects it |
|---|---|
| Coverage — `EffectiveProjectAccess(policy.author, projectID)` must succeed | Service gate 1 → `out_of_scope_policy` (403) |
| Priority `< 9000` (platform reserved band) | Service gate 2 → `policy_priority_reserved` (400) with `{"cap": 9000}` |
| Empty `{}` selector REJECTED | Service gate 4 → `policy_scope_too_broad` (400) with `{"reason": "selector_empty"}` |
| `selector.environment_kind = "non_prod"` OR `selector.environment_id` set | Service gate 4 → `policy_scope_too_broad` (400) with `{"reason": "env_constraint_missing"}` |
| `selector.environment_id` belongs to URL projectID | Service gate 4 → `policy_environment_not_in_project` (400) |
| `selector.environment_id.kind = "non_prod"` (JOINed at write time) | Service gate 4 → `prod_policy_not_allowed_for_scope` (403) with `{"env_kind": "prod"}` |
| `selector.environment_kind` + `selector.environment_id` agree when both present | Service gate 4 → `policy_scope_too_broad` (400) with `{"reason": "env_kind_id_inconsistent"}` |
| `selector.project_id`, when present, equals URL projectID | Service gate 3 → `policy_selector_mismatch` (400) |
| Cannot edit platform NULL rules via the scoped URL | Service gate 4 (Update/Delete) → `platform_policy_not_editable` (403) |
| Cannot edit `is_system` rules | Service gate 5 (Update/Delete) → `ErrSystemRow` → `platform_policy_not_editable` (403) |

### `policy.edit` does NOT auto-cover `policy.author`

A deliberate design choice. Operators must explicitly grant the
`policy_author` role (or a custom role carrying `policy.author`) to
section heads. Platform admins holding `policy.edit` keep using
`/admin/policies` for global rules — they do NOT auto-trip into the
scoped URL family.

The SPA enforces the same split:

- Sidebar entry "Project policies" → gated on `policy.author` only
- Page CTA `+ Author rule` → gated on `policy.author`
- Empty-state shortcut "Manage at /admin/policies" → visible only to
  `policy.edit` holders (so platform engineers wandering onto a
  project's policies page see the right escape hatch)

### `policy_author` seed role

Migration 0034 seeds the system role:

```sql
INSERT INTO roles (name, description, permissions, is_system)
VALUES (
    'policy_author',
    'Author project-scoped policy rules for non-prod environments...',
    '["policy.author"]'::jsonb,
    true
);
```

Assign it scoped to a project or team:

```bash
# Per-project — section head covers exactly one project
curl -X POST /api/v1/user-roles \
  -d '{"user_id":"alice","role_id":"<policy_author>","scope":{"project_id":"<billing-prod>"}}'

# Per-team — section head covers the entire descendant team subtree
curl -X POST /api/v1/user-roles \
  -d '{"user_id":"alice","role_id":"<policy_author>","scope":{"team_id":"<billing-team>"}}'
```

The team-aware resolver walks `team_id` → descendant subtree →
covered projects. A section head's grant on the parent team
automatically extends to child teams as the org grows.

### Capability helper pattern in the SPA

The SPA's `src/auth/capabilities.ts` exposes three pure helpers that
mirror the same `via` field EPIC Q established. The `via` answers
"which permission carried this action?" so the caller picks the right
endpoint family:

| Helper | Returns | Drives |
|---|---|---|
| `canAuthorProjectPolicy(perms, project)` | `{allowed, via, reason}` | `+ Author rule` CTA visibility on the project page |
| `canEditPolicyRule(perms, rule)` | `{allowed, via, reason}` | Delete action visibility on a per-row basis. Returns `{allowed: false, reason: 'platform_owned'}` for inherited platform rules (`is_platform_inherited=true`) regardless of perms — even admins use `/admin/policies` for them. |
| `canManagePlatformPolicy(perms)` | `boolean` | Empty-state "Manage at /admin/policies" shortcut visibility |

Generic `hasPermission('policy.author')` keeps its strict semantic
everywhere else. The capability helpers do NOT call `useAuth` —
they're pure functions taking the actor's `permissions` array, which
keeps them testable.

### Triage SQL

**1. Active scoped rules per project (inventory)**

```sql
SELECT p.name AS project, pr.name AS rule, pr.priority, pr.workflow_id, pr.enabled
FROM policy_rules pr
JOIN projects p ON p.id = pr.project_id
WHERE pr.project_id IS NOT NULL
ORDER BY p.name, pr.priority DESC;
```

**2. Recent `policy.denied_out_of_scope` events (security signal)**

```sql
SELECT actor, occurred_at,
       metadata->>'attempted_project_id' AS attempted_project,
       metadata->>'actor_permission_attempted' AS perm
FROM audit_events
WHERE action = 'policy.denied_out_of_scope'
  AND occurred_at > now() - interval '7 days'
ORDER BY occurred_at DESC
LIMIT 100;
```

**Note** the deliberate absence of `policy_rule_id` from the metadata
— this is the §6 gate-order enumeration-leak protection. The denied
event fires BEFORE the rule is loaded; including the id would defeat
the protection. (Same lesson EPIC Q's `binding.denied_out_of_scope`
learned.)

**3. 7-day scoped vs admin authoring breakdown**

```sql
SELECT date_trunc('day', occurred_at) AS day,
       metadata->>'actor_permission_used' AS perm,
       count(*) AS n
FROM audit_events
WHERE action IN ('policy.create','policy.update','policy.delete')
  AND occurred_at > now() - interval '7 days'
GROUP BY day, perm
ORDER BY day DESC, perm;
```

**4. Per-actor policy activity (incident response)**

```sql
SELECT occurred_at, action, resource,
       metadata->>'actor_permission_used' AS perm,
       metadata->>'project_id' AS project,
       metadata->'selector_keys' AS selector_keys
FROM audit_events
WHERE actor = 'alice'
  AND action LIKE 'policy.%'
ORDER BY occurred_at DESC
LIMIT 200;
```

`selector_keys` carries only the KEY names — the §6 lock keeps
selector VALUES out of the audit log entirely. If you need to know
what `secret_ref_prefix` a scoped author pinned, look at the rule
row directly (it's not exfiltrated through audit).

### Operator playbook

**Grant a section head policy authoring capability**

1. Identify the project (or parent team) they cover.
2. POST `/api/v1/user-roles` with `role_id = <policy_author>` and
   `scope` = `{"project_id": "..."}` OR `{"team_id": "..."}`.
3. They get a sidebar "Project policies" entry on next page load.
4. They land on `/projects/:id/policies` (auto-routed if they cover
   exactly one project; picker if multiple).

**Audit recent self-service activity**

Run triage SQL #3 weekly. A sudden spike in `policy.author` events
on a project with no recent app changes is worth a check-in — could
be experimentation, could be an attacker who phished a section head.
The `policy.denied_out_of_scope` events (triage SQL #2) are the
canary for someone probing without coverage.

**Revoke a section head's `policy.author` without touching their existing rules**

```bash
# Find the grant
curl /api/v1/users/<user_id>/roles

# Revoke
curl -X DELETE /api/v1/user-roles/<assignment_id>
```

The rules they authored stay in `policy_rules` — they're still owned
by the project, not the actor. New rules require a fresh grant; existing
rules can be edited/deleted by another covered actor or by
`policy.edit` admin via `/admin/policies`.

**Diagnose "my scoped rule isn't taking effect"**

Walk the priority band. Platform `policy.edit` rules have priority
`>= 9000`. Scoped rules are bounded `< 9000`. If a platform rule
overlaps the scoped selector at higher priority, platform wins by
design. Triage SQL #1 shows the active rules per project; cross-check
priorities against the `/admin/policies` admin view.

### Observability — Prometheus counters

Four counters, all locked to LOW-CARDINALITY labels. Operator
shouldn't try to derive per-actor or per-rule rates from these —
those live in the audit log.

```
policy_rules_created_total{permission_used, scope}
policy_rules_updated_total{permission_used, scope}
policy_rules_deleted_total{permission_used, scope}
policy_rules_denied_total{reason}
```

- `permission_used` ∈ `{policy.author, policy.edit}` — tracks which
  surface ran the mutation.
- `scope` ∈ `{platform, project}` — `project` for scoped rules,
  `platform` for global rules (admin path adds the label as future
  work; today admin path doesn't emit these counters).
- `reason` is a fixed 8-element set: `out_of_scope`, `platform_owned`,
  `prod_blocked`, `scope_too_broad`, `priority_reserved`,
  `selector_mismatch`, `env_not_in_project`, `not_found`.

**LOW-CARDINALITY LOCK**: counters NEVER carry `actor_id`,
`project_id`, `policy_rule_id`, or `workflow_id` labels. Same posture
as EPIC Q's binding counters. The audit log is where operators look
those up.

### Error code reference

| Code | Status | Meaning | Envelope extras |
|---|---|---|---|
| `policy_not_found` | 404 | Rule doesn't exist OR exists under a different project (the §4 mismatch protection — never leak existence under another parent) | — |
| `platform_policy_not_editable` | 403 | Scoped caller tried to edit a NULL `project_id` row OR an `is_system` row via the scoped URL family | — |
| `out_of_scope_policy` | 403 | Caller's `policy.author` grant doesn't cover the target project per the team-aware resolver | — |
| `policy_selector_mismatch` | 400 | `selector.project_id` was set but doesn't equal URL projectID | — |
| `prod_policy_not_allowed_for_scope` | 403 | Scoped caller tried to author a rule that resolves to a prod env | `{"env_kind": "prod"}` |
| `policy_scope_too_broad` | 400 | Selector doesn't satisfy the non-prod-by-construction invariant | `{"reason": "env_constraint_missing"\|"env_kind_invalid"\|"selector_empty"\|"env_kind_id_inconsistent"}` |
| `policy_priority_reserved` | 400 | Priority `>= 9000` requested; reserved for platform | `{"cap": 9000}` |
| `policy_environment_not_in_project` | 400 | `selector.environment_id` doesn't belong to URL projectID | — |

The SPA's `src/api/policyErrors.ts` ships `toPolicyRuleErrorToast(err)`
which surfaces the `policy_scope_too_broad.reason` variants + the
`policy_priority_reserved.cap` value with concrete user-facing
strings. Per EPIC R §5 correction 1 this lives in its own module —
deliberately separate from `providerConnections.ts`'s
`providerConnectionErrorMessage`.

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
  the cross-team templates above target, and how scoped policy
  authoring participates in cross-team workflow resolution.
- [Permissions catalog — `policy.author`](../reference/permissions.md#workflows)
- [HTTP API endpoints — Project-anchored scoped policy rules](../reference/api-endpoints.md#project-anchored-scoped-policy-rules-epic-r-api108)
