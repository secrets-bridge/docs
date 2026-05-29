# Brand voice & canonical phrasing

Source of truth: Figma file
[Secrets Bridge — Brand](figma.md) and
[`skills/ui/design/BRAND_VOICE.md`](https://github.com/secrets-bridge/skills/blob/main/ui/design/BRAND_VOICE.md).

When writing for **any public surface** — README hero text, PR
descriptions, social cards, error messages, blog posts, conference
slides, docs pages — match these. Don't paraphrase the tagline;
it's the brand.

## Wordmark

| Use | Spelling |
|---|---|
| Logo / wordmark / brand identity | **`SecretsBridge`** (one word) |
| Body copy, prose, headings, repo descriptions | **`Secrets Bridge`** (two words) |
| Diagram callouts | **`SECRETS BRIDGE`** (uppercase, no space) |

The Figma logo art renders `SecretsBridge`; everywhere else we
write "Secrets Bridge". **Don't mix.**

## Tagline (canonical)

> **The brain behind your secrets.**

This is the brand line. Use it verbatim including the trailing
period when used as a sentence. Drop the period when used as a
heading. Never paraphrase ("the brain for your secrets", "your
secrets' brain", etc. — all wrong).

## Eyebrow / category label

> **UNIFIED SECRETS CONTROL PLANE**

All caps, used above the wordmark on landing pages, social cards,
and the website hero. Tailwind class: `text-eyebrow` (rendered
uppercase via CSS).

## Subhead (long form)

Two interchangeable variants:

- **Short:** "Unified secrets control plane for cloud-native teams."
- **Long:** "A distributed secrets control plane that connects and
  governs secrets across every provider — without replacing the
  tools your teams already use."

Use the short one in PR descriptions, README intros, and
social-card subtitles. Use the long one when the audience is
product / business / sales.

## Metaphor family

The brand metaphor is **"the brain"**. Reinforce it consistently.

| Element | Phrasing |
|---|---|
| What the control plane is | "The brain — governance, approvals, RBAC, audit" |
| Cross-provider reach | "One brain, every provider" |
| What providers are | "Where secret values actually live" |
| What the control plane does **not** do | "Values stay inside your providers" |

The brain metaphor is also why the mascot is named **Bridgey**
(the brain itself, anthropomorphized). Use the mascot sparingly —
for delight moments, error pages, blog posts, social cards. **Not**
in production dashboard UI chrome.

## Voice rules

| Do | Don't |
|---|---|
| Lead with the tagline | Lead with feature lists |
| Frame as "the brain" + "the providers" | Frame as "the secrets manager" |
| Emphasize "values stay inside your providers" | Imply we mirror or replicate secret values |
| Use semi-colons + em-dashes for rhythm | Bullet-cascade everything |
| Sentence case for body | Title case for body |

## Example surfaces

=== "GitHub README hero"

    ```markdown
    # Secrets Bridge

    > **The brain behind your secrets.**

    Unified secrets control plane for cloud-native teams.
    Approvals, RBAC, audit, and least-privilege agent execution
    across Vault, AWS Secrets Manager, Azure Key Vault, GCP Secret
    Manager, and Kubernetes / GitOps — without your developers
    ever holding raw provider credentials.
    ```

=== "PR description"

    ```markdown
    ## Summary

    Closes the workflow loop start in the UI — dev team no longer
    has to curl `POST /requests` to begin the flow.

    ...
    ```

    Note: PR descriptions are technical, not marketing. Don't shoehorn
    the tagline. The brand voice rule for PRs is "be precise; be
    specific; be honest about what didn't ship."

=== "Conference slide"

    ```
    [Eyebrow] UNIFIED SECRETS CONTROL PLANE
    [Wordmark] SecretsBridge
    [Tagline] The brain behind your secrets.
    [Subhead] One brain. Every provider. Values stay home.
    ```

=== "Error page (with mascot)"

    The error pages and 404s are one of the few places Bridgey gets
    to appear. Keep the tone helpful, never cute-to-the-point-of-
    annoying. The brain mascot says "I couldn't find that page" —
    not "Oopsie!".

## What to avoid

| Anti-pattern | Why |
|---|---|
| "Our solution" / "Our platform" | Reads like a sales deck. The product name is the subject. |
| "Cutting-edge" / "next-gen" / "AI-powered" | We don't make those claims. We're a control plane, full stop. |
| "Effortless secrets management" | Effortless is a marketing lie when a SOC2 audit is in your future. |
| "Forget about Vault / AWS / your provider" | We augment providers, we don't replace them. The whole architecture depends on this. |
| Mascot in production dashboard chrome | The mascot is for delight surfaces (errors, blog posts, social cards), not for the workhorse UI an operator sees every day. |
