# GitHub Issues — Conventions

This project uses GitHub Issues as the single source of truth for all tracked
work: features, improvements, refactors, bugs, and infrastructure requests.

Every unit of work starts as an issue. No branch, PR, or change should exist
without a corresponding issue backing it.

---

## Issue Types

An issue must carry **at least one type label**, chosen from:

| Label | Meaning | Example |
|-------|---------|---------|
| `bug` | Something is not working as expected | GET /webhook crashes on missing challenge |
| `feature` | New functionality | Add an endpoint to query stored leads |
| `improvement` | Make existing behavior better (UX, perf, clarity) | Faster log read, clearer response body |
| `refactor` | Restructure code without changing behavior | Inject LeadStore abstraction (DIP) |
| `docs` | Documentation changes | ARCHITECTURE.md, README, this file |
| `infra` | Infrastructure request (CI, Docker, deploy, deps, secrets) | Pin GitHub Actions to SHAs |
| `tech-debt` | Technical debt to revisit | Hoist dir-creation out of per-message loop |

### Priority

Every issue should also carry one `priority:*` label:

| Label | Meaning |
|-------|---------|
| `priority:high` | Blocks work or is an immediate risk |
| `priority:medium` | Important but not urgent |
| `priority:low` | Nice to have |

### Context (optional but encouraged)

Add context labels when they apply:

| Label | Meaning |
|-------|---------|
| `security` | The work has security implications |
| `good first issue` | Good entry point for newcomers |

> Type labels map 1:1 to conventional commit prefixes (`bug` → `fix:`,
> `feature` → `feat:`, `refactor` → `refactor:`, `docs` → `docs:`). Use the
> matching prefix in the commit that closes the issue.

---

## Workflow

1. **Open an issue** with a type label (+ priority and context as applicable)
   before starting any work.
2. **Follow GitFlow.** Create a branch named after the issue:
   - `feature/<issue>/<slug>` — feature work
   - `fix/<issue>/<slug>` — bug fixes
   - `refactor/<issue>/<slug>` — refactors
   - `docs/<issue>/<slug>` — documentation
3. **Reference the issue in the PR.** Use `Fixes #N` or `Closes #N` in the PR
   description so merging auto-closes the issue.
4. **Keep one issue = one atomic unit of work.** An issue should be small
   enough to review and merge independently.

---

## Checklist Before You Change Code

- [ ] Is there an issue backing this work?
- [ ] Does the issue carry the correct type label (and priority/context if applicable)?
- [ ] Is the branch named after the issue?
- [ ] Will the PR reference the issue (`Fixes #N` / `Closes #N`)?
