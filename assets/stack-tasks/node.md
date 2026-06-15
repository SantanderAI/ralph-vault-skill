# Stack tasks — node (typescript/javascript backend)

**Detection markers**: `package.json` with `@nestjs/*`, `express`, `fastify`, or `koa`.

## Sections

| Section | Read from | Focus |
|---|---|---|
| `overview` | `README*`, `package.json` scripts/main | Purpose, entry points, run scripts. |
| `architecture` | `src/` layout, module system | Layering, DI/modules, key flows. |
| `domain-model` | entities, DTOs, zod/class-validator schemas | Domain types, validation. |
| `apis` | route/controller files, OpenAPI | Endpoints, payloads, middleware. |
| `data-model` | Prisma/TypeORM/Mongoose, migrations | Schema, relations, migrations. |
| `integrations` | `dependencies`, client wrappers, env | External services, SDKs, queues. |
| `configuration` | `.env*`, config modules, `Dockerfile`, CI | Config surface, deployment. |
| `quality` | `test/`/`__tests__`, jest/vitest config, CI | Test strategy, coverage, lint. |

## Module discovery

For monorepos/workspaces, add `modules/<package>.md` per published package.
