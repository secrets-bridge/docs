---
title: Tokens and theme
description: "Secrets Bridge design tokens: colours for the light and dark themes, the type scale, spacing, radii and control sizes used by the console and this site."
---

# Tokens and theme

The console, this site and the brand assets use one set of tokens with light and dark values. Take every colour, size, radius and font from here; never copy a hex value out of a screenshot.

- **Console:** `src/index.css` in the [`ui`](https://github.com/secrets-bridge/ui) repo declares them as CSS variables and maps them into Tailwind with `@theme`. `data-theme` on `<html>` switches light and dark, and the system setting is the default.
- **This site:** `docs/stylesheets/brand.css` maps them onto mkdocs-material's variables for its light and dark schemes.

## Colour

Build every screen from `bg`, `surface`, `ink`, `muted`, `border` and `rule`: roughly 70% `bg`, 13% `surface`, 10% `ink`, 5% `muted` and `rule`, and about 2% `accent`.

| Token | Light | Dark | Use |
|---|---|---|---|
| `bg` | `#F6F5F1` | `#0F1013` | Paper. Page background behind everything; about 70% of a screen. |
| `surface` | `#FFFFFF` | `#17191E` | Panels, tables, dialogs, drawers and inputs sitting on bg. |
| `sunken` | `#EFEEE9` | `#1D1F25` | Row hover, current nav item, read-only boxes, key chips. |
| `ink` | `#15171C` | `#ECECEE` | Primary text and the production environment tag. 16.4:1 on bg (light), 16.1:1 (dark). |
| `muted` | `#5B606B` | `#A2A6AF` | Secondary text: subtitles, table headers, times, hints. 5.8:1 on bg (light), 7.8:1 (dark); passes 4.5:1 on surface and sunken too. |
| `border` | `#DDDBD4` | `#2B2E36` | Outer edges of panels, tables and dividers between sections. Decorative only: never the only edge of a control. |
| `rule` | `#E8E6E0` | `#22252B` | Hairlines between rows inside a table, list or log. |
| `edge` | `#7E838D` | `#686D7A` | Control borders (inputs, secondary buttons), dashed empty states, hollow status squares. At least 3.3:1 on bg, surface and sunken in light; 3.2:1 in dark. |
| `accent` | `#3141C8` | `#9AA3FF` | Ultramarine. The brand mark, links, the one primary button per view, current-tab underline, focus ring, reveal progress. About 2% of a screen. 7.1:1 on bg (light), 8.2:1 (dark). |
| `on-accent` | `#FFFFFF` | `#0F1013` | Text and icons on accent fills (primary button, nav count). 7.7:1 (light), 8.2:1 (dark). |
| `accent-soft` | `#E9EBFB` | `#1D2140` | Control-plane zone in diagrams and the avatar background. Never a status. |
| `accent-line` | `#BFC5F3` | `#3A4285` | Border for accent-soft areas. |
| `ok` | `#1E7A46` | `#6FCF97` | Success: approved, executed, reveal ready, copied. Text on ok-bg, bg and surface (4.7:1 or more); always with a word. ok and bad differ by hue more than lightness, so never rely on the colour of a status square alone. |
| `ok-bg` | `#E6F4EC` | `#132219` | Success fill behind ok text. |
| `ok-line` | `#A7D7BA` | `#24432F` | Border around ok-bg. |
| `warn` | `#7A5200` | `#F2C14E` | Waiting: pending, pending_values, pending_verification. Text on warn-bg, bg and surface. |
| `warn-bg` | `#FFF3D6` | `#2A2210` | Waiting fill behind warn text. |
| `warn-line` | `#EACB86` | `#4E4024` | Border around warn-bg. |
| `bad` | `#B3261E` | `#FF8A80` | Failure: rejected, refused, failed, validation errors. Text on bad-bg, bg and surface; always with a word. |
| `bad-bg` | `#FDECEA` | `#2C1513` | Failure fill behind bad text; hover on danger buttons. |
| `bad-line` | `#F1B8B3` | `#4E2522` | Border of danger buttons and error banners. |
| `info` | `#3E4A5C` | `#B7C0CF` | Neutral information labels. Text on info-bg. |
| `info-bg` | `#EEF0F3` | `#1B1F27` | Neutral information fill. |
| `info-line` | `#C9CED8` | `#323846` | Border around info-bg. |
| `scrim` | `rgba(21,23,28,0.36)` | `rgba(0,0,0,0.6)` | Overlay behind dialogs and drawers. |

`accent` is a signal: the mark, links, one primary button per view, the current tab, the focus ring, reveal progress. It is never a large fill, a status, or emphasis in running text. `edge` is for what you operate (input and secondary-button borders); `border` and `rule` only separate.

## Status

Show the exact API status as a word after a small square:

| Status | Square | Token |
|---|---|---|
| pending, pending_values, pending_verification | hollow | `warn` |
| approved, executed | solid | `ok` |
| rejected, refused, failed | solid | `bad` |
| cancelled, expired | hollow | `edge` |

A reveal condition (ready, consumed, expired) shows separately from the status, in `ok` or `muted` text. `executed` alone never means a reveal is available.

## Type

IBM Plex Sans and IBM Plex Mono (SIL Open Font License 1.1), weights 400, 500 and 600, self-hosted. Emphasis is weight, never italics or colour. Sentence case everywhere, including buttons and navigation.

| Group | Style | Size / line | Weight | Use |
|---|---|---|---|---|
| Website | `display` | 64 / 66 | 600 | The home page hero only |
| Website | `page-title` | 42 / 47 | 600 | Page h1 |
| Website | `section` | 38 / 43 | 600 | Home page sections |
| Website | `heading` | 23 / 30 | 600 | Headings in docs pages |
| Website | `lede` | 18 / 29 | 400 | The paragraph under a title |
| Website | `body-docs` | 16 / 27 | 400 | Docs body text |
| Console | `console-title` | 20 / 24 | 600 | Page h1 in the console |
| Console | `dialog-title` | 17 / 22 | 600 | Dialog and drawer titles |
| Console | `block-heading` | 13.5 / 20 | 600 | Above tables and panels |
| Console | `body` | 13.5 / 20 | 400 | Prose in the console |
| Console | `ui` | 13 / 18 | 500 | Controls |
| Console | `caption` | 12.5 / 18 | 400 | Hints |
| Console | `label` | 12 / 16 | 500 | Table headers |
| Mono | `mono`, `mono-small` | 13, 12 | 400 | Refs, key names, paths, times, IDs |

## Space, shape and size

| Token | Value |
|---|---|
| `space-1` to `space-8` | 4, 8, 12, 16, 20, 24, 28, 32 px |
| `radius-sm` | 3 px (tags) |
| `radius-md` | 4 px, the largest radius |
| `radius-round` | 50%, avatars only |
| `control-md` / `control-sm` / `control-touch` | 32 px default, 28 px in tables, 44 px on phones |
| `sidebar` / `rail` | 216 px console sidebar, 260 px overview side column |

Panels separate with a `border` line, never a shadow. The `overlay` shadow is only for dialogs, drawers and toasts.

## Accessibility

- Text at least 4.5:1, and controls, focus rings and status squares at least 3:1, against their background in both themes. The usage notes above give the ratios.
- Focus ring: 2 px solid `accent`, 2 px offset, on every interactive element.
- Respect `prefers-reduced-motion`. Nothing in the product needs animation.
