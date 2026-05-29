---
title: Design system
description: The Figma file, brand voice, design tokens, and asset library that keep every Secrets Bridge surface — SPA, docs, README banners, social cards — feeling like one product.
---

# Design system

Secrets Bridge has a real, intentional brand. The SPA, the GitHub
org, the README banners, and these docs all use the same tokens,
the same fonts, and the same canonical phrasing — so the product
feels like one product no matter where you encounter it.

If you're contributing copy, building a new page, or shipping
external comms, **read these three pages first**:

1. **[Brand voice](brand-voice.md)** — the tagline, wordmark
   conventions, metaphor family, voice rules
2. **[Tokens & theme](tokens.md)** — the color palette, type
   ramp, spacing, and how they're consumed in Tailwind
3. **[Figma file & assets](figma.md)** — where the canonical
   design lives, how to download the brand assets, the sync
   scripts that pull tokens from Figma into the SPA

## Why we wrote this down

A brand drifts the moment two people write copy without a shared
reference. Every PR adds friction to "wait, do we call it
*Secrets Bridge* or *SecretsBridge*?" Every external surface (a
README, a social card, a marketing site, a conference slide) is
an opportunity for a contributor to invent their own variant.

The three pages above are the answer to "what do I match against?"
Match these. If you find yourself wanting to deviate, open an
issue against [`secrets-bridge/skills`](https://github.com/secrets-bridge/skills)
and we'll either update the system or document the exception.

## The short version

| Question | Answer |
|---|---|
| Tagline? | **The brain behind your secrets.** (verbatim, including the trailing period) |
| Eyebrow? | **UNIFIED SECRETS CONTROL PLANE** (all caps) |
| Wordmark in logos / brand identity? | **SecretsBridge** (one word) |
| Wordmark in body copy / READMEs / prose? | **Secrets Bridge** (two words) |
| UI font? | [Inter](https://fonts.google.com/specimen/Inter) |
| Code / CLI font? | [JetBrains Mono](https://fonts.google.com/specimen/JetBrains+Mono) |
| Primary accent color? | Cyan `#06B6D4` (`text-accent` in Tailwind) |
| Base background? | Navy 900 `#0B1220` (`bg-bg` in Tailwind) |
| Canonical Figma file | [Secrets Bridge — Brand](figma.md) |

Everything else is detail — but it's detail we've thought about,
written down, and want you to use.
