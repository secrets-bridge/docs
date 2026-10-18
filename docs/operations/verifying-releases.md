---
title: Verifying images and charts
description: Check the cosign signature, SBOM and build provenance of Secrets Bridge container images and Helm charts before you deploy them.
---

# Verifying images and charts

Every container image (`api`, `ui`, `worker`, `agent`, `controller`) and
both Helm charts are signed by the GitHub Actions workflow that built them,
using cosign keyless signing. Each image also carries an SPDX SBOM and SLSA
build provenance. Verify them before you deploy, and pin images by digest
in production, as the charts require.

!!! info "No versioned release yet"
    All repos will release together under one shared version (`v0.1.0`,
    `v0.2.0`, and so on). Until the first release is tagged, the published
    artifacts are the `main` builds: `:dev`, `:main` and `:sha-<short>`
    images and `X.Y.Z-dev.<sha>` charts. They are signed the same way, by
    the workflow running on `refs/heads/main`.

## What is signed and attached

| Artifact | Where | Signed by | Attached |
|---|---|---|---|
| Images | `ghcr.io/secrets-bridge/<api\|ui\|worker\|agent\|controller>` | `https://github.com/secrets-bridge/<repo>/.github/workflows/docker-publish.yml@<ref>` | SPDX SBOM, SLSA provenance |
| Charts | `oci://ghcr.io/secrets-bridge/charts/secrets-bridge` and `.../secrets-bridge-agent` | `https://github.com/secrets-bridge/charts/.github/workflows/chart-publish.yml@<ref>` | none |

`<ref>` is `refs/tags/vX.Y.Z` for a release and `refs/heads/main` for a
`main` build. The image signature covers the multi-arch index and each
platform image in it.

## Verify an image

```bash
cosign verify ghcr.io/secrets-bridge/api:0.1.0 \
  --certificate-identity https://github.com/secrets-bridge/api/.github/workflows/docker-publish.yml@refs/tags/v0.1.0 \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

For a `main` build, use the `sha-<short>` tag (or the digest) and
`@refs/heads/main` as the identity. Verification fails if the image was
signed by any other repository or workflow.

## Inspect the SBOM and provenance

```bash
docker buildx imagetools inspect ghcr.io/secrets-bridge/api:0.1.0 --format '{{ json .SBOM }}'
docker buildx imagetools inspect ghcr.io/secrets-bridge/api:0.1.0 --format '{{ json .Provenance }}'
```

The SBOM lists the packages in the image. The provenance records the
source repository, the commit and the build parameters.

## Verify a chart

```bash
cosign verify ghcr.io/secrets-bridge/charts/secrets-bridge:0.1.0 \
  --certificate-identity https://github.com/secrets-bridge/charts/.github/workflows/chart-publish.yml@refs/tags/v0.1.0 \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

## Release pages

Each release has a GitHub Release in every repo, with the changes for that
version, the exact image or chart digests and these commands filled in.
Release tags are never moved or reused: a broken release is followed by a
new patch version.
