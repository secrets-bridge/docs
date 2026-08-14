# Tokens & theme

The SPA's Tailwind theme, this docs site, the GitHub social
banners, and every brand surface use the same set of design
tokens. The Figma file is the source; the SPA's
`tailwind.config.js` is the consumer.

## Color tokens

| Tailwind name | Hex | Role |
|---|---|---|
| `bg` | `#0B1220` | Base page background (Navy 900) |
| `surface` | `#0F172A` | Card / panel surface (Dark Navy) |
| `text` | `#CBD5E1` | Body copy (Slate 300) |
| `muted` | `#64748B` | Secondary text / labels (Slate 500) |
| `accent` | `#06B6D4` | **Primary accent** (Cyan) |
| `accent-bright` | `#22D3EE` | Highlight / hover |
| `border` | `#1E293B` | Card edges, separators |
| `teal` | `#14B8A6` | Secondary accent |
| `blue` | `#3B82F6` | Tertiary / brand-gradient end |
| `purple` | `#A855F7` | Tertiary (sparingly) |
| `success` | `#10B981` | StatusPill success (Vault healthy, request approved) |

### Status colors (StatusPill variants)

| Variant | When |
|---|---|
| `success` | Green outline / fill: agent active, request approved, audit success, secret present |
| `warning` | Yellow outline / fill: agent stale, audit denied, env uat, archived project, applied_unverified |
| `error` | Red outline / fill: request rejected/failed, env prod, audit failure |
| `pending` | Yellow: request pending |
| `accent` | Cyan: role badges, env staging |
| `system` | Cyan outline: system-seed row marker |
| `neutral` | Muted: env other, preview chips |
| `cancelled` | Muted strikethrough: consumed wraps |

## Type tokens

| Family | Font | When |
|---|---|---|
| Sans | [Inter](https://fonts.google.com/specimen/Inter) | Body copy, headings, UI labels |
| Mono | [JetBrains Mono](https://fonts.google.com/specimen/JetBrains+Mono) | Code, CLI snippets, identifiers, UUIDs, secret refs |

Loaded via Google Fonts with `preconnect` to keep CLS low. The
SPA's CSP allows `fonts.googleapis.com` + `fonts.gstatic.com` for
this reason.

### Type scale

| Token | Tailwind class | Use |
|---|---|---|
| `display` | `text-5xl font-bold` | Hero headings (Figma frames only) |
| `h1` | `text-2xl font-bold tracking-tight` | Page title (PageHeader) |
| `h2` | `text-base font-semibold` | Card / section headers |
| `eyebrow` | `text-[11px] uppercase tracking-wider text-muted font-medium` | Field labels, table headers |
| `body` | `text-sm` | Default body copy |
| `caption` | `text-[11px] text-muted` | Footer notes, helper text |

## Spacing & layout

The SPA uses Tailwind's default 4px-grid spacing scale. Cards have:

- `rounded-2xl` corners (16px)
- `border border-border` outline
- `bg-surface` background
- `shadow-2xl` on modals only

PageHeader carries a 6-unit (24px) bottom margin; Card → Card
spacing is 16px (`gap-4`) on grids and 24px (`space-y-6`) on
vertical stacks.

## Gradients

`bg-brand-gradient` is the **only** gradient that ships in the SPA.
It's the cyan→blue gradient used on every primary CTA pill (`+ New
…`, `Reveal (one-time)`, `Mint`, `Submit`, `Sign in`):

```css
background-image: linear-gradient(135deg, #06B6D4 0%, #3B82F6 100%);
```

Do not invent new gradients. If you need to highlight something
that isn't a primary CTA, use a solid color (`bg-accent/10`) or a
border-l-4 callout, not a new gradient.

## Where these live in code

| File | What |
|---|---|
| [`ui/tailwind.config.js`](https://github.com/secrets-bridge/ui/blob/main/tailwind.config.js) | The canonical Tailwind config: every token above |
| [`ui/src/ui/`](https://github.com/secrets-bridge/ui/tree/main/src/ui) | The shared primitives that consume the tokens: `Button`, `Card`, `StatusPill`, `Drawer`, `ConfirmModal`, `PageHeader`, `LogoMark` |
| [`skills/ui/design/tokens/`](https://github.com/secrets-bridge/skills/tree/main/ui/design/tokens) | The Figma → JSON sync output; the `sync.sh` script + `design-tokens.json` + `mapping.md` |
| [`skills/ui/design/BRAND_VOICE.md`](https://github.com/secrets-bridge/skills/blob/main/ui/design/BRAND_VOICE.md) | The canonical brand voice doc |

## How to update a token

The flow is **Figma → skills/ui/design → tailwind.config.js**:

1. Make the change in the Figma file (versions 02 Foundations).
2. Re-run `skills/ui/design/tokens/sync.sh` to pull the latest
   token definitions into `design-tokens.json`.
3. Update `ui/tailwind.config.js` to match: same Tailwind names,
   new hex values.
4. Rebuild the SPA; visual diff against the Figma frames in
   `skills/ui/design/frames/` (six PNG renders cached at last
   sync).
5. Open a PR against both `ui` and `skills`; they ship together.

The reverse direction (code → Figma) is not supported. Figma is
upstream; the SPA is downstream.
