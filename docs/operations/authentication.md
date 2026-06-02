---
title: "Authentication"
description: "Cookie-only session model, account lockout, OIDC sign-in, app-MFA enrollment + step-up, and the break-glass posture."
---

# Authentication

Secrets Bridge ships **two ways to sign in** — OIDC for everyone, local-admin as break-glass — and gates Tier 2 operations (approve, reject, reveal) behind **fresh MFA**. This page explains the model end-to-end so an operator knows what's enforced where.

## The session model (Slices A2 + C)

Sessions are **server-side**, not stateless tokens.

| Concept | Where it lives |
|---|---|
| Identity proof | `sb_session` cookie — HttpOnly, Secure (prod), SameSite=Strict |
| Source of truth | `sessions` table in Postgres — `revoked_at`, `expires_at`, `idle_expires_at`, `last_mfa_at`, `ip`, `user_agent` |
| Cookie content | 32 random bytes, base64url; **SHA-256 stored**, plaintext returned ONCE in Set-Cookie |
| Revocation | Immediate — `UPDATE sessions SET revoked_at = NOW()`; next request fails validation |

**The SPA never holds a token.** Closing the tab + reopening it re-uses the same cookie. Reload, navigate, refresh — all hit the server. There is no `localStorage` / `sessionStorage` keypair to steal.

### TTLs (architect Q3)

| TTL | Default | Behaviour |
|---|---|---|
| Absolute | 8 hours | Hard ceiling from session create; the browser drops the cookie at this point |
| Idle | 30 minutes | Slides forward on every authenticated request; clamped to the absolute TTL |
| Step-up | 15 minutes | `last_mfa_at` must be within this window for Tier 2 ops |

A user who hasn't acted in 30 minutes is logged out idle-side; a user who's been active for 8 straight hours is logged out absolute-side. Both require a fresh login.

## Account lockout (Slice A1)

Five consecutive wrong-password attempts pin the account out for 15 minutes. State lives in Postgres (`local_users.failed_login_count` + `locked_until`), not Redis — a cache flush must **not** silently re-enable a locked account.

Even a *correct* password is rejected during the lock window. The 6th attempt with the right password fails just like the wrong ones — operators must wait out the timer or have a sibling admin clear the lock via psql.

The audit trail captures every state change:

- `auth.login` with `status=denied` + `error_kind=wrong_password` + `failed_login_count=N` — every wrong attempt
- `auth.lockout.applied` — written exactly once, when the threshold is crossed
- `auth.login` with `status=denied` + `error_kind=account_locked` — every attempt against a locked account
- `auth.login` with `status=success` + `BREAK_GLASS_LOGIN` (severity=CRITICAL) — successful sign-in, see below

### Rate limit (per-IP, anti-scan)

| Endpoint | Limit | Window |
|---|---|---|
| `POST /auth/login` | 30 | 60s |
| `GET /auth/oidc/callback` | 60 | 60s |
| `POST /auth/oidc/{logout,backchannel}` | 60 | 60s |
| `POST /agents/:id/heartbeat` | 6 per-agent | 60s |
| `GET /requests/:id/wraps/:wrap_id` | 20 per-user | 60s |

The login / callback caps are **deliberately permissive** so users behind shared CGNAT (an entire ISP or VPC behind one egress IP) aren't locked out by their neighbours. **Brute-force defence lives in the per-account lockout above**, not the per-IP rate limit — the lockout is IP-independent so rotating source IPs doesn't dodge it. Designed against Iraqi CGNAT and similar shared-egress environments.

## OIDC sign-in (Slices B + C + E)

Single Identity Provider (architect Q4). The api refuses to mount the OIDC routes unless `SB_OIDC_ISSUER` is set; until then, only `/auth/login` (local admin) accepts sign-ins.

The flow:

```
SPA → GET /api/v1/auth/oidc/start
api → 302 to IdP with PKCE state/nonce/code_challenge
IdP → user authenticates + consents
IdP → 302 back to /api/v1/auth/oidc/callback?code=...&state=...
api → verify state, exchange code, verify ID token (signature + audience + nonce)
api → JIT upsert local_users row keyed on email-or-sub
api → reconcile user_roles against the configured group claim (see below)
api → stamp last_mfa_at if amr ⊇ {strong-factor}
api → Set-Cookie + 302 to return_to
SPA → /users/me → render
```

### Group-claim → role mapping (Slice E)

`SB_OIDC_GROUP_MAP` is a JSON object mapping IdP group names to Secrets Bridge role names:

```json
{
  "sb-admins":    "admin",
  "sb-approvers": "approver",
  "sb-devs":      "developer"
}
```

The reconciler runs on **every** OIDC sign-in:

