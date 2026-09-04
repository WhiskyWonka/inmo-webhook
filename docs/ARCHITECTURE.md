# Architecture Guide

This document describes the layered architecture of the inmo-webhook project and the SOLID principles applied to it. Agents must read this before making any code changes.

---

## Layer Structure

The codebase follows a strict layered architecture. Each layer has a single responsibility and depends only on layers below it.

```
main.py (composition root)
   └── app/config.py          ← Settings (pydantic-settings)
   └── app/web.py             ← FastAPI handlers + create_app()
   └── app/domain/            ← Pure business logic (no framework imports)
   │     ├── verification.py
   │     ├── messages.py
   │     └── signature.py
    └── app/storage/           ← Persistence adapters
          ├── base.py          ← LeadStore / PropertyStore protocols (web depends on these)
          └── postgres.py      ← PostgresLeadStore / PostgresPropertyStore (SQLAlchemy)
   └── app/db/                ← Schema metadata for migrations (Alembic/SQLAlchemy Core)
         ├── base.py          ← DeclarativeBase exported for alembic env.py
         └── models/          ← ORM models (neighborhoods, properties, leads)
```

> **Note on `app/db/`:** Although `app/db/` is drawn next to the other `app/`
> modules, it is *schema infrastructure*, not a runtime layer. It exists to feed
> the migration pipeline (`migrations/env.py` reads `Base.metadata`) and is not
> part of the runtime request path. It must never be imported by `app/domain/`
> (keeping Domain pure) and it does not depend on any other application layer.
> `app/db/models/` holds the ORM models (neighborhoods, properties, leads);
> importing `app.db` registers them all with `Base.metadata` so Alembic
> `autogenerate` picks up every table automatically.

### Layer Responsibilities

| Layer | Files | Responsibility | Allowed Imports |
|-------|-------|---------------|-----------------|
| **Config** | `app/config.py` | Load env vars via pydantic-settings | `pydantic_settings` only |
| **Domain** | `app/domain/*.py` | Pure business logic, no side effects | stdlib only (no FastAPI, no storage) |
| **Storage** | `app/storage/*.py` | Persistence adapters (write, read, query) | `app/domain/*` (for data classes), `app/db/models/*` (SQLAlchemy models) |
| **DB (schema)** | `app/db/*.py`, `app/db/models/*.py` | SQLAlchemy Core metadata for Alembic migrations; NOT a runtime storage adapter | `sqlalchemy` only |
| **Web** | `app/web.py` | HTTP handlers, request/response wiring | `app/config`, `app/domain/*`, `app/storage/*` |
| **Composition** | `main.py` | Wire everything together, start uvicorn | `app/config`, `app/web` |

### Dependency Rules

1. **Domain is the foundation.** `app/domain/` must never import from `app/web`, `app/storage`, `app/db`, or any third-party framework (FastAPI, SQLAlchemy, etc.). Domain modules use only stdlib.
2. **Storage depends on Domain.** `app/storage/` imports data classes from `app/domain/` (e.g., `Lead`). It must never import from `app/web`.
3. **DB layer is isolated schema infra.** `app/db/` provides SQLAlchemy Core metadata for the migration pipeline. It must never be imported by `app/domain/` (keeping Domain pure) and it does not depend on any other application layer. At runtime, persistence still flows through the injected `LeadStore` abstraction — `app/db/` is *not* a runtime storage adapter.
4. **Web depends on Domain + Storage.** `app/web.py` orchestrates domain logic and storage writes. It must never import from `main.py`.
4. **Composition is the root.** `main.py` imports `Settings` and `create_app`, wires them, and starts uvicorn. It must never contain business logic.

### Violation Checklist

Before adding a new import, verify:

- [ ] Does the import cross a layer boundary upward? (e.g., domain importing web) → FORBIDDEN
- [ ] Does the import introduce a framework dependency into domain? → FORBIDDEN
- [ ] Does the import create a circular dependency? → FORBIDDEN

---

## SOLID Principles — Current State

### S — Single Responsibility Principle ✅

Each module has one reason to change:

