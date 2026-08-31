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
   │     └── messages.py
   └── app/storage/           ← Persistence adapters
         └── lead_log.py
```

### Layer Responsibilities

| Layer | Files | Responsibility | Allowed Imports |
|-------|-------|---------------|-----------------|
| **Config** | `app/config.py` | Load env vars via pydantic-settings | `pydantic_settings` only |
| **Domain** | `app/domain/*.py` | Pure business logic, no side effects | stdlib only (no FastAPI, no storage) |
| **Storage** | `app/storage/*.py` | Persistence adapters (write, read, query) | `app/domain/*` (for data classes) |
| **Web** | `app/web.py` | HTTP handlers, request/response wiring | `app/config`, `app/domain/*`, `app/storage/*` |
| **Composition** | `main.py` | Wire everything together, start uvicorn | `app/config`, `app/web` |

### Dependency Rules

1. **Domain is the foundation.** `app/domain/` must never import from `app/web`, `app/storage`, or any third-party framework (FastAPI, SQLAlchemy, etc.). Domain modules use only stdlib.
2. **Storage depends on Domain.** `app/storage/` imports data classes from `app/domain/` (e.g., `Lead`). It must never import from `app/web`.
3. **Web depends on Domain + Storage.** `app/web.py` orchestrates domain logic and storage writes. It must never import from `main.py`.
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
- `storage/lead_log.py` → changes only when persistence format changes
- `web.py` → changes only when HTTP routing/wiring changes

**Known issue:** `web.py` line 27 uses `print()` instead of `logging`. This is a minor SRP smell — the handler mixes I/O logging with HTTP logic. Fix: inject a logger or use Python's `logging` module. Deferred to a future branch.

### O — Open/Closed Principle ✅

The system is open for extension, closed for modification:

- New parsers can be added to `app/domain/` without modifying existing ones.
- New storage backends can be added to `app/storage/` without changing `lead_log.py`.
- New endpoints can be added to `create_app()` without touching existing handlers.

### L — Liskov Substitution Principle ✅ (N/A)

No inheritance hierarchies exist in the current codebase. All modules use composition and plain functions. LSP does not apply.

### I — Interface Segregation Principle ✅ (Implicit)

No bloated interfaces exist. Each module exposes a minimal API:

- `Settings` → 2 fields
- `LeadLogStore` → `write()` + `path` property
- `validate_verification()` → 4 params, returns `int | dict`
- `parse_whatsapp_payload()` → 1 param, returns `list[Lead]`

### D — Dependency Inversion Principle ⚠️ VIOLATION

**The problem:** `web.py` line 6 imports `LeadLogStore` directly (concrete class), and line 11 instantiates it inside `create_app()`. This couples the web layer to a specific storage implementation.

**Why it matters:** If you want to swap `LeadLogStore` for a database store, you must modify `web.py`. The web layer should depend on an abstraction, not a concrete class.

**The fix (pending — issue #7 related work):**

1. Create a `Protocol` in `app/storage/base.py`:

```python
from typing import Protocol
from app.domain.messages import Lead

class LeadStore(Protocol):
    def write(self, lead: Lead) -> None: ...
```

2. Change `create_app()` signature to accept a store:

```python
def create_app(settings: Settings, store: LeadStore) -> FastAPI:
```

3. Wire in `main.py`:

```python
from app.storage.lead_log import LeadLogStore
store = LeadLogStore(settings.leads_log_path)
app = create_app(settings, store)
```

**Status:** This fix is documented but NOT implemented. It should be done before adding any new storage backend.

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
2. Implement the `LeadStore` Protocol (when DIP fix is applied) or match `LeadLogStore`'s interface
3. Import and wire in `main.py`
4. Do NOT modify `web.py` — pass the store via `create_app()`

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

---

## File Map

```
main.py                          → Composition root (10 lines)
app/__init__.py                  → Package marker (empty)
app/config.py                    → Settings (pydantic-settings)
app/web.py                       → FastAPI create_app + handlers
app/domain/__init__.py           → Package marker (empty)
app/domain/verification.py       → Webhook handshake validation
app/domain/messages.py           → Lead dataclass + payload parser
app/storage/__init__.py          → Package marker (empty)
app/storage/lead_log.py          → Append-only log store
tests/__init__.py                → Package marker (empty)
tests/unit/__init__.py           → Package marker (empty)
tests/unit/test_verification.py  → 6 domain tests
tests/unit/test_messages.py      → 6 parser tests
tests/integration/__init__.py    → Package marker (empty)
tests/integration/test_webhook.py → 7 HTTP handler tests
```
