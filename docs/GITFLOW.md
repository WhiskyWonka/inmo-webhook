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
2. The feature branch is merged back into `develop` through a Pull Request.
3. When `develop` is ready for release, a `release/<version>` branch is created.
4. The release branch is merged into `main` with `--no-ff` and tagged `v<version>`.
5. The release branch is also merged back into `develop` to keep it in sync.
6. Urgent fixes branch off `main` as `hotfix/<name>`, then merge back to both `main` and `develop`.

All merges use `--no-ff` (non-fast-forward) with structured commit messages to preserve a clear history of when work was integrated.

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
git checkout -b release/1.0.0 develop

# Final checks, version bumps, changelog updates
ruff check .
pytest -q

git add .
git commit -m "chore: prepare release 1.0.0"

git checkout main
git merge --no-ff release/1.0.0 -m "release: 1.0.0"
git tag v1.0.0
git push origin main --tags

git checkout develop
git merge --no-ff release/1.0.0 -m "merge: 1.0.0 back into develop"
git push origin develop
```

After merging, delete the release branch:

```bash
git branch -d release/1.0.0
```

## Hotfixes

For urgent fixes that must land in production immediately:

```bash
git checkout -b hotfix/severe-issue main

# Fix, run tests
ruff check .
pytest -q

git add .
git commit -m "fix: description of the hotfix"
git push -u origin hotfix/severe-issue

# Open a PR to main, get it reviewed and merged
# Then merge the fix back into develop
git checkout develop
git merge --no-ff hotfix/severe-issue -m "merge: hotfix/severe-issue into develop"
git push origin develop
```

Both `main` and `develop` must receive the fix. Do not skip the develop merge, or the fix will be overwritten by the next release.

## Branch protection and CI

The following rules are enforced on GitHub for both `main` and `develop`:

- **CI check required**: The `lint-and-test` job (ruff + pytest) must pass before any pull request can merge.
- **Linear history**: Required. Force-pushes are blocked, so feature branches are typically rebased onto `develop` before merging to keep history clean.
- **No direct pushes**: All changes must go through a Pull Request. Direct pushes to `main` and `develop` are blocked.
- **No force-pushes**: Force-pushing to `main` or `develop` is prohibited.
- **Owner override**: Repository owners can bypass these rules in emergencies (`enforce_admins` is off).

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