- `config.py` → changes only when env vars change
- `domain/verification.py` → changes only when Meta webhook handshake spec changes
- `domain/messages.py` → changes only when Meta payload format changes
- `domain/signature.py` → changes only when Meta signature spec changes
- `storage/postgres.py` → changes only when persistence behaviour changes
- `web.py` → changes only when HTTP routing/wiring changes

**Known issue:** `web.py` line 27 uses `print()` instead of `logging`. This is a minor SRP smell — the handler mixes I/O logging with HTTP logic. Fix: inject a logger or use Python's `logging` module. Deferred to a future branch.

### O — Open/Closed Principle ✅

The system is open for extension, closed for modification:

- New parsers can be added to `app/domain/` without modifying existing ones.
- New storage backends can be added to `app/storage/` without touching `postgres.py`.
- New endpoints can be added to `create_app()` without touching existing handlers.

### L — Liskov Substitution Principle ✅ (N/A)

No inheritance hierarchies exist in the current codebase. All modules use composition and plain functions. LSP does not apply.

### I — Interface Segregation Principle ✅ (Implicit)

No bloated interfaces exist. Each module exposes a minimal API:

- `Settings` → 3 fields
- `LeadStore` (protocol) → `write(parsed: LeadWithMessages)`
- `PropertyStore` (protocol) → `create()`, `list()`, `find_by_reference_code()`
- `validate_verification()` → 4 params, returns `int | dict`
- `parse_whatsapp_payload()` → 1 param, returns `list[LeadWithMessages]`

### D — Dependency Inversion Principle ✅ RESOLVED

**Historical problem:** `web.py` originally imported `LeadLogStore` directly (concrete class) and instantiated it inside `create_app()`. This coupled the web layer to a specific storage implementation.

**Why it mattered:** Swapping `LeadLogStore` for a database store would have required modifying `web.py`. The web layer should depend on an abstraction, not a concrete class.

