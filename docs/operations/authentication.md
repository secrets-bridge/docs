---
title: "Authentication"
description: "Cookie-only session model, account lockout, OIDC + MFA step-up, and the break-glass posture."
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

## MFA + step-up (Slice D)

Tier 2 operations (approve / reject / reveal-wrap; future: rotate, role-edit, provider-edit) require a session whose `last_mfa_at` is within the step-up TTL. A stale or unstamped session gets:

```
401 Unauthorized
WWW-Authenticate: step-up max_age=900 acr_values=mfa
```

The SPA's global step-up interceptor catches this and redirects to:

```
GET /api/v1/auth/oidc/start?step_up=mfa&return_to=<current page>
```

which forwards to the IdP with `prompt=login&max_age=0&acr_values=mfa`. The IdP re-prompts for the second factor even with an alive SSO session. The api callback stamps `last_mfa_at` on the **same session row** — the cookie value does not change. The user returns to the original page; the cookie they had before is the cookie they have after. Audit chains, revocation semantics, and idle-TTL slides are all preserved.

### Strong-factor recognition (`amr`)

The `last_mfa_at` stamp only fires when the IdP's ID-token `amr` claim includes one of the RFC 8176 strong-factor identifiers:

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

`pwd` (password alone) and `kba` (knowledge-based answer) are explicitly **not** strong. A password-only IdP cannot accidentally stamp MFA.

### Recommended factor priority

When you configure MFA on your IdP, use this priority order:

1. **FIDO2 / WebAuthn (hardware keys)** — phishing-resistant, no shared secret on the device, no battery. YubiKey, Solo, built-in TouchID/Windows-Hello.
2. **Hardware OTP token** — Yubico, RSA SecurID. Better than software OTP because the device can't be cloned to a malware-controlled phone.
3. **Software TOTP** — Aegis, 1Password, Authy. Fine for most users; vulnerable to phishing kits that proxy the TOTP code.
4. **SMS / email OTP** — **avoid**. SIM swap and email-account takeover are well-documented bypasses.

If your IdP supports it, prefer **WebAuthn first** in the user enrolment flow so new users register a hardware key before they fall back to software TOTP.

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

### Local-admin sessions are NEVER MFA-fresh

`last_mfa_at` is only stamped via OIDC callback when `amr` carries a strong factor. Local-admin sessions never go through OIDC, so they never get a stamp. Every Tier 2 operation **forces a step-up to OIDC** — even when the user is a local-admin. This is intentional. Break-glass proves *who you are*; it does not prove *fresh MFA*.

Concretely: a local-admin user can sign in during an IdP outage and see the dashboard, but they **cannot** approve a request or reveal a secret until OIDC is back up and they step up. If you're routinely approving as the break-glass user, your operating model is wrong — that account should be reserved for "the IdP is broken and I need to fix it."

### Disabling break-glass entirely

For deployments that want to refuse local-admin sign-in once OIDC is configured, the chart will gain a `SB_LOCAL_ADMIN_ENABLED=false` flag in a follow-up. Today the flag is implicit — leave `SB_BOOTSTRAP_ADMIN_EMAIL` unset and no local-admin account exists, so `/auth/login` always fails with `invalid credentials`.

## What this page does NOT cover

- **RBAC enforcement** at the route level. Sidebar nav already hides admin pages without `team.edit` / `role.edit`; route-level enforcement on the api lands in a follow-up.
- **Audit log forwarding** to SIEM. The api emits structured slog JSON; pick that up with Fluent Bit / Vector and route to wherever.
- **mTLS for agent ↔ api**. Slice B of the workload-identity track replaces the static agent secret with a SPIFFE / IRSA-backed identity. Tracked separately from the user-auth series.

For the chart-side knobs (`api.config.oidc.*`, `api.config.bootstrap.userId`), see [Configuration reference](config.md). For the underlying threat model + hard rules, see [Threat model](../overview/threat-model.md).
