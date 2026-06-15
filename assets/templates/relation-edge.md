---
type: relation
load_tier: 2
schema_version: 1
from: "[[repos/{FROM}/README|{FROM}]]"
to: "[[repos/{TO}/README|{TO}]]"
relation_type: {KIND}
tags: [relation, {KIND}]
---

# {FROM} → {KIND} → {TO}

> One typed edge of the system graph. File path: `relations/{KIND}/{FROM}_{KIND}_{TO}.md`.

## Type

{What kind of dependency this is — e.g. synchronous gRPC call, REST call, Kafka topic consumption, shared database, code/library dependency, shared secret, observability instrumentation.}

## Detail

| Touchpoint | Mechanism | Configuration |
|---|---|---|
| {endpoint / topic / table / package} | {client / consumer / import} | {env / config source} |

## Direction & contract

- **Caller / producer**: [[repos/{FROM}/README|{FROM}]].
- **Callee / consumer**: [[repos/{TO}/README|{TO}]].
- **Contract**: {proto/openapi/schema/package name + version, or TBD}.

## Evidence

- `{FROM}/path/to/source`
- `{TO}/path/to/source`
