# Stack tasks — frontend (SPA)

**Detection markers**: `angular.json`, or `package.json` with `react`, `vue`, `@angular/*`, or `svelte`.

## Sections

| Section | Read from | Focus |
|---|---|---|
| `overview` | `README*`, `package.json`, app entry | Purpose, run/build, routing entry. |
| `architecture` | `src/` layout, routing, state mgmt | Component tree, state, data flow. |
| `domain-model` | TS types/interfaces, view models | Client domain types. |
| `apis` | API client layer, hooks/services | Backend endpoints consumed, contracts. |
| `data-model` | local/store state, caching | Client-side state shape (if notable). |
| `integrations` | `dependencies`, SDKs, auth libs | Third-party UI/services, analytics. |
| `configuration` | env, build config, `Dockerfile`, CI | Build/deploy, feature flags. |
| `quality` | test setup, e2e, CI | Unit/e2e strategy, lint, a11y. |

## Note

`02`/`04` may be thin for stateless UIs — note that rather than padding.
