---
title: Brand voice
description: "How Secrets Bridge describes itself: say what we keep, describe the mechanism and label maturity exactly, with examples and the words we avoid."
---

# Brand voice

Write the way the engineer who has to defend the claim in a review would.

## Rules

- **Say what we keep.** "We don't keep your secret values. We keep requests, approvals and audit metadata." Never "zero-knowledge" or "bank-grade".
- **Describe the mechanism.** "The agent connects out, so you open no inbound ports." Not "seamless connectivity".
- **Label maturity exactly.** Use the words on [Product status](../overview/product-status.md): implemented, QA-certified, in progress, roadmap. Not "production-ready".
- **Short sentences, plain verbs, sentence case.** "Ask for access. Someone approves. The agent reads it." No exclamation marks, no emoji.
- **No proof we don't have.** No invented customers, certifications, percentages or uptime.
- **Address the reader as "you".** Name people and teams: "Waiting for Sam Noor", not "Pending approval".
- **Errors say what happened and what to do.** "That code wasn't accepted. Nothing was retrieved."

## Describing the product

| Where | Wording |
|---|---|
| One line | Secrets Bridge governs who may use the secrets a team already keeps in AWS Secrets Manager or HashiCorp Vault. |
| A little more | It adds access requests, approvals, audit and agent execution around those secrets. It keeps requests, approvals and audit metadata; the values stay in your provider. |
| Providers | Name the ones that work today. Azure Key Vault and GCP Secret Manager are on the roadmap; say so when you mention them. |
| Maturity | Open source and pre-1.0. Link to [Product status](../overview/product-status.md) rather than restating it. |

## Words we avoid

seamless, effortless, military-grade, bank-grade, unbreakable, guaranteed, revolutionary, zero-knowledge, production-ready, SOC 2-ready (or any certification we don't hold).

## Examples

=== "README intro"

    ```markdown
    # Secrets Bridge

    Secrets Bridge governs who may use the secrets your team already keeps
    in AWS Secrets Manager or HashiCorp Vault. It adds access requests,
    approvals, audit and agent execution around them. The values stay in
    your provider.
    ```

=== "Error message"

    ```text
    That key is outside the binding's allowed keys for this environment.
    Ask a project admin to check the binding.
    ```

=== "Pull request summary"

    ```markdown
    ## Summary

    The agent now refuses a job that names a different KV mount from the
    one it was configured with. Before, it read from the job's mount.
    ```
