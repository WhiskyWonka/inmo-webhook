# inmo-webhook — Agent Rules

**CRITICAL:** Before making any code changes, read `docs/ARCHITECTURE.md` for the full architecture guide, layer responsibilities, and SOLID analysis.

---

## Hard Rules (never break these)

1. **Domain is pure.** `app/domain/` must never import FastAPI, storage, or any framework. Stdlib only.
2. **Dependencies flow downward.** Domain → Storage → Web → Composition. Never import upward.
3. **No business logic in `main.py`.** It is a thin composition root — wire settings + app + start uvicorn.
4. **No `importlib.reload` in tests.** Use `Settings` injection. The reload hack is removed.
5. **DIP violation is documented.** `web.py` imports `LeadLogStore` concretely. Do NOT add new concrete imports in `web.py` — fix the DIP violation first (see `docs/ARCHITECTURE.md` → DIP section).
6. **No direct pushes to `main` or `develop`.** Always PR via GitFlow.
7. **Conventional commits only.** Prefix: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`.
8. **No AI attribution in commits.** No "Co-Authored-By" lines.

## Before You Change Code

- [ ] Read `docs/ARCHITECTURE.md` if this is your first session
- [ ] Identify which layer your change touches
- [ ] Verify your imports respect the dependency rules
- [ ] Run `ruff check .` and `pytest -q` before committing
