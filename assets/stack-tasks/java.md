# Stack tasks — java (spring)

**Detection markers**: `pom.xml`, `build.gradle`, `build.gradle.kts`.

## Sections

| Section | Read from | Focus |
|---|---|---|
| `overview` | `README*`, `pom.xml`/`build.gradle`, main application class | Purpose, modules, run/boot. |
| `architecture` | package structure, `@Configuration` | Layering (controller/service/repo), wiring. |
| `domain-model` | `@Entity`, domain classes, value objects | Entities, aggregates, invariants. |
| `apis` | `@RestController`, `@RequestMapping`, OpenAPI | Endpoints, DTOs, status codes. |
| `data-model` | JPA entities, Flyway/Liquibase migrations | Tables, relations, schema versions. |
| `integrations` | dependencies, `@FeignClient`, messaging | External services, brokers, libs. |
| `configuration` | `application.yml/properties`, profiles, `Dockerfile`, CI | Config, profiles, deployment. |
| `quality` | `src/test`, JUnit, CI | Test layers, coverage, observability. |

## Module discovery

For multi-module builds, add `modules/<module>.md` per Maven/Gradle submodule with public API.
