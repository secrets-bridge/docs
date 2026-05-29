# secrets-bridge / docs

Documentation site for [Secrets Bridge](https://github.com/secrets-bridge) — `mkdocs-material` + `mike` → [secrets-bridge.io](https://secrets-bridge.io).

## Versioning

The site is **versioned by `mike`**. Each GitHub release tag (`vMAJOR.MINOR.PATCH`) deploys to its own URL on the `gh-pages` branch:

| URL | Maps to | When |
|---|---|---|
| `secrets-bridge.io/` | `latest` | Visitors land here by default |
| `secrets-bridge.io/latest/` | The most recent release tag | Aliased on every tag push |
| `secrets-bridge.io/v0.2/` | The `v0.2.x` major.minor track | Aliased on every patch within `v0.2.x` |
| `secrets-bridge.io/v0.1/` | The `v0.1.x` major.minor track | Frozen after `v0.2.x` releases |
| `secrets-bridge.io/dev/` | Whatever's on `main` right now | Rolling — every push to main updates it |

The **version selector** in the top-right of every page lets a visitor switch between any deployed version. Old versions stay live indefinitely (`mike` doesn't delete them).

## Local development

```bash
# Option A: docker (no Python install needed)
docker run --rm -it -p 8000:8000 -v ${PWD}:/docs squidfunk/mkdocs-material:latest

# Option B: native Python
pip install -r requirements.txt
mkdocs serve
```

Open http://localhost:8000. Local serve doesn't use `mike` — you get a single un-versioned preview, which is what you want while authoring.

## Build

```bash
mkdocs build --strict
```

`--strict` is enforced in CI. Any warning (broken link, missing page, malformed nav) fails the build.

## Deploy

CI handles every deploy. You shouldn't need to run `mike` locally.

| Trigger | What CI does |
|---|---|
| Push to `main` | `mike deploy --push dev` — updates the rolling `dev` version |
| Push a `v*.*.*` tag | `mike deploy --push --update-aliases v<major>.<minor> latest` + `mike set-default latest` — promotes the new release to `latest` and updates the major.minor track |
| Manual workflow dispatch | You choose the version + alias from the Actions tab |

### Releasing

```bash
# After landing the release commit on main:
git tag v0.2.0
git push origin v0.2.0
```

CI picks up the tag, deploys to `/v0.2/`, re-aliases `latest` → `v0.2`, and updates the default landing version.

To redeploy an old version (e.g. backporting a typo fix):

```bash
# From the Actions tab → Deploy docs → Run workflow:
#   version: v0.1
#   alias: (blank — don't change `latest` for an old version)
```

## Contributing

- Match the [brand voice](docs/design/brand-voice.md) — tagline, wordmark conventions, voice rules
- Tokens and theme come from the [Figma file](docs/design/figma.md); don't invent new colors
- Every external surface — README, social card, blog post — should reference these docs as the source of truth
- File issues at [`secrets-bridge/.github`](https://github.com/secrets-bridge/.github)