**The fix (implemented, issue #41):**

1. The `LeadStore` protocol lives in `app/storage/base.py` and evolves to receive the full aggregate:

```python
from typing import Protocol
from app.domain.messages import LeadWithMessages

class LeadStore(Protocol):
    def write(self, parsed: LeadWithMessages) -> None: ...
```

2. `create_app()` takes the store as an injected argument:

```python
def create_app(settings: Settings, store: LeadStore) -> FastAPI:
```

3. Wiring happens in `main.py` (the composition root), which constructs the concrete `PostgresLeadStore` from `Settings().database_url`:

```python
from app.storage.postgres import PostgresLeadStore
engine = create_engine(settings.database_url)
store = PostgresLeadStore(engine)
app = create_app(settings, store)
```

`LeadLogStore` (the file-log store) is **retired** as of #41 — leads persist to Postgres only.

**Status:** RESOLVED. `web.py` no longer imports any concrete store. Any class matching the protocol can be injected (see integration test `test_post_uses_injected_store_backend`). New storage backends must implement the `LeadStore` interface.

---

## Testing Conventions

Tests are split into two categories by what they validate:

### Unit Tests (`tests/unit/`)

- **What:** Pure domain logic — no HTTP, no file I/O, no framework.
- **How:** Direct function calls, assert on return values.
- **Example:** `test_verification.py` calls `validate_verification()` and checks `int` vs `dict`.
- **Rule:** Unit tests must never import FastAPI, httpx, or any web framework.

### Integration Tests (`tests/integration/`)

- **What:** HTTP handlers via FastAPI's `TestClient`.
- **How:** `TestClient(app)` sends real HTTP requests, asserts on status codes and response bodies.
- **Example:** `test_webhook.py` sends `GET /webhook` with query params and checks the response.
- **Rule:** Integration tests must use `Settings` injection (no `importlib.reload` hack).

### Test Commands

```bash
ruff check .                    # Lint
pytest                           # Run all tests
pytest tests/unit/               # Unit only
pytest tests/integration/        # Integration only
pytest -q                        # Quiet mode
```

---

## How to Extend

### Adding a New Storage Backend

1. Create `app/storage/new_store.py`
2. Implement the `LeadStore` interface (define `write(self, parsed: LeadWithMessages) -> None`)
3. Import and wire in `main.py` — pass the instance to `create_app(settings, store)`
4. Do NOT modify `web.py` or its imports — it depends only on the `LeadStore` abstraction

### Adding a New Domain Function

1. Create or extend a file in `app/domain/`
2. Keep it pure — no FastAPI imports, no file I/O
3. Add unit tests in `tests/unit/`

### Adding a New Endpoint

1. Add the route handler in `app/web.py` inside `create_app()`
2. Use domain functions for business logic
3. Add integration tests in `tests/integration/`

### Adding a New Config Field

1. Add the field to `Settings` in `app/config.py`
2. Set a default value
3. Document in README.md

### Adding a New Schema Model (migration)

1. Create `app/db/models/<name>.py` declaring a `Base` subclass with SQLAlchemy 2.0 style (`Mapped` / `mapped_column`).
2. Import and re-export it from `app/db/models/__init__.py` so it registers with `Base.metadata`.
3. Run `alembic revision --autogenerate -m "add <table> table"` against a reachable Postgres to generate the migration.
4. Review the generated revision: ensure CHECK constraints, FKs (`ondelete`), JSONB columns, server defaults, and indexes are present; alembic does NOT auto-generate triggers, functions, or seed data — add those by hand.
5. Add unit tests in `tests/unit/test_db_models.py` (metadata-only) and integration coverage in `tests/integration/test_schema.py`.

---

## Request Signature Verification

`POST /webhook` verifies the `X-Hub-Signature-256` header before processing
the payload, using the `app_secret` (env `APP_SECRET`).

**Critical rule:** the HMAC-SHA256 signature must be computed over the
**raw request body bytes** exactly as they arrived (`await request.body()`),
then parsed to JSON afterwards. Never re-serialize JSON (with
`json.dumps` or `await request.json()`) before verifying — JSON re-serialization
can change key order, whitespace, or unicode escaping and break the digest.
This keeps the service compatible with both the real Meta WhatsApp Cloud API
and the `whap` mock, which signs the exact bytes it transmits (escaping
non-ASCII as `\uXXXX`, matching Meta).

---

## File Map

```
main.py                          → Composition root (wires PostgresLeadStore + uvicorn)
app/__init__.py                  → Package marker (empty)
app/config.py                    → Settings (pydantic-settings)
app/web.py                       → FastAPI create_app + handlers
app/domain/__init__.py           → Package marker (empty)
app/domain/verification.py       → Webhook handshake validation
app/domain/messages.py           → Lead/Message/LeadWithMessages dataclasses + payload parser
app/domain/signature.py          → HMAC-SHA256 X-Hub-Signature-256 verification
app/storage/__init__.py          → Package marker (empty)
app/storage/base.py              → LeadStore / PropertyStore protocols (DIP)
app/storage/postgres.py          → PostgresLeadStore / PostgresPropertyStore (SQLAlchemy)
app/db/__init__.py               → Package marker (imports app.db.models to register schema)
app/db/base.py                   → DeclarativeBase (Base.metadata) consumed by alembic env.py
app/db/models/__init__.py        → Package marker; re-exports the ORM models
app/db/models/neighborhoods.py   → `neighborhoods` table (barrios seeded via migration, issue #37)
app/db/models/properties.py      → `properties` table (listings, issue #31)
app/db/models/leads.py           → `leads` table (prospects, issue #31; phone UNIQUE)
app/db/models/messages.py        → `messages` table (per-lead messages; issue #41/#33)
migrations/env.py                → Alembic env: wires target_metadata + DATABASE_URL
migrations/versions/             → Migration revision scripts (schema + v_leads_pipeline view)
alembic.ini                      → Alembic configuration
entrypoint.sh                    → Container entrypoint: alembic upgrade head + uvicorn
tests/__init__.py                → Package marker (empty)
tests/unit/__init__.py           → Package marker (empty)
tests/unit/test_verification.py  → domain handshake tests
tests/unit/test_messages.py      → parser tests
tests/unit/test_signature.py     → signature verification tests
tests/unit/test_db_models.py     → schema-model metadata tests (unit, no DB)
tests/integration/__init__.py    → Package marker (empty)
tests/integration/test_webhook.py → HTTP handler tests (GET handshake + POST signed/persisted)
tests/integration/test_schema.py → schema integration tests (DB-backed)
tests/integration/test_storage.py → Postgres store adapter tests (DB-backed)
```