- User has a mapped group → grant added (if absent), `granted_by='system:oidc'`
- User no longer has a mapped group → grant revoked
- Mapped role doesn't exist in the catalog → silent skip + audit (typo doesn't 5xx the login)
- Reconcile failure → audited as `auth.oidc.reconcile_failed`; user still signs in

### The reconciler invariant (don't break this)

> The reconciler **only** touches `user_roles` rows with `granted_by = 'system:oidc'`.

Admin-assigned grants — the `SB_BOOTSTRAP_ADMIN_USER_ID` grant, every manually-curated team-scoped grant, every grant created via `POST /api/v1/user-roles` — carry a different `granted_by` value and are **invisible** to the reconciler. They survive every reconcile pass, including the "user belongs to no mapped groups" case.

This protects:

1. The break-glass admin from getting locked out when the IdP returns no groups during an outage.
2. Manually-curated team-scoped grants (which OIDC has no way to express in v1).
3. Operator overrides during incident response.

If you ever find yourself "cleaning up" this filter, **stop**. It is the security boundary, not an accident.

## MFA + step-up (Slices H + I — current model)

Tier 2 operations (approve / reject / reveal-wrap; future: rotate, role-edit, provider-edit) require a session whose `last_mfa_at` is within the step-up TTL.

**The Control Plane owns MFA enrollment + step-up directly.** Identity stays with the IdP; MFA is an app-level concern. This is an architectural inversion of the original Slice D design (described as the legacy path further down). Every user enrolls one or more factors in the SPA at `/me/mfa`; step-up runs through the api's `/auth/mfa/{challenge,verify}` endpoints. Local-admin and OIDC users follow the same enrollment surface and the same step-up flow.

### Factor types

| Kind | Library on the api side | Description |
|---|---|---|
| `totp` | stdlib (RFC 6238, HMAC-SHA1, 6 digits, 30 s step, ±1 step skew) | Compatible with every authenticator app (Google Authenticator, Authy, 1Password, Bitwarden, YubiKey Authenticator). |
| `webauthn` | `github.com/go-webauthn/webauthn` (FIDO2 / WebAuthn) | Hardware-backed: YubiKey, Solo, Titan, platform authenticators (Touch ID / Face ID / Windows Hello). Phishing-resistant by design. |

WebAuthn requires the chart's `api.config.mfa.webauthn.rpId` + `api.config.mfa.webauthn.rpOrigins` to be set. When either is empty the api mounts only the TOTP routes (and the SPA's `/me/mfa` page hides the "Add security key" button). See [Configuration reference](config.md) for the values.

### Enrollment ceremony

Both kinds follow the same two-step shape (Stripe / GitHub / AWS Console model):

1. **`POST /users/me/mfa/<kind>/.../start`** mints the challenge + envelope-encrypts the factor secret + parks the encrypted blob in Redis under a 10-minute challenge id. Nothing lands in Postgres yet.
2. **`POST /users/me/mfa/<kind>/.../confirm` (or `…/finish`)** consumes the Redis blob (GETDEL — single-shot), verifies the user's response, and only then persists the factor row.

A wrong TOTP code or a failed WebAuthn attestation **burns the challenge** — the user restarts from step 1. This blocks an attacker from brute-forcing the 6-digit space against a single secret.

The SPA exposes the enrollment surfaces at `/me/mfa`. A user with zero factors sees an accent-coloured "Add MFA factor →" nudge in the sidebar; an enrolled user sees a quieter "Security" link.

### Step-up ceremony

When a Tier 2 op hits the api's `RequireFreshMFA` gate on a stale session:

```
401 Unauthorized
WWW-Authenticate: step-up max_age=900 acr_values=mfa
```

The SPA's global onError interceptor opens the step-up modal:

1. Modal asks the user to pick a factor — filtered by what they have enrolled.
2. SPA calls `POST /auth/mfa/challenge { kind }` for the chosen kind.
3. **TOTP path** — user types the 6-digit code; SPA calls `POST /auth/mfa/verify { challenge_id, factor_id, code }`.
4. **WebAuthn path** — SPA calls `navigator.credentials.get(...)` with the api-issued options; ships the assertion back via `POST /auth/mfa/verify { challenge_id, response }`.
5. On `204 No Content` the session is MFA-fresh — the api stamped `last_mfa_at` on the **same session row** (no new cookie). The user re-clicks the original button.

### Two related responses the interceptor routes

| Response | What it means | SPA action |
|---|---|---|
| `412 mfa_enrollment_required` | User has zero factors enrolled. | Navigate to `/me/mfa`. The step-up modal would be a dead-end. |
| `401 factor_compromised` | WebAuthn sign-count regression — the api detected a possible cloned authenticator and revoked every session for the user. | Hard-navigate to `/login`. |

