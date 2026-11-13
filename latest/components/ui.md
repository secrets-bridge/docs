# UI (SPA)

Repo: [`secrets-bridge/ui`](https://github.com/secrets-bridge/ui)
· Stack: Vite 8 + React 19 + TypeScript + Tailwind 4 +
TanStack Query 5 + React Hook Form + Zod 4 +
React Router 7
· Container: multi-stage Node build → `nginx:1.27-alpine`,
unprivileged user 101

The operator-facing surface. A single-page application served as
static assets behind the same hostname as the api (path-based
routing: `/` → ui, `/api/v1/*` → api).

## Pages shipped today

| Route | Page | What |
|---|---|---|
| `/` | Overview | Counters, **Next up** with its context and action, the rest as rows, and a right rail with system health or your requests, recent activity and where you can request |
| `/approvals` | Approvals | Requests waiting for your decision, oldest first, with the oldest in full and Approve / Reject (with reason) |
| `/requests` | My requests | Your open and closed requests, with search and a status filter |
| `/requests/:id` | Request detail | Timeline, Approvals, **Wraps** (single-shot Reveal modal, read flow), the **Argo CD (observed by Gateway …)** panel with Gateway evidence, a muted **Argo CD history (before the Gateway)** card with the rows the retired control-plane poller wrote before the [cutover](../operations/gateway-cutover.md), read from `GET /requests/:id/gitops` and shown by `history_status` with the label *context only* (requester only, hidden when there are none), Details, Approver actions, Cancel-own |
| `/agents` | Agents | Revoke confirm, and a Mint drawer with a **reveal-once panel** for the agent secret. The drawer calls the legacy direct mint, which the api refuses (`403`) unless the dev-only `SB_ALLOW_DIRECT_AGENT_MINT` is on; onboard agents by [enrollment](../operations/bootstrap.md#enrolling-your-first-agent) |
| `/secrets` | Secrets | Filter strip (cluster / provider / ref prefix / status / label chips), with details beside the table when there's room |
| `/audit` | Audit log | Filter panel, and a drawer with the event's metadata and a link to its whole chain |
| `/admin/projects` | Projects | Master-detail (340px project rail + envs panel); soft-delete via archive/restore. The **Observation** column shows each environment's source (**Gateway** or **None**) to `gateway.list` holders; **Change…** appears only with `gateway.bind` |
| `/admin/roles` | Roles | Permission chip picker hydrated from `GET /permissions` (canonical catalog) |
| `/admin/assignments` | Role assignments | Person × role × scope table; people are picked by name or email |
| `/admin/workflows` | Workflows | TTL knobs, min approvers, justification required |
| `/admin/policies` | Policies | Selector → workflow priority-ordered list |
| `/admin/gateways` | Gateways | Create, enroll, approve connectors, bind targets, disable, enable and revoke [Gateways](../operations/gateway.md) |
| `/login` | Login | Real email + password against `POST /auth/login`, which sets the HttpOnly session cookie |

Administration (`/admin`) is one entry in the sidebar, with its own navigation grouped as people and access, projects and secrets, approval rules, infrastructure, and sign-in and security. Below 1360px the sections are a select. Besides the admin pages above, it holds Accounts (`/admin/users`, including people waiting for approval), Teams (`/admin/teams`), Sign-in methods (`/admin/sign-in`), Provider connections and Platform settings. On a phone the main places are bottom tabs, picked from what the person can open, and dialogs and drawers open as sheets from the bottom.

## Hard rules baked into the SPA

| Rule | Where |
|---|---|
| No credential in page scripts, nothing in localStorage / sessionStorage / IndexedDB | The api sets an HttpOnly, `SameSite=Strict` session cookie and the api client sends it with `credentials: 'include'`. `src/auth/AuthContext.tsx` holds identity from `GET /users/me`, with no token field. A reload keeps the session |
| HTTPS required on non-localhost | `src/api/client.ts` throws at module-load if `VITE_API_BASE_URL` is `http://` for non-loopback |
| No SSR | Vite SPA build; nginx serves static assets only |
| Strict CSP | `default-src 'self'; frame-ancestors 'none'` |
| Initial bundle ≤ 500 KB gzipped (FR-13) | CI bundle-size budget; currently ~125 KB |
| Typed shapes carry no secret values | `src/api/types.ts` has no `value` / `plaintext` / `token` fields by design |
| Container unprivileged + RO-FS friendly | nginx `USER 101`, tmp paths under `/tmp` |
| **Reveal-once modals** clear plaintext on close | `useEffect(() => () => setDecoded(null), [])` on both the wrap-reveal and agent-secret modals |

## Design system

The console uses the Switchboard identity: warm graphite with a
chartreuse accent and blue for success, Geist and Geist Mono with
Bricolage Grotesque for titles, and status as a shape per group plus
the exact word. Administration is one sidebar entry with its own
navigation, and on phones the console has bottom tabs and sheets.

See [Design system](../design/index.md) for the brand voice and tokens.

## Configuration

The SPA is configured at **build time**, not runtime:

| Env var | Default | Notes |
|---|---|---|
| `VITE_API_BASE_URL` | empty (same-origin) | Set to `https://api.example.com` only when serving the UI on a different origin |

Production deployments serve the UI and the api behind the same
ingress with path-based routing so cookies + CORS aren't in play.
