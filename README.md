# secrets-bridge / docs

Documentation site for [Secrets Bridge](https://github.com/secrets-bridge) — `mkdocs-material` → [secrets-bridge.io](https://secrets-bridge.io).

## Local development

```bash
# Option A: docker (no Python install needed)
docker run --rm -it -p 8000:8000 -v ${PWD}:/docs squidfunk/mkdocs-material:latest

# Option B: native Python
pip install -r requirements.txt
mkdocs serve
```

Then open http://localhost:8000.

## Build

```bash
mkdocs build --strict
```

`--strict` is enforced in CI. Any warning (broken link, missing page, malformed nav, etc.) fails the build.

## Deploy

Every push to `main` triggers `.github/workflows/deploy.yml`, which runs `mkdocs gh-deploy`. The deployed site lives on the `gh-pages` branch and serves at https://secrets-bridge.io (CNAME → GitHub Pages).

## Contributing

- Match the [brand voice](docs/design/brand-voice.md) — tagline, wordmark conventions, voice rules
- Tokens and theme come from the [Figma file](docs/design/figma.md); don't invent new colors
- Every external surface — README, social card, blog post — should reference these docs as the source of truth
- File issues at [`secrets-bridge/.github`](https://github.com/secrets-bridge/.github)