### Recommended factor priority

When you onboard users, encourage this enrollment order:

1. **WebAuthn (hardware key — YubiKey, Solo, Titan)** — phishing-resistant, no shared secret on the device, no battery.
2. **WebAuthn (platform — Touch ID / Face ID / Windows Hello)** — phishing-resistant, no extra device to carry, but tied to one machine.
3. **TOTP via authenticator app (Aegis, 1Password, Authy)** — universal fallback; vulnerable to phishing kits that proxy the code.
4. **SMS / email OTP** — Secrets Bridge does NOT support this. SIM swap and email-account takeover are well-documented bypasses.

Operators should enrol **at least two factors** per privileged user — one hardware key plus one TOTP backup — so a lost YubiKey doesn't lock them out of Tier 2 ops.

### Step-up vs login-time MFA

The default posture (Slices H + I) gates **only Tier-2 ops** (approve / reject / reveal-wrap). Sign-in itself + Tier-1 browsing (lists, dashboards) only need a session cookie. The argument: the session cookie is the high-value loot — step-up makes "I have your cookie" insufficient at the moment of a sensitive action without paying the ergonomic cost of a modal on every page load.

The alternative posture — **login-time MFA on every authenticated route** — is available via the Slice K opt-in knob.

Set `api.config.mfa.requireMFAAtLogin: true` (renders `SB_REQUIRE_MFA_AT_LOGIN=true`) to enable. When the knob is on:

- A fresh session with no MFA stamp returns `401 step_up_required` on every Tier-1 route (lists, dashboards, project pages).
- The SPA's global onError interceptor opens the step-up modal **immediately after sign-in** before the user reaches any value-bearing surface.
- A user with no factor enrolled is bounced to `/me/mfa` via the `412 mfa_enrollment_required` shape (the same response the existing 412 path uses).
- Tier-2 routes still enforce the 15-min freshness window via the per-route `RequireFreshMFA`.

