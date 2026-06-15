# Stack tasks — go

**Detection markers**: `go.mod`.

## Sections

| Section | Read from | Focus |
|---|---|---|
| `overview` | `README*`, `go.mod`, `cmd/` | Purpose, binaries, entry points. |
| `architecture` | package layout, `internal/`, `pkg/` | Package boundaries, key flows. |
| `domain-model` | core structs/interfaces | Types, interfaces, invariants. |
| `apis` | HTTP/gRPC handlers, exported funcs | Endpoints/RPCs, request/response. |
| `data-model` | sql/sqlc, migrations, store packages | Schema, queries, migrations. |
| `integrations` | `go.mod` requires, client packages | External services, libs. |
| `configuration` | env, flags, `Dockerfile`, CI | Config, deployment. |
| `quality` | `*_test.go`, CI | Test strategy, coverage, observability. |
