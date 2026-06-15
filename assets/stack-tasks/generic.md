# Stack tasks — generic (fallback)

Use when no specific stack template fits, or `stack: generic`.

## Sections to generate (in `repos/<name>/`)

| Section | Read from source | Focus |
|---|---|---|
| `overview` | README, top-level docs, entry points | Purpose, responsibilities, how to run. |
| `architecture` | directory layout, main modules | Components, layering, key flows. |
| `domain-model` | core types/structs/classes | Entities, relationships, invariants. |
| `apis` | public interfaces, CLI, handlers | Surface others depend on. |
| `data-model` | storage, schemas, files | Persistence shape, if any. |
| `integrations` | dependency manifests, clients | External systems, libraries. |
| `configuration` | config files, env, CI, containers | How it is configured + deployed. |
| `quality` | tests, CI workflows | Test strategy, coverage signals, observability. |

Omit a section that genuinely does not apply (note why in `overview`).

## Cross-repo signals (feed the graph tiers)

While reading the source for the sections above, record candidates for the graph tiers — do **not** write those tiers here, just leave the evidence in `integrations` / `configuration` so the dedicated prompts can pick them up:

| Signal in source | Feeds | Look for |
|---|---|---|
| gRPC stubs / clients to another repo | `relations/grpc` | `*_pb2_grpc`, proto imports, channel targets. |
| HTTP/REST clients to another repo | `relations/http` | base URLs, OpenAPI clients, service hostnames. |
| Topic produce/consume | `relations/kafka` | broker config, topic names, consumer groups. |
| Shared DB/schema access | `relations/db` | connection strings, shared schema/table names. |
| Dependency on a shared lib/artifact | `relations/code` + `components/` | manifest entries pointing at another repo's package. |
| Shared secret/credential | `relations/secret` | secret refs, vault paths consumed by ≥ 2 repos. |
| Infra it runs on (broker, cache, db, ingress, idp) | `infrastructure/` | deploy manifests, charts, managed-service config. |
| External SDK/provider/API | `technologies/` | third-party SDK imports, provider API keys. |

## Always finish with

- `repos/<name>/README.md` — section index.
- `agent-context/repo-cards/<name>.md` — tier-1 card (≤ ~1000 tokens).
