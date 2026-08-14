# Figma file & brand assets

The canonical design lives in **one Figma file**. Treat it as the
source of truth; everything else (the SPA's Tailwind tokens, the
README banners, the social cards, this docs site's theme) is
downstream.

## The Figma file

| Field | Value |
|---|---|
| **Name** | Secrets Bridge - Brand |
| **File key** | `1kcrITjYhP91uDEseJZzoj` |
| **Pages** | 01 Cover · 02 Foundations · 03 Diagram & Banner · 04 Website · 05 Dashboard · 06 Requests / Roles / Modals |

Access is gated. Request via the
[`secrets-bridge` org](https://github.com/secrets-bridge) if you
need an editor seat. **Read-only view links** are circulated on
request for design partners and contributors who need to reference
the canonical frames without an editor seat.

## What lives on which page

| Figma page | What's on it | When you'd open it |
|---|---|---|
| **01 Cover** | File overview, version history note | Just orienting |
| **02 Foundations** | Color palette, type ramp, spacing scale, status pill variants, button states, form field states | Adding a new component to the SPA or this docs site: match these tokens |
| **03 Diagram & Banner** | Architecture diagrams (the same one you see on the [Architecture](../overview/architecture.md) page, but as Figma vector), GitHub social banners, README hero banner | Updating an external surface that needs the brand banner / OG image |
| **04 Website** | The marketing site mockups (`secrets-bridge.io` landing, pricing if/when, contact) | Building or updating the marketing site |
| **05 Dashboard** | The operator-facing Dashboard page (KPI row, Pending Approvals table, Providers Health, Agents card, Requests-this-week chart) | Implementing a Dashboard widget or changing its layout |
| **06 Requests / Roles / Modals** | Requests list (My-requests + Approver queue), Request detail (Timeline / Approvals / Wraps / GitOps), Roles list + drawer, ConfirmModal patterns | Implementing a request- or admin-related page |

## Brand assets (downloadable)

The brand assets are mirrored to the
[`secrets-bridge/.github`](https://github.com/secrets-bridge/.github/tree/main/profile)
repo so anyone, including non-editor contributors, can pull them
without a Figma seat.

| Asset | URL | Use |
|---|---|---|
| Logo (light) | [`logo.svg`](https://raw.githubusercontent.com/secrets-bridge/.github/main/profile/logo.svg) | Light-background hero / docs |
| Logo (dark) | [`logo-dark.svg`](https://raw.githubusercontent.com/secrets-bridge/.github/main/profile/logo-dark.svg) | Dark-background hero / docs |
| Icon (full) | [`icon.svg`](https://raw.githubusercontent.com/secrets-bridge/.github/main/profile/icon.svg) | Slack / GitHub App icon |
| Icon (control plane) | [`icon-control-plane.svg`](https://raw.githubusercontent.com/secrets-bridge/.github/main/profile/icon-control-plane.svg) | Diagrams |
| Favicon (app) | [`favicon.svg`](https://raw.githubusercontent.com/secrets-bridge/.github/main/profile/favicon.svg) | SPA + docs site favicon |
| GitHub avatar | [`github-avatar.png`](https://raw.githubusercontent.com/secrets-bridge/.github/main/profile/github-avatar.png) | Org avatar (440×440) |
| Mascot (Bridgey) | [`mascot.svg`](https://raw.githubusercontent.com/secrets-bridge/.github/main/profile/mascot.svg) | Error pages, blog posts, social cards; never production dashboard chrome |
| OG banner | [`og-banner.png`](https://raw.githubusercontent.com/secrets-bridge/.github/main/profile/og-banner.png) | Open Graph / Twitter card (1200×630) |
| Diagram (control plane) | [`diagram-control-plane.svg`](https://raw.githubusercontent.com/secrets-bridge/.github/main/profile/diagram-control-plane.svg) | Embed in blog posts / docs |

## How the SPA stays in sync with Figma

The SPA's brand fidelity is enforced by a sync chain:

```
Figma file (1kcrITjYhP91uDEseJZzoj)
   ↓ skills/ui/design/tokens/sync.sh
   pulls styles via Figma REST API → design-tokens.json
   ↓ manual: copy values into tailwind.config.js
ui/tailwind.config.js
   ↓ vite build
ui SPA (renders the brand)
```

The sync scripts live in
[`skills/ui/design/tokens/`](https://github.com/secrets-bridge/skills/tree/main/ui/design/tokens)
(for color + type tokens) and
[`skills/ui/design/brand/`](https://github.com/secrets-bridge/skills/tree/main/ui/design/brand)
(for SVG / PNG asset renders).

The Figma screen frames themselves are cached as PNG renders in
[`skills/ui/design/frames/`](https://github.com/secrets-bridge/skills/tree/main/ui/design/frames)
so a contributor implementing a page can read the design without a
Figma seat; just open the corresponding PNG.

## Hard rule

The reverse direction (code → Figma) is **not** supported.
Figma is upstream; the SPA is downstream. If you need to change a
token or a layout:

1. Update the Figma file first.
2. Re-render the relevant frame PNG into `skills/ui/design/frames/`.
3. Update the SPA to match.

Don't ship a SPA change that contradicts the Figma file. We've
worked hard to keep the two in sync; let's keep it that way.

## Need a Figma seat?

Open an issue against
[`secrets-bridge/.github`](https://github.com/secrets-bridge/.github)
with:

- Your Figma account email
- What you want to do (read-only review / editor)
- Your GitHub username

We'll add you (editor seats are gated; read-only is freely
granted to active contributors).
