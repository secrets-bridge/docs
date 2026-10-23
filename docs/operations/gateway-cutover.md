---
title: Gateway cutover
description: "Move an install from the retired control-plane Argo CD poller to Gateway observation: bind Gateways first, upgrade, rotate the Argo CD token, clean up."
---

# Gateway cutover

The control plane no longer talks to Argo CD. A [Gateway](gateway.md) inside
your boundary is the only Secrets Bridge component that reads Argo CD. The api
has no Argo CD client and no Argo CD endpoint or app-mapping routes, the worker
has no poller, and the control plane stores no Argo CD token.

This page is for installs that used the old control-plane poller
(`SB_GITOPS_ENABLED` on the api and `SB_WORKER_GITOPS_ENABLED` on the worker)
and are upgrading to an api that includes migration `0049`. If you never turned
the poller on, the upgrade only changes the default observation source to
`none`. Skip to [After upgrading](#after-upgrading), steps 3 to 6.

!!! danger "Action required: rotate the Argo CD account token"
    The token you gave the control plane sat in its Postgres as a KMS
    envelope. The upgrade deletes it, but database backups taken before the
    upgrade still hold the ciphertext until they age out, and it stays
    decryptable while the KMS key exists. Rotate or delete that token on the
    Argo CD side ([step 1 after upgrading](#after-upgrading)).

```mermaid
flowchart TD
    A["Before: bind a Gateway per environment<br/>that used the poller, check the panel"] --> B["Upgrade api and worker together"]
    B --> C["Migration 0049:<br/>tokens purged, tables dropped,<br/>control_plane environments move to none"]
    C --> D["After: rotate the Argo CD token,<br/>remove egress, retired settings and worker KMS access"]
    D --> E["Set each environment's<br/>observation source to gateway"]
```

## Before upgrading

On the version you run today, the poller and the Gateway can both be
configured, and each environment uses one of them at a time. Use that to move
every environment to a Gateway before the poller goes away.

1. **List what the poller observes.** Each environment with the source
   `control_plane` and at least one Argo CD app mapping is observed by the
   poller. Note the Argo CD instance and the applications mapped to each
   secret. After the upgrade these records are gone, so write them down now.
2. **Install and enroll a Gateway** in each boundary that can reach those Argo
   CD instances, with a read-only Argo CD account of its own. Follow
   [Gateway](gateway.md), steps 1 to 6. Do not reuse the token you gave the
   control plane.
3. **Approve the connector and bind each application** that had a mapping to
   the same secret scope, in the same environment
   ([step 7](gateway.md#7-approve-the-connector-and-bind-a-target)).
4. **Turn on the worker's Gateway sweepers**
   ([step 9](gateway.md#9-turn-on-the-worker-sweepers)). With the
   `secrets-bridge` chart, set `worker.config.gatewaySweepers.enabled=true`.
   The chart always renders `SB_WORKER_GATEWAY_SWEEPERS_ENABLED`, and the
   rendered value wins over one in the env Secret. If the chart version you
   run today has no `gatewaySweepers` values, set
   `SB_WORKER_GATEWAY_SWEEPERS_ENABLED=true` in the env Secret for now and
   move it to the chart value when you upgrade the chart.
5. **Check parity on one environment.** Switch it to `gateway`
   ([step 8](gateway.md#8-switch-the-environment-to-gateway-observation)),
   submit and approve a change to a bound secret, and open the request page.
   The **Argo CD (observed by Gateway …)** panel shows, for each bound
   application, the facts the poller used to store: **Sync**, **Health**,
   **Last operation** and **Revision**. Each one is labelled observed
   operational state and carries the caveat that Argo CD health is not proof
   the new value reached the app. The api's parity test checks the same thing.
6. Repeat step 5 for every environment that used the poller, or move them in
   one go after the upgrade (step 6 after upgrading).

An environment that has no Gateway when you upgrade still works. Its requests
run as before and show no Argo CD state until a Gateway observes them.

## What the upgrade does

Upgrade the api, the worker and the `secrets-bridge` chart in the same
release. The api applies migration `0049` when it starts. An older worker with
the poller still on would read tables that the migration drops.

Migration `0049`:

- Writes one `argocd_endpoint.token_purged` audit row for each
  `argocd_endpoints` row, soft-deleted rows included. The actor is
  `system:migration`, the resource is `argocd_endpoint:<id>`, and the metadata
  holds only `environment_id`, `changed_keys` (the four token column names) and
  `reason: gateway_cutover`.
- Drops `argocd_endpoints`, and with it every token envelope
  (`token_ciphertext`, `token_data_key_ciphertext`, `token_nonce`,
  `token_kms_key_id`). It also drops `gitops_app_mappings`.
- Moves every environment whose observation source is `control_plane` to
  `none`, with one `environment.observation_source.update` audit row each
  (`observation_source_before: control_plane`, `observation_source_after:
  none`).
- Makes `none` the default source and refuses `control_plane` from then on.
  `PUT /admin/environments/:id/observation-source` with `control_plane`
  answers `400 source_retired`.
- Keeps `gitops_observations`. The poller's old rows are not rewritten and stay
  readable to the requester at `GET /api/v1/requests/:id/gitops`, each labelled
  `history_context_only` with a `history_status`
  ([API reference](../reference/api-endpoints.md#requests-access-requests)). The console shows
  them to the requester in the muted **Argo CD history (before the Gateway)**
  card on the request page, which is hidden when a request has none.

The migration is idempotent: a second run drops nothing, moves nothing and
writes no audit row.

To confirm it ran, read the audit log (needs `audit.read`, using the session
from [Gateway, step 2](gateway.md#2-sign-in-and-step-up)):

```bash
curl -fsS -b "$JAR" "$CP/api/v1/audit-events?actor=system:migration&action=argocd_endpoint.token_purged" \
  | jq 'map({resource, metadata})'
curl -fsS -b "$JAR" "$CP/api/v1/audit-events?actor=system:migration&action=environment.observation_source.update" \
  | jq 'map({resource, metadata})'
```

## After upgrading

1. **Rotate or delete the Argo CD account token on the Argo CD side.** Revoke
   the token of the Argo CD account you gave the control plane, or delete the
   account if only the control plane used it. For a local account:

    ```bash
    argocd account get --account <cp-account>           # lists token ids
    argocd account delete-token --account <cp-account> <token-id>
    ```

    Backups taken before the upgrade keep the old ciphertext until they age
    out. Rotating the token makes it worthless.

2. **Remove Argo CD egress from the api and the worker.** Delete any rule you
   added so the control plane could reach Argo CD: entries in
   `api.networkPolicy.egress.extraRules` and
   `worker.networkPolicy.egress.extraRules` of the `secrets-bridge` chart, and
   any firewall rule outside the cluster. Only the Gateway reaches Argo CD,
   through the NetworkPolicy of its own chart.

3. **Remove the retired values and settings.** The `secrets-bridge` chart no
   longer has these values, and Helm ignores them if they are left in a values
   file. Delete them from your values files:

    ```yaml
    api:
      config:
        gitopsEnabled: false        # remove
    worker:
      config:
        gitopsEnabled: false        # remove
        gitopsPollInterval: 15s     # remove
        gitopsTimeoutInterval: 1m   # remove
        gitopsHttpTimeout: 15s      # remove
        gitopsBatchSize: 20         # remove
    ```

    The chart no longer renders `SB_GITOPS_ENABLED`,
    `SB_ALLOW_INSECURE_ARGOCD_ADDR` or `SB_WORKER_GITOPS_*`. If one of them is
    still in your env Secret, the api or the worker logs its name once at
    startup, never its value, and ignores it. Remove it from the Secret. See
    [Retired settings](config.md#retired-settings).

4. **Remove the worker's KMS access.** The worker opened the KMS backend only
   to unwrap stored Argo CD tokens. It no longer reads `SB_KMS_*`, and the
   chart no longer sets them on the worker. Take the KMS permissions off the
   worker's identity: its IAM role (`worker.serviceAccount.annotations`) for
   `aws-kms`, or its Vault policy for `vault-transit`. Drop any worker egress
   rule that exists only for the KMS endpoint. Leave the api's KMS access
   alone: it still needs it for wraps and its other envelopes.

    The chart still mounts the shared env Secret (`secrets.existingSecret`)
    into the worker through `envFrom`, and the chart has no separate Secret for
    the worker. Any KMS credential stored in that Secret, such as
    `SB_KMS_VAULT_TOKEN`, is therefore still in the worker's environment,
    although the worker ignores it. With `aws-kms`, give the KMS permissions
    to the api's IRSA role (`api.serviceAccount.annotations`) so no KMS
    credential sits in the shared Secret. With `vault-transit`, the Vault
    token in the shared Secret still reaches the worker's environment.

5. **Keep the Gateway sweepers on.** Check that
   `worker.config.gatewaySweepers.enabled` is `true` in your values. If you
   set `SB_WORKER_GATEWAY_SWEEPERS_ENABLED` in the env Secret before the
   upgrade, move it to this value: the chart now renders the variable, and
   the rendered value (`false` by default) wins over the Secret. The interval
   values are listed in the
   [configuration reference](config.md#worker).

6. **Set each environment's observation source to `gateway`** once a Gateway
   is bound for it
   ([step 8](gateway.md#8-switch-the-environment-to-gateway-observation)).
   Environments the migration moved to `none` stay unobserved until you do.
   The source is read when a request reaches `executed`, so requests executed
   before the switch get no tasks.

7. **Use the console as it is now.** Admin → Integrations and its Argo CD
   endpoint and app-mapping pages are gone. Argo CD is configured on the
   Gateway (Admin → Gateways). On a project's **Environments** tab, the
   **Observation** dialog offers **Gateway** and **None**; an environment with
   no stored source shows **None**.

## Rollback

Redeploying an older api does not restore the control-plane path. The Argo CD
tokens and the endpoint and mapping tables are gone, and the down migration
restores the schema only: no token comes back and no environment returns to
`control_plane`. There is no setting that turns the poller back on.

Until a Gateway runs and its environment is set to `gateway`, observation shows
as unavailable or unverified: requests carry no Argo CD state, or their tasks
end `timed_out` (`gateway_unavailable`) at the deadline. Neither fails the
request. Both clear once a bound Gateway is running.
