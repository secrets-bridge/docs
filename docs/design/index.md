---
title: Design system
seo_title: "Secrets Bridge design system and brand"
description: "The Secrets Bridge design system: brand voice, colour and type tokens, and the logos and assets shared by the console, this site and the brand marks."
---

# Design system

One system covers the console, this site and the brand marks. It aims for an operations tool written by the engineers who answer for it: plain, exact and quiet, with warm graphite, one chartreuse accent and nothing decorative.

Read these before you write copy, build a page or make an image:

1. **[Brand voice](brand-voice.md)**: how we describe the product and its maturity, and the words we avoid.
2. **[Tokens and theme](tokens.md)**: colours for light and dark, the type scale, spacing, radii, and where each repo reads them.
3. **[Logos and assets](assets.md)**: the Checkpoint mark, its approved colourings, the product icons and the architecture illustration.

## The short version

| Question | Answer |
|---|---|
| Name | **Secrets Bridge**, two words, everywhere. In logos it comes from the lockup files; never retype it. |
| Fonts | Geist for what people read, Geist Mono for what machines read (refs, key names, paths, times, code), and Bricolage Grotesque for titles and counts. |
| Accent | Lime `#D4F24C`, as a fill only: one primary button per view, counts. Anything thin uses `accent-ink`, `#4A6600` on light and lime on dark. |
| Surfaces | Paper `bg`, white `surface`, `ink` text. Panels separate with a border, not a shadow. |
| Corners | 6 px tags, 8 px controls, 12 px panels, 14 px dialogs. Only avatars are round. |
| Status | A shape for its group and the exact status word. Blue means success. Colour never carries a status alone. |
| Secret values | Never shown outside the reveal panel: no values, lengths, hashes or previews. |

## Where it lives

- The console reads the tokens from `src/index.css` in the [`ui`](https://github.com/secrets-bridge/ui) repo (Tailwind `@theme`), with light and dark themes.
- This site maps the same tokens onto mkdocs-material in `docs/stylesheets/brand.css`.
- Logos, icons and the illustration are served from this site's `assets/` folder, listed on [Logos and assets](assets.md).

If something here doesn't cover your case, open an issue in [`secrets-bridge/docs`](https://github.com/secrets-bridge/docs/issues) and we'll either extend the system or write down the exception.
