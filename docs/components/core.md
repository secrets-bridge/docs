# Core (shared library)

Repo: [`secrets-bridge/core`](https://github.com/secrets-bridge/core)
· Stack: Go 1.24, **infra-free**

Shared types + the provider interface every other Go service
depends on. Deliberately small — adding anything Postgres-shaped or
Redis-shaped here is a CI failure on the dependent repos.

## What lives in `core`

| Package | Purpose |
|---|---|
| `providers/` | The `Provider` interface, `SecretRef` / `SecretMetadata` / `SecretValue` / `SecretVersion` / `PutOptions` / `ProviderScope`, concurrent `Registry`, plus the Vault + AWS Secrets Manager connector packages |
| `sync/` | Doc-only placeholder (the sync engine lives in the agent + worker; this package is reserved) |
| `types/` | Doc-only placeholder |

## The metadata / value split

```go
type Provider interface {
    GetMetadata(ctx, ref) (SecretMetadata, error)        // CP, discovery, controller
    ListMetadata(ctx, scope) ([]SecretMetadata, error)
    GetValue(ctx, ref) (SecretValue, error)              // agent only
    PutValue(ctx, ref, value, opts) (SecretVersion, error) // agent only
}
```

The interface is the load-bearing architectural decision in the
whole project. The CP only ever needs metadata; the agent only
ever needs values. Different processes hold different trust.

`SecretValue.String()` and `.GoString()` both return `"<redacted>"`,
verified across every default formatting verb in `core#3` — so a
casual `log.Printf("%+v", value)` can't leak.

## What `core` deliberately doesn't have

- No `database/sql` import
- No `github.com/redis/...` import
- No HTTP framework dependency
- No knowledge of workflow / RBAC / audit (those live in the api)

If you find yourself wanting to add any of these, your code
belongs in `api` or `agent` instead.
