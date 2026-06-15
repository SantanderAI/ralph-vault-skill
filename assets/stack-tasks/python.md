# Stack tasks — python

**Detection markers**: `pyproject.toml`, `requirements.txt`, `setup.py`, `Pipfile`. Airflow variant if `dags/` + `airflow.cfg` present (document DAGs as the API surface).

## Sections

| Section | Read from | Focus |
|---|---|---|
| `overview` | `README*`, `pyproject.toml` `[project]`, package `__init__` | Purpose, packages, entry points/CLI. |
| `architecture` | top-level packages/modules | Package layering, key call flows. |
| `domain-model` | dataclasses, pydantic models, ORM models | Entities, validation, invariants. |
| `apis` | FastAPI/Flask/Django routes, public functions, CLI | Endpoints/signatures, request/response shapes. |
| `data-model` | SQLAlchemy/Django models, Alembic migrations | Tables, relations, schema evolution. |
| `integrations` | dependency manifest, client modules, env | External services, queues, SDKs. |
| `configuration` | `settings`, `.env*`, `Dockerfile`, CI | Config surface, deployment. |
| `quality` | `tests/`, `pytest.ini`/`tox.ini`, CI | Test layout, fixtures, coverage, lint. |

## Module discovery

For packages with public API surface, add `repos/<name>/modules/<pkg>.md` (`type: module`) keeping provenance fields.
