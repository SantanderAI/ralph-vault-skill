# Stack tasks — scala (sbt)

**Detection markers**: `build.sbt`, `*.sbt`, `project/build.properties`, `.scalafmt.conf`.

## Sections

| Section | Read from | Focus |
|---|---|---|
| `overview` | `README*`, `build.sbt`, main object/app | Purpose, modules, run. |
| `architecture` | source layout, sbt subprojects | Layering, key flows, effects model. |
| `domain-model` | case classes, ADTs, type classes | Domain types, invariants. |
| `apis` | http4s/Play/Akka routes, public traits | Endpoints, request/response. |
| `data-model` | Doobie/Slick, migrations | Schema, queries, migrations. |
| `integrations` | `libraryDependencies`, clients | External services, libs, streaming. |
| `configuration` | `application.conf`, env, `Dockerfile`, CI | Config, deployment. |
| `quality` | `src/test`, ScalaTest/MUnit, CI | Test strategy, coverage. |

## Module discovery

For multi-project sbt builds, add `modules/<subproject>.md` per subproject with public API.
