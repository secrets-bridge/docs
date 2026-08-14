# Bootstrap & first sign-in

After the api starts for the first time, the platform has to be
**bootstrapped** with a usable admin identity. Otherwise nothing
can be done: every write endpoint is gated by
`auth.Require(perm)` and there are no role assignments yet.

## What "bootstrapped" means

Two things happen on first boot when `local_users` is empty and
the bootstrap env vars are set:

1. **A local admin user is created**, bcrypt-hashed password
   stored in `local_users` (idempotent: a second boot with the
   same env vars is a no-op once any user exists).
2. **The new user is bound to the seed `admin` role** with global
   scope, via the existing user_roles flow.

The api logs both actions at INFO so you can see them in
`docker logs secrets-bridge-api-1`:

```
{"msg":"bootstrap local admin created","user_id":"<uuid>","email":"admin@example.com"}
{"msg":"bootstrap admin assignment created","user_id":"<uuid>","role":"admin","scope":"global"}
```

## Configuration

| Env var | Required | Default | Notes |
|---|---|---|---|
| `SB_BOOTSTRAP_ADMIN_EMAIL` | recommended on first boot |  | Becomes the local-admin email |
| `SB_BOOTSTRAP_ADMIN_PASSWORD` | recommended on first boot |  | **Rotate immediately after first sign-in** |
| `SB_BOOTSTRAP_ADMIN_USER_ID` | optional |  | Pre-OIDC escape hatch: assigns the admin role to a specific opaque `user_id` (matches the future OIDC `sub` claim). Use this alongside `_EMAIL`/`_PASSWORD` if you want both the local-admin login and a pre-arranged OIDC identity to hold admin. |

## First sign-in

1. Open the UI (`http://localhost:18080/` for docker-compose).
2. You'll be redirected to `/login`.
3. Enter the email + password from the env vars.
4. You land on the Dashboard with the `Agents Online` KPI showing
   `0 / 0`.

The token is stored in React state only, **closing the tab
signs you out** by design (BRD §15).

## Rotating the admin password

There's no UI surface for this in the current slice. For now, use
`psql` directly against the api's Postgres:

```bash
# Generate a bcrypt hash for the new password
NEW_HASH=$(htpasswd -bnBC 12 "" "your-new-password" | tr -d ':\n' | sed 's/^.\$2y/$2y/')

# Update the row
docker exec -i secrets-bridge-postgres-1 \
  psql -U secrets_bridge -d secrets_bridge \
  -c "UPDATE local_users SET password_hash = decode('$(echo "$NEW_HASH" | xxd -p)', 'hex') WHERE email = 'admin@example.com';"
```

A real password-change endpoint + UI page lands as a follow-up.

## Disabling the local admin (after OIDC ships)

Once you've added a real OIDC identity with the admin role, you
can disable the local-admin row so brute-force attempts against
its bcrypt hash are pointless:

```sql
UPDATE local_users SET disabled = TRUE WHERE email = 'admin@example.com';
```

A disabled user's login attempts return the same generic
`401 invalid credentials`; the audit log records
`error_kind=user_disabled`.

## Minting your first agent

From the Dashboard:

1. **Sidebar → Agents**
2. **+ Mint agent** → drawer opens
3. Fill **Name** (e.g. `prod-eu-vault`) + **Scope cluster** (e.g.
   `prod-eu`)
4. **Mint** → the drawer swaps to the reveal-once panel
5. **Copy the agent secret immediately.** The bash snippet at the
   bottom is ready to drop into your agent container's env.
6. Click **I've copied it** → the panel closes and the secret is
   gone from React state forever.

If you lose the secret before copying it, **revoke the agent** and
mint a new one. There's no recovery path. That's the whole
point of reveal-once.

## Submitting your first read request

Once you have an agent running and `provider creds`
configured for it:

1. **Sidebar → Requests → + New request**
2. **Read** type
3. **Provider**: Vault (or AWS Secrets Manager)
4. **Provider config**: leave blank for Vault (defaults to
   `kvMount=secret`)
5. **Secret reference**: e.g. `prod/db/password`
6. **Keys**: e.g. `DB_PASSWORD` (or leave one empty row for "all
   keys in the bundle")
7. **Justification**: required, typically an incident or ticket
   number
8. **Submit** → you're navigated to the request detail page

Then either:

- Sign in as a second user (with `secret.approve` permission)
  and approve from the Requests page's Approver queue, or
- Enable `allow_self_approval` on the workflow used by the request
  and approve from the detail page's Approver actions card.

Once approved → agent claims → fetches → posts wrap → request →
`executed`. Refresh the detail page; the Wraps card now shows
`DB_PASSWORD` with the **Reveal (one-time)** button. Click it,
confirm, see the value, copy it, close.

That's the whole read flow.
