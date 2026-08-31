# inmo-webhook — Agent Rules

**CRITICAL:** Before making any code changes, read `docs/ARCHITECTURE.md` for the full architecture guide, layer responsibilities, and SOLID analysis.

---

## Hard Rules (never break these)

1. **Domain is pure.** `app/domain/` must never import FastAPI, storage, or any framework. Stdlib only.
2. **Dependencies flow downward.** Domain → Storage → Web → Composition. Never import upward.
3. **No business logic in `main.py`.** It is a thin composition root — wire settings + app + start uvicorn.
4. **No `importlib.reload` in tests.** Use `Settings` injection. The reload hack is removed.
5. **DIP is resolved & enforced.** The web layer depends on the `LeadStore` abstraction (`app/storage/base.py`), NOT concrete stores. Do NOT import `LeadLogStore` (or any concrete store) in `web.py` or add new concrete imports there.
6. **No direct pushes to `main` or `develop`.** Always PR via GitFlow.
7. **Conventional commits only.** Prefix: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`.
8. **No AI attribution in commits.** No "Co-Authored-By" lines.

## SOLID — Every New Feature (mandatory)

Every new feature, endpoint, parser, or store must comply with SOLID, as documented in `docs/ARCHITECTURE.md`. Before implementing a feature, satisfy all five:

- **S** — One reason to change per module. No multi-responsibility blobs.
- **O** — Open for extension, closed for modification. Add new behavior via new modules, not edits to working ones (unless it's a bug fix).
- **L** — No surprising substitutions if you introduce inheritance or shared interfaces.
- **I** — Depend on small, focused interfaces; never a fat service object.
- **D** — Depend on abstractions. Inject storage/backends via `create_app()`; never instantiate a concrete store inside `web.py`.

Add tests that verify the new behavior, and keep unit vs integration split as documented.

## Before You Change Code

- [ ] Read `docs/ARCHITECTURE.md` if this is your first session
- [ ] Identify which layer your change touches
- [ ] Verify your imports respect the dependency rules (especially: no concrete store imports in `web.py`)
- [ ] Confirm the feature satisfies S, O, L, I, D (see SOLID section above)
- [ ] Run `ruff check .` and `pytest -q` before committing
