# CLAUDE.md: secrets-bridge/docs

Instructions for Claude Code and contributors working in this repo.

## What this repo is

The public documentation site for Secrets Bridge, built with mkdocs-material and versioned with mike. It deploys to https://secrets-bridge.io.

## Layout

| Path | Purpose |
|---|---|
| `mkdocs.yml` | Site config, navigation, theme |
| `docs/overview/` | Architecture, threat model, glossary, and `product-status.md` |
| `docs/operations/` | Bootstrap, config, authentication, OIDC, agent onboarding, provider connections, cross-team requests, troubleshooting |
| `docs/reference/` | API endpoints, providers, KMS backends, permissions |
| `overrides/` | Theme overrides (SEO metadata) |

## Build and preview

```bash
pip install -r requirements.txt
mkdocs serve                      # local preview
mkdocs build --strict             # must pass before a PR
```

`--strict` does not parse Mermaid. Preview every changed diagram locally, or check it with `@mermaid-js/mermaid-cli`. Avoid `;` inside sequence-diagram messages and quote subgraph titles as `subgraph id ["Title"]`.

Pushes to `main` deploy the rolling version through `.github/workflows/deploy.yml`. Leave the `gh-pages` branch alone; mike manages it.

## Rules for this repo

- `docs/overview/product-status.md` is the source of truth for what works. Keep Live, QA-certified, In progress and Roadmap separate, and never list a feature as live before it passes QA.
- Document what exists in the code today. Describe how things are, not what changed in the last PR.
- Use Mermaid for diagrams. No invented screenshots.
- Plain, neutral technical voice. Avoid marketing language.
- Every example uses placeholders: `example.com` hosts, `123456789012` account IDs, generic names such as `tenant-a-uat`. Never real hostnames, account IDs, cluster names, secret paths or company names.
- A new feature in another repo usually needs a docs update here (product-status plus the relevant operations page).

## Contributing

Feature branch off `main`, conventional commits (`docs:`), CI green, then open a PR for maintainer review. Never push to `main`.

**No AI attribution.** Commits and PRs describe the change, nothing else. Don't add `Co-Authored-By` trailers for AI assistants, "Generated with ..." lines or links to AI sessions to commit messages, PR titles or PR bodies. A squash merge copies the PR body into the commit on `main`, where it can't be edited later. If you use a coding assistant, turn off its commit and PR attribution in its settings.
