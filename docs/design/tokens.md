---
title: Tokens and theme
description: "Secrets Bridge design tokens: colours for the light and dark themes, the type scale, spacing, radii and control sizes used by the console and this site."
---

# Tokens and theme

The console, this site and the brand assets use one set of tokens with light and dark values. Take every colour, size, radius and font from here; never copy a hex value out of a screenshot.

- **Console:** `src/index.css` in the [`ui`](https://github.com/secrets-bridge/ui) repo declares them as CSS variables and maps them into Tailwind with `@theme`. `data-theme` on `<html>` switches light and dark, and the system setting is the default.
- **This site:** `docs/stylesheets/brand.css` maps them onto mkdocs-material's variables for its light and dark schemes.

## Colour

Build every screen from `bg`, `surface`, `ink`, `muted`, `border` and `rule`, with `accent` kept to about 2%.

| Token | Light | Dark | Use |
|---|---|---|---|
| `bg` | `#F5F4EF` | `#111110` | Page background behind everything; about 70% of a screen. |
| `side` | `#EDECE6` | `#0D0D0C` | The console sidebar and the phone bars. |
| `surface` | `#FFFFFF` | `#1A1A18` | Panels and tables sitting on bg. |
| `raised` | `#FFFFFF` | `#232321` | Dialogs, drawers, the current nav item and key chips. |
| `field` | `#FFFFFF` | `#0B0B0A` | Inputs, code and revealed values. |
| `hover` | `#EFEEE8` | `#1E1E1C` | Row and control hover. |
| `press` | `#E6E5DE` | `#272724` | A control while it is pressed. |
| `ink` | `#161614` | `#F4F2EA` | Primary text and the production environment tag. 16.45:1 on bg (light), 16.86:1 (dark). |
| `muted` | `#5E5C55` | `#ADABA1` | Secondary text: subtitles, table headers, times, hints. 6.08:1 on bg (light), 8.20:1 (dark). |
| `border` | `#DCDAD2` | `#2A2A27` | Outer edges of panels, tables and dividers between sections. Decorative only: never the only edge of a control. |
| `rule` | `#E8E6DF` | `#222220` | Hairlines between rows inside a table, list or log. |
| `edge` | `#85837B` | `#76756D` | Control borders (inputs, secondary buttons), dashed empty states, hollow status shapes. At least 3:1 on bg and surface in both themes. |
| `accent` | `#D4F24C` | `#D4F24C` | Lime. A fill only: the one primary button per view, counts, reveal fills. Graphite on lime is 14.33:1 (light), 14.94:1 (dark). |
| `accent-ink` | `#4A6600` | `#D4F24C` | Everything thin in the accent: links, the current tab, focus ring, radios, reveal progress. 5.97:1 on bg (light), 14.94:1 (dark). |
| `accent-edge` | `#7E9420` | `transparent` | The outline of a lime button on light. |
| `on-accent` | `#161614` | `#111110` | Text and icons on lime. |
| `accent-soft` | `#F1F8D6` | `#20260F` | The control-plane zone in diagrams, reveal-ready panels and checked options. Never a status. |
| `accent-line` | `#B9CF6A` | `#4B5A1A` | Border for accent-soft areas. |
| `ok` | `#1F6FB8` | `#72BBFF` | Success, in blue: approved, executed, copied. Text on ok-bg, bg and surface; always with a word. |
| `ok-bg` | `#E7F1FB` | `#0F1E2C` | Success fill behind ok text. |
| `ok-line` | `#A9CBEC` | `#24476A` | Border around ok-bg. |
| `warn` | `#9A5A00` | `#FFAE52` | Waiting: pending, pending_values, pending_verification. Text on warn-bg, bg and surface. |
| `warn-bg` | `#FFF2DE` | `#2A1E0E` | Waiting fill behind warn text. |
| `warn-line` | `#EBC58C` | `#5A3F1C` | Border around warn-bg. |
| `bad` | `#B42318` | `#FF7070` | Failure: rejected, refused, failed, validation errors. Text on bad-bg, bg and surface; always with a word. |
| `bad-bg` | `#FDECEA` | `#2C1414` | Failure fill behind bad text; hover on danger buttons. |
| `bad-line` | `#F1B8B3` | `#5E2828` | Border of error banners. |
| `info` | `#4A4943` | `#CAC8BE` | Neutral information labels. Text on info-bg. |
| `info-bg` | `#F0EFEA` | `#1C1C1A` | Neutral information fill. |
| `info-line` | `#D6D4CC` | `#34342F` | Border around info-bg. |
| `scrim` | `rgba(22,22,20,0.36)` | `rgba(0,0,0,0.62)` | Overlay behind dialogs and drawers. |

Lime is a fill, never a line. On the light background it is about 1.2:1, so anything thin uses `accent-ink`, and a filled control keeps lime with an `accent-edge` border. In the console, ESLint refuses `text-accent` and its relatives. `edge` is for what you operate (input and secondary-button borders); `border` and `rule` only separate.

## Status

Show the exact API status as a word after a shape. Each group has its own shape, so a status never rests on colour alone:

| Status | Shape | Token |
|---|---|---|
| pending, pending_values, pending_verification | half | `warn` |
| approved (the agent is working) | split | `ok` |
| executed | solid | `ok` |
| rejected, refused, failed | diamond | `bad` |
| cancelled, expired | hollow | `edge` |

A reveal condition (ready, consumed, expired) shows separately from the status, in `ok` or `muted` text. `executed` alone never means a reveal is available.

## Type

Geist and Geist Mono for the interface, with Bricolage Grotesque for titles and counts only (all SIL Open Font License 1.1), self-hosted. Emphasis is weight, never italics or colour. Sentence case everywhere, including buttons and navigation.

| Group | Style | Size / line | Weight | Use |
|---|---|---|---|---|
| Website | `display` | 64 / 64 | 700 | The home page hero only, in Bricolage Grotesque |
| Website | `section` | 40 / 44 | 700 | Home page sections, in Bricolage Grotesque |
| Website | `heading` | 26 / 31 | 700 | Headings in docs pages, in Bricolage Grotesque |
| Website | `lede` | 17 / 27 | 400 | The paragraph under a title |
| Website | `body-docs` | 16 / 27 | 400 | Docs body text |
| Console | `console-title` | 30 / 34 | 700 | Page h1 in the console, in Bricolage Grotesque |
| Console | `dialog-title` | 20 / 25 | 700 | Dialog and drawer titles, in Bricolage Grotesque |
| Console | `count` | 28 / 30 | 700 | Counters, in Bricolage Grotesque |
| Console | `block-heading` | 15 / 22 | 600 | Above tables and panels |
| Console | `body` | 14.5 / 22 | 400 | Prose in the console |
| Console | `ui` | 14 / 20 | 500 | Controls |
| Console | `caption` | 13.5 / 20 | 400 | Hints |
| Console | `label` | 12.5 / 16 | 500 | Table headers |
| Mono | `mono`, `mono-small` | 12.5, 11.5 | 400 | Refs, key names, paths, times, IDs |

## Space, shape and size

| Token | Value |
|---|---|
| `space-1` to `space-8` | 4, 8, 12, 16, 20, 24, 28, 32 px |
| `radius-sm` | 6 px (tags) |
| `radius-md` | 8 px (controls) |
| `radius-lg` | 10 px (banners and wells) |
| `radius-xl` | 12 px (panels) |
| `radius-2xl` | 14 px (dialogs) |
| `radius-round` | 50%, avatars only |
| `control-md` / `control-sm` / `control-touch` | 38 px default, 32 px in tables, 44 px on phones |
| `sidebar` / `rail` | 240 px console sidebar, 320 px right rail |

Panels separate with a `border` line, never a shadow. The `overlay` shadow is only for dialogs, drawers and toasts.

## Accessibility

- Text at least 4.5:1, and controls, focus rings and status squares at least 3:1, against their background in both themes. The usage notes above give the ratios.
- Focus ring: 2 px solid `accent-ink`, 2 px offset, on every interactive element.
- Respect `prefers-reduced-motion`. Nothing in the product needs animation.
