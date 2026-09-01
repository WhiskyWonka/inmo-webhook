# GitFlow workflow

> Workflow and process documentation for the repository. This is agent/development
> guidance, distinct from the architecture and deployment concerns documented in
> [README.md](../README.md).

This repository follows [GitFlow](https://www.atlassian.com/git/tutorials/comparing-workflows/gitflow-workflow) as its branching model.

## Branches

| Branch | Purpose |
|--------|---------|
| `main` | Production-ready code. Only merged via release or hotfix branches. Tagged on every release (`v<version>`). |
| `develop` | Integration branch. All feature branches merge here first. |
| `feature/*` | One branch per feature or change, created from and merged back into `develop`. |
| `release/*` | Release preparation. Branched from `develop`, merged to both `main` and `develop`. |
| `hotfix/*` | Urgent fixes. Branched from `main`, merged to both `main` and `develop`. |

## Lifecycle

1. New work starts from `develop` via a `feature/<name>` branch.
2. The feature branch is merged into `develop` through a Pull Request.
3. When `develop` is ready for release, a `release/<version>` branch is created.
4. The release branch is merged into `main` through a Pull Request and tagged `v<version>`.
5. Urgent fixes branch off `main` as `hotfix/<name>` and are merged back to both `main` and `develop` via Pull Requests.

Merges to `develop` and `main` happen **through Pull Requests**, never direct pushes. `main` uses merge commits (`--no-ff`); `develop` keeps a **linear history** (squash or rebase merges) to satisfy branch protection.

## Workflow: adding a feature

```bash
git checkout develop
git pull origin develop
git checkout -b feature/your-feature

# Make changes. Run lint and tests:
ruff check .
pytest -q

# Commit with a conventional message
git add .
git commit -m "feat: add your feature description"

git push -u origin feature/your-feature
# Open a PR: feature/your-feature -> develop
```

Branch protection requires the `lint-and-test` CI check to pass before merging. You cannot push directly to `develop` or `main` -- all changes go through Pull Requests.

## Releasing

When `develop` contains all changes planned for a release:

```bash
# 1. Branch the release from develop
git checkout develop
git pull origin develop
git checkout -b release/1.0.0
git push -u origin release/1.0.0
```

Make any release-only adjustments (version bumps, changelog, README) on the `release/1.0.0` branch and commit them. Then:

```bash
# 2. Open a PR: release/1.0.0 -> main
#    Merge it. The merge commit becomes the release commit on main.
```

Tag the release against the merge commit on `main`:

```bash
git checkout main
git pull origin main
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

Sync `develop` with any release-only changes. If nothing changed on the release branch
beyond what already lived in `develop`, `develop` is already in sync and no action is
needed. If release-only commits were added, propagate them to `develop` with a separate
PR (`release/1.0.0 -> develop`), cherry-picking the release-only changes onto a feature-style
branch so `develop` keeps a linear history.

After everything is merged, delete the release branch:

```bash
git branch -d release/1.0.0      # locally
git push origin --delete release/1.0.0   # remotely
```

> Do **not** `git merge release/1.0.0` directly into `develop` and push it. `develop`
> forbids merge commits; a direct merge+push is rejected and leaves the branch violating
> its protection rules. Route every `develop` update through a PR.

## Hotfixes

For urgent fixes that must land in production immediately:

```bash
git checkout main
git pull origin main
git checkout -b hotfix/severe-issue
git push -u origin hotfix/severe-issue

# Fix, run tests
ruff check .
pytest -q

git add .
git commit -m "fix: description of the hotfix"
git push
```

Then open two Pull Requests:

1. **`hotfix/severe-issue -> main`** — release the fix to production, then tag it.
2. **`hotfix/severe-issue -> develop`** — keep the fix from being overwritten by the next release. Route this through a PR (squash into `develop`) rather than a direct merge, so `develop` stays linear.

Both `main` and `develop` must receive the fix. Do not skip the `develop` PR, or the fix will be overwritten by the next release.

## Branch protection and CI

The following rules are enforced on GitHub for both `main` and `develop`:

- **CI check required**: The `lint-and-test` job (ruff + pytest) must pass before any pull request can merge.
- **Linear history**: Required on `develop`. Every merge into `develop` is a squash/rebase, so the history stays a straight line (no merge commits).
- **No direct pushes**: All changes must go through a Pull Request. Direct pushes to `main` and `develop` are blocked.
- **No force-pushes**: Force-pushing to `main` or `develop` is prohibited. This rule is enforced durably (GitHub returns `GH006`), so history cannot be rewritten once pushed.

The CI workflow (`.github/workflows/ci.yml`) runs on every push to `main` or `develop` and on every Pull Request targeting those branches. It checks out the code, installs dependencies from `requirements-dev.txt`, runs `ruff check .`, and runs `pytest -q`.

## Commit conventions

This repository uses [Conventional Commits](https://www.conventionalcommits.org/). Prefix every commit message with one of:

| Prefix | Use case |
|--------|----------|
| `feat:` | A new feature or capability |
| `fix:` | A bug fix |
| `docs:` | Documentation changes only |
| `chore:` | Maintenance, tooling, or CI changes |
| `test:` | Adding or updating tests |
| `refactor:` | Code restructuring without changing behavior |

Examples:

```
feat: add X-Hub-Signature-256 verification to POST /webhook
fix: handle missing text field in WhatsApp payload gracefully
docs: add GitFlow workflow and branch protection documentation
chore: update CI to Python 3.11
```
