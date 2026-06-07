# Permissions catalog

The canonical list of permission strings used by `auth.Require(perm)`.

Source: [`api/internal/auth/permissions.go`](https://github.com/secrets-bridge/api/blob/main/internal/auth/permissions.go).
The api also serves the live catalog at
`GET /api/v1/permissions` (with descriptions), cached for 5
minutes — the UI's Roles admin page hydrates from there so the
chip picker stays in sync with what the api actually understands.

## Seed roles

Three roles ship as system seeds (migration 0005). Operators can
edit their permission lists but can't delete the rows.

| Role | Permissions | Notes |
|---|---|---|
| `admin` | `role.edit`, `user_role.edit`, `workflow.edit`, `policy.edit`, `agent.mint`, `agent.revoke`, `secret.request`, `secret.approve`, `audit.read` | |
| `approver` | `secret.approve`, `audit.read` | |
| `developer` | `secret.request`, `secret.reveal.direct`, `audit.read` | |
| `value_provider` | `secret.value.provide` | Slice N seed — used for the [cross-team flow](../operations/cross-team-requests.md). Assignment **must** carry a `team_id` scope; the Assignments form gates global grants behind a type-to-confirm. |
| `security_approver` | `secret.security.approve` | Slice N seed — holder can cast the security vote on cross-team requests where the bound workflow has `requires_security_approval=true`. |
| `provider_connection_binder` | `integration.bind` | EPIC Q seed — section-head capability for [self-service provider connection binding](../operations/provider-connections.md#scoped-bindings-integrationbind). Assignment carries a `team_id` (covers descendant project subtree) or `project_id` (one project) scope. **Not** auto-granted to `integration.edit` holders — operators grant explicitly. |
| `policy_author` | `policy.author` | EPIC R seed (api#108) — section-head capability for [scoped non-prod policy authoring](../operations/policy-templates.md#scoped-policy-authoring-policyauthor). Assignment carries `team_id` or `project_id` scope. **Not** auto-granted to `policy.edit` holders — operators grant explicitly. Scoped rules are bounded `priority < 9000` (the platform-reserved band) and rejected against any selector that resolves to a prod environment. |

## Catalog by group

### RBAC

| Permission | Description |
|---|---|
| `role.edit` | Create / update / delete roles. |
| `user_role.edit` | Grant / revoke role assignments to users. |

### Workflows

| Permission | Description |
|---|---|
| `workflow.edit` | Create / update / delete workflow definitions. |
| `policy.edit` | Create / update / delete policy rules. Global scope — affects every project's resolution. Does NOT auto-cover `policy.author` server-side (EPIC R, api#108) — operators grant scoped authoring explicitly via the `policy_author` system role. |
| `policy.author` | Author project-scoped policy rules for non-prod environments (EPIC R, api#108). Scoped via the existing team-aware resolver. Refuses prod env selectors, priority `>= 9000` (platform reserved), and edits to platform global rules. Granted via the `policy_author` system seed role. |

### Agents

| Permission | Description |
|---|---|
| `agent.mint` | Mint a new agent identity and return its credentials. |
| `agent.revoke` | Revoke an agent — heartbeats stop being accepted. |
| `agent.list` | (Reserved) List agents in the projection — today this is open to any signed-in user. |

### Secrets

| Permission | Description |
|---|---|
| `secret.request` | Submit a read or patch request. |
| `secret.approve` | Vote on a pending request (approve or reject). |
| `secret.reveal.direct` | (Slice L4) Eligibility for the auto-executed direct-reveal path. The matched `policy_rules` row MUST ALSO have `direct_reveal_allowed=true` AND the environment's `kind` must be `non_prod`. Without all three, the user is routed through the standard request flow. PROD direct-reveal is impossible by construction. |
| `secret.value.provide` | (Slice N) Holder appears in the [cross-team inbox](../operations/cross-team-requests.md) for the team scoped on the grant and can fill cross-team requests targeting it. **Team-scoped**: the grant carries `team_id` in `user_roles.scope`. The SPA sidebar's Inbox entry is fail-closed on this permission. |
| `secret.security.approve` | (Slice N) Holder can cast the security vote on cross-team requests where the bound workflow has `requires_security_approval=true`. **Global in v1**; per-project / per-environment scoping is deferred. Adding this permission to a role triggers a type-to-confirm gate in the SPA Roles editor. |

### Observability

| Permission | Description |
|---|---|
| `audit.read` | Read the immutable audit event log. |

### Integrations

| Permission | Description |
|---|---|
| `integration.edit` | Create / update / delete ArgoCD endpoints + GitOps app mappings + Provider connections (EPIC P, api#92). One permission, three surfaces — does **not** auto-cover `integration.bind` server-side; the SPA's capability helper unifies them in the UI but the api treats each endpoint family strictly. |
| `integration.bind` | Bind / unbind self-service-bindable provider connections on projects + environments you cover (EPIC Q, api#99). Scoped via the existing team-aware resolver. Never auto-covered by `integration.edit` — grant explicitly via the `provider_connection_binder` system role (or any custom role carrying this permission). Refuses prod envs, disabled connections, and connections without `self_service_bindable=true`. |

## Scoped permissions (today)

Most permissions today gate via `auth.Require(perm)` — the user
holds the permission or they don't. A few are intended to gate
via `auth.RequireScoped(perm, scopeFn)` so a grant can be narrowed
to a single project / environment / secret-ref prefix / provider:

- `secret.request` (typical scope: `{project_id, environment}`)
- `secret.approve` (typical scope: `{secret_ref_prefix, environment}`)
- `secret.value.provide` (typical scope: `{team_id}` — required for the seed `value_provider` role)
- `agent.mint` (typical scope: `{cluster}`)
- `agent.revoke` (typical scope: `{cluster}`)

The middleware shape is already in place; the actual scoped
gating on each endpoint lands as part of
[api#27](https://github.com/secrets-bridge/api/issues/27).

## How the UI consumes the catalog

The Roles admin page calls `GET /api/v1/permissions` on mount and
hydrates the chip picker from the response. The catalog includes
the group label so the chips render in the same RBAC / Workflows /
Agents / Secrets / Observability / Integrations groupings.

If a role contains a permission string the catalog doesn't know
about (e.g. a legacy custom permission from before
[api#32](https://github.com/secrets-bridge/api/issues/32) shipped
the catalog), the UI renders it in a separate **Custom / unknown**
group at the bottom — so old roles stay editable.

## How to add a permission

```go
// In api/internal/auth/permissions.go:

const (
    // ...existing
    PermSomethingNew Permission = "something.new"
)

var Catalog = []Descriptor{
    // ...existing
    {PermSomethingNew, "Group Name", "What this permission gates."},
}
```

That's it — `Catalog` is the source of truth; the `Keys()` /
`IsKnown()` helpers + the HTTP endpoint + the drift-guard test all
pick it up automatically.

A drift-guard test asserts that **every permission string
referenced in seed migrations is present in the Catalog** —
otherwise the seed roles would request unknown permissions on
first boot.