Carve-outs the gate ALWAYS allows through (so it isn't self-locking):

```
GET    /api/v1/users/me                 SPA identity hydration
GET    /api/v1/users/me/projects        identity-adjacent
GET    /api/v1/users/me/mfa/factors     SPA factor-kind picker
POST   /api/v1/users/me/mfa/totp/*      enrollment must reach
POST   /api/v1/users/me/mfa/webauthn/*  the user pre-stamp
DELETE /api/v1/users/me/mfa/factors/:id factor removal
POST   /api/v1/auth/logout              always allow sign-out
POST   /api/v1/auth/mfa/challenge       the gate's own ceremony
POST   /api/v1/auth/mfa/verify          ditto
```

Pick the posture by environment, not by user:

| Posture | When it fits |
|---|---|
| **Step-up only** (default) | Dev clusters, single-tenant deployments, deployments where users browse infrequently and verifying on every access would be friction without benefit. |
| **Login-time MFA** (`requireMFAAtLogin: true`) | Production multi-tenant deployments, regulated environments (SOC2 / ISO 27001 audit), AWS-Console / GitHub-org-with-2FA-required parity. |

The two postures share the same factor enrollment surface (`/me/mfa`) and the same verify endpoint (`/auth/mfa/verify`) — the gate position is the only difference. Switching between them is a single env-var change + pod roll; users keep their enrolled factors.

## OIDC-trust MFA (Slice D — legacy, opt-in)

The api retains the original Slice D path for deployments whose IdP genuinely owns MFA (Microsoft Entra / Okta with strong-factor policy bound), so an operator can keep that posture during a transition window.

Set `api.config.oidc.trustAmrForMFA: true` (renders `SB_OIDC_TRUSTED_AMR_MFA=true`) to opt in. When enabled, the OIDC callback stamps `last_mfa_at` on the session whenever the ID-token `amr` claim includes one of the RFC 8176 strong-factor identifiers:

| Factor | Code |
|---|---|
| Multi-factor (explicit) | `mfa` |
| One-time password | `otp` |
| Hardware key | `hwk` |
| FIDO2 / WebAuthn | `fido` |
| Software-secured key | `swk` |
| Smart card | `sc` |
| Proof-of-possession | `pop` |
| Biometric — iris | `eye` |
| Biometric — fingerprint | `fpt` |
| Biometric — retina | `retina` |

`pwd` and `kba` are not strong. **The app-MFA path (above) runs in parallel** — a user can still satisfy step-up via `/auth/mfa/verify` even when the OIDC-trust knob is on. Operators flip this knob OFF (the default) once every user has enrolled an app-MFA factor; `amr` continues to be recorded in audit either way.

**Hard rule:** `SessionService.MarkMFA` only fires from `MFAVerifyService.Verify` (the app path) OR from the OIDC callback when `TrustAMRForMFA=true`. The architectural invariant is that exactly one path writes `last_mfa_at`. New callers in the api codebase need explicit justification or the step-up gate's contract collapses.

## Break-glass (local-admin) policy (architect Q1)

Local-admin sign-in via `/auth/login` is the **break-glass surface** — the way operators sign in when the IdP is down, the OIDC client is misconfigured, or the network is partitioned. It is **not** the day-to-day sign-in path once OIDC is configured.

Every successful local-admin sign-in emits a high-severity audit event:

```
action:   BREAK_GLASS_LOGIN
status:   success
severity: CRITICAL    (in metadata)
actor:    user:<uuid>
```

**Route this audit action into your alert pipeline.** Splunk / Datadog / Grafana Alertmanager — whichever you use, page the on-call when a `BREAK_GLASS_LOGIN` shows up outside of an open incident bridge. The Slack notification recipe:

```yaml
# Example: worker notification sink (when configured) or external SIEM rule
when:
  action: BREAK_GLASS_LOGIN
  severity: CRITICAL
then:
  notify:
    channel: "#security-incidents"
    message: |
      Break-glass local-admin login by ${actor}.
      Expected? If not, open an incident.
      Session ID: ${metadata.session_id}
      IP: ${metadata.ip}
      User-agent: ${metadata.user_agent}
```

### Local-admin sessions + step-up

Local-admin users go through the **same app-MFA enrollment + step-up surfaces as OIDC users**. The local-admin sign-in path does not stamp `last_mfa_at` directly — every Tier 2 op the operator runs is gated by a fresh `/auth/mfa/verify` against an enrolled factor.

Operationally this means:

- A local-admin user with no factor enrolled hits `412 mfa_enrollment_required` on the first Tier 2 op and is routed to `/me/mfa` to enrol.
- After enrolling, every Tier 2 op runs through the step-up modal — same flow as OIDC users.
- If the operator is in the middle of an IdP outage and *also* hasn't enrolled an MFA factor, they should enrol one immediately — the IdP outage doesn't block factor enrollment, and once enrolled they can satisfy step-up without the IdP.

This is a tighter posture than the pre-H4 architecture, where local-admin users were forced through `/auth/oidc/start?step_up=mfa` for every Tier 2 op and effectively couldn't approve anything during an IdP outage. App-MFA closes that gap.

If you're routinely approving as the break-glass user, your operating model is still wrong — that account should be reserved for "the IdP is broken and I need to fix it." But during a real IdP outage the break-glass user can now approve cleanly without an additional dependency.

### Disabling break-glass entirely

For deployments that want to refuse local-admin sign-in once OIDC is configured, the chart will gain a `SB_LOCAL_ADMIN_ENABLED=false` flag in a follow-up. Today the flag is implicit — leave `SB_BOOTSTRAP_ADMIN_EMAIL` unset and no local-admin account exists, so `/auth/login` always fails with `invalid credentials`.

## Direct reveal permission (Slice L4)

Slice L4 added `secret.reveal.direct` to the permission catalog and seeded it onto the bootstrap `developer` role.

The permission is a NECESSARY but NOT SUFFICIENT gate. Three conditions must all hold for a direct-reveal request to auto-execute:

1. The caller holds `secret.reveal.direct` (route-level `auth.Require`).
2. The matched `policy_rules` row has `direct_reveal_allowed=true`.
3. The matched environment's `kind` is `non_prod`.

If any one of these fails, the API returns 403 and the SPA shows an inline error. The dev endpoint never bypasses approval against a `prod`-classified env — the PolicyEngine zeroes `direct_reveal_allowed=true` server-side regardless of operator misconfig. See [Project environments](project-environments.md#kind-vs-type-why-both) for the `kind` model and [Policy templates](policy-templates.md#template-1-non-prod-direct-reveal) for ready-to-paste rules.

Operators who want a stricter baseline can strip `secret.reveal.direct` from the developer role via the existing Roles admin endpoint — the rest of the developer surface (`secret.request`, `audit.read`) is unaffected.

## What this page does NOT cover

- **RBAC enforcement** at the route level. Sidebar nav already hides admin pages without `team.edit` / `role.edit`; route-level enforcement on the api lands in a follow-up.
- **Audit log forwarding** to SIEM. The api emits structured slog JSON; pick that up with Fluent Bit / Vector and route to wherever.
- **mTLS for agent ↔ api**. Slice B of the workload-identity track replaces the static agent secret with a SPIFFE / IRSA-backed identity. Tracked separately from the user-auth series.

For the chart-side knobs (`api.config.oidc.*`, `api.config.bootstrap.userId`), see [Configuration reference](config.md). For the underlying threat model + hard rules, see [Threat model](../overview/threat-model.md).
