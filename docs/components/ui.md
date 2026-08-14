# UI (SPA)

Repo: [`secrets-bridge/ui`](https://github.com/secrets-bridge/ui)
· Stack: Vite 6 + React 18 + TypeScript 5 + Tailwind 3 +
TanStack Query 5 + React Hook Form 7 + Zod 3 +
react-router-dom v6
· Container: multi-stage Node build → `nginx:1.27-alpine`,
unprivileged user 101

The operator-facing surface. A single-page application served as
static assets behind the same hostname as the api (path-based
routing: `/` → ui, `/api/v1/*` → api).

## Pages shipped today

| Route | Page | What |
|---|---|---|
| `/` | Dashboard | KPI cards, pending approvals (preview), recent audit activity (preview), providers health (preview), **agents** card (real), requests-this-week chart (preview) |
| `/requests` | Requests | My-requests filter pills (All / Pending / Approved / Rejected / Executed × patch / read) + Approver queue with inline Approve / Reject (with-reason) |
| `/requests/:id` | Request detail | Timeline, Approvals, **Wraps** (single-shot Reveal modal, read flow), GitOps observations (disabled banner when §26 is off), Details, Approver actions, Cancel-own |
| `/agents` | Agents | Mint drawer with **reveal-once panel** for agent secret + bash env snippet, Revoke confirm |
| `/secrets` | Discovered secrets | Filter strip (cluster / provider / ref prefix / status / label chips), two-pane (table + sticky details with provider_config JSON) |
| `/audit` | Audit log | Filter strip + correlation drill-in chip on every row, sticky details with metadata JSON |
| `/admin/projects` | Projects | Master-detail (340px project rail + envs panel); soft-delete via archive/restore |
| `/admin/roles` | Roles | Permission chip picker hydrated from `GET /permissions` (canonical catalog) |
| `/admin/assignments` | Assignments | User × role × scope table; scope chips with `=` separator |
| `/admin/workflows` | Workflows | TTL knobs, min approvers, allow self-approval, justification required |
| `/admin/policies` | Policies | Selector → workflow priority-ordered list |
| `/admin/integrations` | Integrations | ArgoCD endpoints + GitOps app mappings; feature-gated banner when §26 is off |
| `/login` | Login | Real email + password against `POST /auth/login` (token in memory only) |

## Hard rules baked into the SPA

| Rule | Where |
|---|---|
| Token in memory only, never localStorage / sessionStorage / IndexedDB / cookies | `src/auth/AuthContext.tsx` keeps it in React state; reload signs out |
| HTTPS required on non-localhost | `src/api/client.ts` throws at module-load if `VITE_API_BASE_URL` is `http://` for non-loopback |
| No SSR | Vite SPA build; nginx serves static assets only |
| Strict CSP | `default-src 'self'; frame-ancestors 'none'` |
| Initial bundle ≤ 500 KB gzipped (FR-13) | CI bundle-size budget; currently ~125 KB |
| Typed shapes carry no secret values | `src/api/types.ts` has no `value` / `plaintext` / `token` fields by design |
| Container unprivileged + RO-FS friendly | nginx `USER 101`, tmp paths under `/tmp` |
| **Reveal-once modals** clear plaintext on close | `useEffect(() => () => setDecoded(null), [])` on both the wrap-reveal and agent-secret modals |

## Design system

The SPA matches the Figma file `Secrets Bridge - Brand` byte-for-byte
on the brand pages: fonts (Inter + JetBrains Mono), colors (Navy
900 / Dark Navy / Cyan accent), brand-gradient primary CTAs,
`StatusPill` variants, and the reveal-once UX pattern.

See [Design system](../design/index.md) for the brand voice,
tokens, and Figma file reference.

## Configuration

The SPA is configured at **build time**, not runtime:

| Env var | Default | Notes |
|---|---|---|
| `VITE_API_BASE_URL` | empty (same-origin) | Set to `https://api.example.com` only when serving the UI on a different origin |

Production deployments serve the UI and the api behind the same
ingress with path-based routing so cookies + CORS aren't in play.
