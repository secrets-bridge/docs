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
| Priority `< platform_reserved_priority` (default `9000`, admin-configurable per R-follow-up #2) | Service gate 2 → `policy_priority_reserved` (400) with `{"cap": <live-value>}` |
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

**5. Recent `policy.denied_workflow_not_authorable` events (R-follow-up #1)**

```sql
SELECT actor, occurred_at,
       metadata->>'attempted_workflow_id' AS attempted_workflow,
       metadata->>'attempted_project_id' AS attempted_project,
       metadata->>'actor_permission_attempted' AS perm
FROM audit_events
WHERE action = 'policy.denied_workflow_not_authorable'
  AND occurred_at > now() - interval '7 days'
ORDER BY occurred_at DESC
LIMIT 100;
```

**Audit metadata differences** from `policy.denied_out_of_scope`:

- `attempted_workflow_id` IS included. The actor picked the workflow
  from the dropdown they were just shown; logging the id is fine for
  triage and isn't a leak.
- `policy_rule_id` is DELIBERATELY absent. The gate fires BEFORE
  the rule is INSERTed (Create path) or BEFORE the UPDATE runs
  (Update path) — including the id would defeat the same gate-order
  protection EPIC Q's `binding.denied_out_of_scope` and EPIC R's
  `policy.denied_out_of_scope` apply.

Use this query to spot a scoped author repeatedly trying to use a
workflow platform has deliberately walled off. If `attempted_workflow_
id` is the same across many rows for one actor, it's worth a
conversation — they probably need that workflow opted in, or they
need pointed at the alternatives.

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
`>= platform_reserved_priority` (default `9000`, admin-configurable
per R-follow-up #2). Scoped rules are bounded
`< platform_reserved_priority`. If a platform rule overlaps the
scoped selector at higher priority, platform wins by design. Triage
SQL #1 shows the active rules per project; cross-check priorities
against the `/admin/policies` admin view.

### Curating workflows for scoped authoring

R-follow-up #1 ([api#112](https://github.com/secrets-bridge/api/issues/112))
adds the `workflow_definitions.scoped_policy_authorable` flag so
platform admin curates which workflows scoped authors see in their
`/projects/:id/policies` author drawer. Default-deny: every workflow
is invisible to scoped authors until explicitly opted in.

#### What the flag does

| `scoped_policy_authorable` | Effect |
|---|---|
| `false` (default) | Workflow stays admin-only. `/admin/workflows` still shows it; `/admin/policies` admin can still use it for global rules. Scoped authors at `/projects/:id/policies` do NOT see it in their dropdown, and trying to use it via API returns 403 `workflow_not_authorable_for_scope`. |
| `true` | Workflow appears in the scoped author drawer's workflow dropdown. Admin can still use it through `/admin/policies` exactly as before. |

#### Opting a workflow in (admin SPA)

`/admin/workflows` → open the workflow you want to expose → scroll
to the **"Scoped author access"** section at the bottom of the form
→ tick **"Available for scoped policy authoring"** → Save. A small
`[scoped]` chip appears on the workflow's row in the admin list.

Any open author drawer on `/projects/:id/policies` sees the new
workflow within ~30 seconds without a page reload — both the admin
workflow list cache key AND the scoped author dropdown cache key are
invalidated on every workflow mutation.

#### Opting a workflow in (API)

```bash
# Get the workflow id
gh api .../api/v1/workflows | jq '.[] | select(.name=="standard") | .id'

# Flip the flag — Get-then-merge in the api preserves all other fields
curl -X PUT /api/v1/workflows/<id> \
  -H 'Authorization: Bearer <jwt>' \
  -H 'Content-Type: application/json' \
  -d '{"scoped_policy_authorable": true}'
```

The api's `UpdateWorkflow` does a Get-then-merge when fields are
omitted, so a partial PUT body only touches what it carries. Send
`false` to opt out; OMIT to preserve. **Never send the literal value
`false` to a workflow you don't want to change** — that's a
no-op-looking write that flips the flag off.

#### Grandfathering existing rules on opt-out

When platform admin opts a workflow OUT after scoped authors have
already used it, EXISTING rules referencing that workflow KEEP
working. The §1 Q4 grandfather rule on the api side enforces this:

- A scoped author can still UPDATE priority / selector / name /
  enabled state on rules attached to the now-opted-out workflow.
- A scoped author CAN'T attach the rule to a different workflow that
  ISN'T also opted in — `UpdateForScopedAuthor` runs the authorable
  check whenever `workflow_id` changes.
- A scoped author CAN'T CREATE a NEW rule on the now-opted-out
  workflow — `CreateForScopedAuthor` runs the check unconditionally.

This means an admin opting a workflow out doesn't break any pending
policy work; new authoring on that workflow simply stops until it's
opted back in.

#### Rolling deploy safety

The flag landed in api migration 0035. Admin clients that don't yet
know about the field (older SPA build during rolling deploy) keep
working: the api's UpdateWorkflow preserves the flag on PUT bodies
that omit it (Get-then-merge), and the SPA's new WorkflowForm tracks
both the loaded value AND whether the admin TOUCHED the checkbox —
PUT body only includes the field when one of those is true. Either
side acting alone is safe.

### Adjusting the reserved priority band

R-follow-up #2 ([api#113](https://github.com/secrets-bridge/api/issues/113))
made the platform-reserved priority band admin-configurable. The cap
that used to live as the hardcoded constant `PlatformReservedPriority
= 9000` is now a row in the `platform_settings` table seeded with
`{"value": 9000}` on first boot; admin edits it without a redeploy.

#### What the cap controls

| Code path | Behavior |
|---|---|
| Service gate 2 (Create + Update) | Rejects priorities `>= cap` with `policy_priority_reserved` (400); envelope carries the live `cap`. |
| `policy_rules` envelope (SPA Author drawer) | Reads `priority_cap` from `GET /api/v1/projects/:id/policy-rules` so the drawer's "Priority (< N — platform reserved)" label reflects the live value at page load. |
| Author drawer Zod schema | Built from the live cap at mount — the `< cap` validation rejects values at or above whatever admin has flipped to right now. |

#### Editing through the SPA (admin)

`/admin/platform-settings` → **Scoped policy reserved priority** card →
**Edit** → enter the new value (whole number between `100` and
`1,000,000`) → **Save**.

The confirm modal carries a grandfathering warning + an inline triage
SQL block that previews which scoped rules would land in the
grandfathered band BEFORE you confirm. **Lowering the cap is
grandfathered** — see the next subsection.

The change propagates to every api pod within seconds via the Redis
pub/sub channel `secrets-bridge:platform_settings:platform_reserved_priority`.
Subscribers do NOT trust the published payload — they re-fetch the
row from the database on every notification, so a malicious or
malformed publish can't poison the cache. A 5-minute TTL backstop
catches dropped notifications.

#### Editing through the API

```bash
curl -X PUT /api/v1/platform-settings/platform_reserved_priority \
  -H 'Authorization: Bearer <jwt>' \
  -H 'Content-Type: application/json' \
  -d '{"value": 10000}'
```

Permission: `policy.edit`. Bounds: `100 ≤ value ≤ 1,000,000`, whole
numbers only. Out-of-bounds and non-integer JSON return
`invalid_platform_setting` (400) with `{"min": 100, "max": 1000000}`
in the envelope.

#### The grandfather rule

Lowering the cap does NOT auto-delete scoped rules that now sit in
the platform-reserved band. **Existing rows keep their priorities;
they continue to apply.** What changes is:

- New scoped Create requests with `priority >= new_cap` are rejected.
- Scoped Update requests are revalidated against the new cap on every
  call (NOT just when priority is changing) — bumping any other field
  on a rule whose priority sits in the grandfathered band is rejected
  with `policy_priority_reserved`.
- Platform admins editing through `/admin/policies` are unaffected;
  their permission is `policy.edit`, not the scoped path.

This means admin can lower the cap to close off a band without
breaking pending authoring work — existing rules continue to apply
while authors migrate to lower priorities.

#### Triage SQL — list scoped rules in the grandfathered band

```sql
SELECT id, name, priority, project_id
  FROM policy_rules
 WHERE is_platform_inherited = false
   AND priority >= <new_cap>
 ORDER BY priority ASC;
```

The confirm modal in the SPA admin page embeds this exact query with
the proposed `<new_cap>` substituted so an operator can sanity-check
before saving.

#### Fail-closed when the settings cache is unavailable

If the SettingsService cache reload fails (Postgres outage, KMS
unavailability cascading through), service gates fall closed: scoped
Create and Update return `platform_setting_unavailable` (503). The
Author drawer renders a disabled form with a red banner explaining
that authoring stays disabled until the cap is readable — falling
back to a stale value would let scoped rules into the
platform-reserved band.

#### Observability

- `platform_setting_updates_total{key, result}` — counter for admin
  edit attempts. `result` ∈ `{ok, invalid, unavailable, conflict}`.
- `platform_setting_cache_reloads_total{key, trigger}` — counter for
  cache reloads. `trigger` ∈ `{boot, pubsub, on_demand}`.

LOW-CARDINALITY LOCK: counters NEVER carry actor identity. The audit
events `platform_setting.updated` carry the actor + old/new values.

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
- `reason` is a fixed 9-element set: `out_of_scope`, `platform_owned`,
  `prod_blocked`, `scope_too_broad`, `priority_reserved`,
  `selector_mismatch`, `env_not_in_project`, `not_found`,
  `workflow_not_authorable` (R-follow-up #1, api#112).

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
| `policy_priority_reserved` | 400 | Priority at or above the platform-reserved band requested. The cap is admin-configurable per R-follow-up #2 (default `9000`); the envelope echoes the live value. | `{"cap": <live-value>}` |
| `policy_environment_not_in_project` | 400 | `selector.environment_id` doesn't belong to URL projectID | — |
| `workflow_not_authorable_for_scope` | 403 | Scoped caller picked a workflow that platform admin hasn't opted into the scoped author surface (R-follow-up #1, api#112). Distinct from `platform_policy_not_editable`: the workflow exists and is admin-usable; it just isn't exposed to scoped authors yet. | `{"workflow_id": "<uuid>"}` |

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
