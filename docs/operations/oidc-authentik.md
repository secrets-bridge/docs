---
title: "OIDC with Authentik"
description: "Step-by-step Authentik setup for Secrets Bridge, application, scopes, group claim, WebAuthn enrolment."
---

# OIDC with Authentik

This guide configures [Authentik](https://goauthentik.io/) as the IdP for Secrets Bridge. Authentik is the **worked example**, Keycloak, Okta, Auth0, and Entra ID work the same way; the screens are different but the contract (issuer URL, client id / secret, redirect URL, scopes, group claim) is identical.

Prerequisites:

- A running Authentik instance with admin access.
- A running Secrets Bridge installation. See [Bootstrap & first sign-in](bootstrap.md).
- A public hostname for the SPA + api, e.g. `https://secrets-bridge.example.com`.

## 1. Create the application in Authentik

In the Authentik admin:

1. **Applications → Applications → Create**
   - Name: `Secrets Bridge`
   - Slug: `secrets-bridge`
   - Group: (your choice, controls who can see it in the user library)
2. **Applications → Providers → Create → OAuth2/OpenID Provider**
   - Name: `secrets-bridge`
   - Authorization flow: `default-provider-authorization-explicit-consent` (or implicit, your call)
   - Client type: **Confidential**
   - Client ID: `secrets-bridge` (or whatever, note it down)
   - Client Secret: Authentik generates one, note it down, store it in the env Secret
   - Redirect URIs: `https://secrets-bridge.example.com/api/v1/auth/oidc/callback`
   - Signing key: the same key your other apps use, or `authentik Self-signed Certificate`
   - Scopes: leave the default OpenID + profile + email scopes selected; **also enable the `groups` scope** (Authentik exposes group memberships via this scope)
3. Back in the Application, bind the provider you just created.

The **issuer URL** you'll need for Secrets Bridge is:

```
https://authentik.example.com/application/o/secrets-bridge/
```

(Note the **trailing slash**, Authentik's discovery endpoint is `<issuer>/.well-known/openid-configuration` and that resolves only with the slash present.)

## 2. Configure the group claim

Group-claim → role mapping is the architect Q5 deferral that Slice E delivered. The reconciler reads the `groups` claim by default and maps each IdP group to a Secrets Bridge role.

Authentik emits the `groups` claim automatically when the `groups` scope is granted on the provider, no scope mapper to configure.

If your Authentik install has groups named differently from your Secrets Bridge roles, set the map in `values.yaml`:

```yaml
api:
  config:
    oidc:
      groupClaim: groups   # the default; matches Authentik
      groupMap:
        sb-admins:    admin
        sb-approvers: approver
        sb-devs:      developer
```

The chart serializes this map to JSON and exposes it as `SB_OIDC_GROUP_MAP`. The api binary's `ValidateOIDCGroupMap` fails the boot if the JSON is malformed or has empty keys/values, operators get the signal up front, not as a 401 in production.

### The reconciler invariant (you cannot disable this)

The reconciler **only** touches `user_roles` rows with `granted_by = 'system:oidc'`. Admin-assigned grants are invisible to it. See [Authentication → The reconciler invariant](authentication.md#the-reconciler-invariant-dont-break-this) for what this protects. Repeat in your runbook so the next on-call doesn't relax the filter as "cleanup."

## 3. Configure Secrets Bridge

In your chart values:

```yaml
api:
  config:
    oidc:
      issuer:             "https://authentik.example.com/application/o/secrets-bridge/"
      clientId:           "secrets-bridge"
      redirectUrl:        "https://secrets-bridge.example.com/api/v1/auth/oidc/callback"
      scopes:             "openid profile email groups"
      postLogoutRedirect: "https://secrets-bridge.example.com/"
      groupClaim:         groups
      groupMap:
        sb-admins:    admin
        sb-approvers: approver
        sb-devs:      developer
```

And in the env Secret (`secrets.existingSecret`, typically `secrets-bridge-env`):

```
SB_OIDC_CLIENT_SECRET=<the secret Authentik generated above>
```

Apply the chart upgrade:

```bash
helm upgrade secrets-bridge ./charts/secrets-bridge \
  -n secrets-bridge \
  -f my-values.yaml
```

The api pod rolls automatically, the chart's `checksum/config` annotation includes the OIDC issuer + groupMap, so a Helm upgrade that flips OIDC on/off or rewrites the mapping triggers a fresh pod.

## 4. Sign in

Browse to `https://secrets-bridge.example.com/login`. The SPA probes the api for OIDC availability via `/api/v1/auth/oidc/start` and renders the **"Sign in with SSO"** button above the local-admin form when OIDC is mounted.

Click it. The redirect chain runs:

1. SPA → api `/auth/oidc/start` → Authentik authorize endpoint
2. Authentik prompts for credentials (and MFA, see below)
3. Authentik → api `/auth/oidc/callback?code=...&state=...`
4. api verifies + JIT-creates the user + reconciles roles + Set-Cookie
5. api → 302 to the SPA's original page

If your user's `groups` claim contained `sb-admins`, the reconciler grants the `admin` role on the way through. Your first sign-in lands you on the Dashboard with full permissions.

If your `groups` claim contained none of the mapped groups, the user is provisioned with **no role grants**. An admin must assign one from `/admin/assignments` before the user can do anything beyond `/users/me`.

## 5. MFA, Authentik vs the Control Plane

**The current model has the Control Plane own MFA enrollment + step-up directly.** Identity stays with Authentik; users enrol a TOTP factor or a WebAuthn credential in the Secrets Bridge SPA at `/me/mfa`; step-up runs through the api's `/auth/mfa/{challenge,verify}` endpoints. See [Authentication → MFA + step-up](authentication.md#mfa-step-up-slices-h-i-current-model) for the full model. You do **not** need to configure MFA inside Authentik for Secrets Bridge to enforce it.

If you want Authentik to handle MFA on the IdP side instead (so the same MFA stage protects every app behind Authentik, not just Secrets Bridge), set `api.config.oidc.trustAmrForMFA: true` in the chart. The api will then stamp `last_mfa_at` when the ID-token `amr` claim carries an RFC 8176 strong factor, see [Authentication → OIDC-trust MFA (Slice D, legacy)](authentication.md#oidc-trust-mfa-slice-d-legacy-opt-in). The two paths run in parallel; users on a `trustAmrForMFA: true` deployment can still satisfy step-up via the app-MFA path if they prefer.

The IdP-trust path remains useful when you have a uniform MFA policy across many apps (Entra / Okta with org-wide WebAuthn enforcement). Most Secrets Bridge deployments are simpler with the app-MFA default.

### Enabling MFA in Authentik (only if you flip `trustAmrForMFA: true`)

1. **Flows & Stages → Stages → Create → WebAuthn Authenticator Setup**
2. Add the stage to your default authentication flow (or a user-self-enrolment flow).
3. Mark the stage as **required** for users with any of your `sb-admins` / `sb-approvers` groups, those are the people who'll need step-up MFA on every approve.

### Verifying `amr` is correct (IdP-trust path only)

After a user signs in with WebAuthn through Authentik, check the audit row on the Secrets Bridge side:

```sql
SELECT metadata->>'amr', metadata->>'session_id', occurred_at
FROM audit_events
WHERE action = 'auth.oidc.callback'
ORDER BY occurred_at DESC
LIMIT 5;
```

You should see `amr` as `["mfa"]` (or `["pwd","mfa"]` for a password-then-WebAuthn flow). If you only see `["pwd"]`, the IdP did not assert MFA, Tier 2 ops will demand step-up via the app-MFA path (a fine outcome if you've enrolled the factor there) OR fail closed (if you haven't). That's a sign your Authentik flow isn't enforcing the WebAuthn stage; users with an app-MFA factor stay unaffected.

## 6. Step-up flow in action

The first time the user tries to approve a request, they'll see:

1. SPA opens the request detail → clicks **Approve**
2. SPA `POST /requests/:id/approve` → api returns `401 step_up_required` (session is MFA-stale)
3. SPA's global step-up interceptor opens the step-up modal
4. User picks their factor, TOTP code or tap their security key
5. SPA `POST /auth/mfa/verify` → api stamps `last_mfa_at` on the **same session row** (cookie unchanged) → `204 No Content`
6. Modal closes → user re-clicks **Approve** → 200

The "cookie unchanged" invariant is critical, see [Authentication → Step-up ceremony](authentication.md#step-up-ceremony). Your audit chain stays continuous; the session ID never changes.

## 7. Back-channel logout

Authentik supports RFC 8417 back-channel logout. To wire it:

1. In the provider settings: enable **Back-channel logout** and set the URL to:
   ```
   https://secrets-bridge.example.com/api/v1/auth/oidc/backchannel
   ```
2. Authentik will POST a `logout_token` to this URL when the user signs out of Authentik (single sign-out across applications).
3. The Secrets Bridge api verifies the token signature + audience + the `events` claim, then revokes **every** server-side session for the user's `sub`. The user is signed out of Secrets Bridge immediately.

## 8. Troubleshooting

| Symptom | Likely cause |
|---|---|
| "OIDC routes don't appear on /login" | `SB_OIDC_ISSUER` is empty; SPA probes 404 and hides the button. Check the api logs for the `oidc disabled` line at boot. |
| "Login succeeds but I have no permissions" | The user's `groups` claim doesn't include any mapped group, OR the role name in `groupMap` doesn't exist in the role catalog. Check the `auth.oidc.role_reconcile` audit row, `metadata.added` will be empty. |
| "User has admin BUT shouldn't" | An admin-assigned grant exists for them (`granted_by != 'system:oidc'`). The reconciler can't see it. Revoke via `/admin/assignments` or `DELETE /api/v1/user-roles/:id`. |
| "Tier 2 ops still step up after I enabled WebAuthn" | The `amr` claim doesn't contain a strong factor. Run the SQL in §5 to verify. Usually the WebAuthn stage isn't bound to the authentication flow, or it's optional and the user skipped it. |
| "Boot fails with 'SB_OIDC_GROUP_MAP must be a JSON object…'" | The chart was given a non-object groupMap (e.g. a list) OR an entry has an empty role name. Fix the values and `helm upgrade` again. |

## See also

- [Authentication overview](authentication.md), full auth model
- [Bootstrap & first sign-in](bootstrap.md), local-admin setup before OIDC lands
- [Configuration reference](config.md), every env var, including the `SB_OIDC_*` set
