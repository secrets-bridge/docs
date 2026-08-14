---
title: "Teams and section heads"
description: "Model an org as an N-level team tree and grant role scopes that fan out through the subtree."
---

# Teams and section heads

Most organisations don't fit cleanly into a flat list of projects. A
real engineering org has sections, sub-teams, leads, and members, and
the people at each level need access to *their part of the world*, no
more and no less. The platform models this with a first-class **team
tree**: an N-level hierarchy where role grants scoped to a team
automatically fan out through that team's entire subtree.

## The model

Three entities, one rule.

### `teams`: the tree

Each team carries a name, optional description, status (`active` /
`archived`), and a nullable `parent_team_id`. Root teams have no
parent; everything else is a descendant. The depth is N. The schema
doesn't impose a limit.

```text
acme
├── platform
│   ├── platform-east
│   └── platform-west
└── security
    └── security-compliance
```

Sibling names must be unique under the same parent. `acme/platform/ops`
and `acme/security/ops` are both fine; two `ops` under `acme/platform`
are not. The constraint is per-parent, so renaming or re-parenting
never breaks cousins.

A team cannot be deleted while it has children; unparent or delete
those first. `team_members` rows cascade-delete with the team they
belong to (the user account stays; only the membership row goes).

### `team_members`: who belongs

A simple `(team_id, user_id)` join. **Structural only**: membership
does NOT grant any permission on its own. The platform deliberately
keeps "who you are" and "what you can do" in two tables so you can
reorganise teams without rewriting RBAC.

### Role grants scoped to a team

The connecting tissue. A row in `user_roles` carries a `scope` JSON
object; setting `scope.team_id = <team>` tells the access resolver
*"this grant applies to that team's entire subtree"*.

```json
{
  "user_id": "alice",
  "role_id": "<approver-role>",
  "scope": { "team_id": "acme/platform" }
}
```

Alice is now an approver for everything inside `platform` and every
descendant team. She can approve `platform-east` and `platform-west`
requests, and requests for a new sub-team created under `platform`
tomorrow, with no follow-up grant needed.

## The "section head" pattern

A common shape this model unlocks:

1. **Build the tree** under `/admin/teams`. Reflect your org chart:
   a top-level team per section, child teams per squad, grandchild
   teams if you have feature pods.
2. **Assign projects to teams** by setting `project.team_id` on
   create (or via `PUT /projects/:id/team` after). This is the wiring
   that lets the access resolver expand a team-scoped grant into a
   set of accessible projects.
3. **Grant the section head** on `/admin/assignments`: pick the user,
   pick the role (`secret.approve` for an approver, `secret.list +
   secret.request` for a developer-style lead), and pick the section
   team in the Team dropdown. Leave Project unset; the team scope
   makes it implicit.

That single grant produces this behaviour:

| The section head's view | How it works |
|---|---|
| `/secrets` shows every secret bound to every project under their section | `EffectiveProjectAccess` expands `team_id` → descendant teams (recursive CTE) → projects with `team_id` in that set |
| `/requests` lists requests from any project under their section | Same expansion, filtered server-side |
| Approve / Reject works for any of those requests | The approve gate runs `checkApproverScope` with the same resolver |
| Approve / Reject **refuses** on any request OUTSIDE their subtree | Returns 403 with the stable string `out_of_scope_project` |
| New sub-team added later under their section | Auto-covered, no follow-up grant |
| Project re-assigned to a different team | Auto-shifts in/out of scope, no manual cleanup |

## How requests respect the scope

The check fires at submit time AND at approve time, on top of the
normal `secret.list` / `secret.request` / `secret.approve` permission
check:

- **Submit gate**: `Requests.WithTenancyGate` validates the caller's
  `secret.request` grants cover the request's `project_id`, op is in
  the binding's `allowed_ops`, and every requested key is in
  `allowed_keys` (when non-null). Stable errors:
  `out_of_scope_project`, `out_of_scope_op`, `out_of_scope_key`.
- **Approve gate**: `checkApproverScope` validates the voter's
  `secret.approve` grants cover the request's `project_id`. Same
  team-subtree expansion as the submit gate.

Both gates have the same back-compat behaviour: legacy requests whose
`TargetScope["project_id"]` isn't a UUID bypass the team check (so
installs without scoped projects keep working byte-for-byte).

## How the UI uses this

The SPA hydrates a single `/users/me` call after login:

```json
{
  "id":           "<uuid>",
  "email":        "alice@example.com",
  "display_name": "Alice",
  "permissions":  ["secret.list", "secret.request", "secret.approve", "..."],
  "teams":        [{"id":"...","name":"platform","parent_team_id":null,"status":"active"}],
  "projects":     [{"id":"...","name":"Billing","status":"active"}]
}
```

- **Sidebar** items gate on the `permissions` array. The admin
  section hides entirely if no admin permission is held; individual
  nav items hide if their gating permission is missing.
- **`/secrets`** is filtered server-side to only the projects in
  `projects` (or every project if the caller holds a global grant).
- **Submit drawer** defaults to *"From my bindings"* mode for scoped
  users: pick a project from `projects`, pick one of its bound
  secrets, the form auto-fills provider type + ref + the allowed-ops
  / allowed-keys constraints. Admins (holders of `team.edit`) start
  on the free-form mode for onboarding new bindings.
- **`/me`** profile page renders the full payload: identity, the
  permission set, direct team memberships, and the accessible
  projects, all read from the same `AuthContext`.

Permission gating is strictly **fail-closed**: until `/users/me`
returns, `hasPermission(...)` is `false` for every key. A session
restored from `sessionStorage` shows the Dashboard + a *"Loading
permissions…"* line while the request is in flight; there is no
flash of admin nav for non-admins on rehydration.

## Practical advice

- **Keep teams shallow when you can.** Two or three levels covers
  most orgs. The recursive CTE handles depth N just fine, but a
  flatter tree is easier for admins to reason about.
- **Don't reuse `team_members` as a permission system.** Membership
  is structural metadata. Always grant capabilities via a role +
  scope.
- **Archive instead of delete** when a team is being wound down. The
  status flag preserves audit trails: requests filed against
  projects in an archived team subtree still resolve. Delete only
  when the team is truly empty and the historical references are no
  longer interesting.
- **A grant can target both `project_id` and `team_id`** in the same
  scope object. The resolver computes the union, so a user can be
  "the section head over `platform`" PLUS "co-owner of one specific
  project in `security`" via two separate grant rows or one combined
  scope.
- **Free-form mode in the submit drawer still works.** It's the
  default for admins, who are usually the ones submitting the first
  request against a brand-new binding. The api-side gate is the same
  in both modes; bound mode is a UX overlay that keeps scoped users
  from constructing requests that would 403.
