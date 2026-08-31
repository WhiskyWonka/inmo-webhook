# inmo-webhook

A minimal FastAPI webhook server that receives WhatsApp Cloud API messages and logs each incoming lead to a local file.

## Overview

This server acts as a lead-capture endpoint for WhatsApp Business messaging. It exposes a single webhook endpoint that handles both the Meta verification handshake (GET) and incoming message delivery (POST). For every incoming message from the `whatsapp_business_account` object, it extracts the sender's phone number and message text, then appends a timestamped line to `/app/data/leads.log`.

The server is intentionally minimal -- a single Python file with no database, no authentication layer beyond webhook verification, and no message queue. It is designed to be deployed behind a reverse proxy or load balancer that terminates TLS.

## Technologies

- **Python 3.11** -- runtime
- **FastAPI** -- HTTP framework; handles routing, request parsing, and JSON serialization
- **Uvicorn** -- ASGI server; runs the FastAPI application
- **Docker** -- containerization; builds a reproducible image based on `python:3.11-slim`

## Project structure

```
inmo-webhook/
├── main.py                 # Composing: Settings → create_app → uvicorn entrypoint
├── app/
│   ├── config.py           # Settings (pydantic-settings): verify_token, leads_log_path
│   ├── domain/
│   │   ├── messages.py     # Lead model + WhatsApp payload parser
│   │   └── verification.py # Handshake validation logic (token + challenge)
│   ├── storage/
│   │   └── lead_log.py     # LeadLogStore: injected path, ensures dir, writes formatted line
│   └── web.py              # FastAPI handlers (GET/POST /webhook) — thin, delegates to domain/storage
├── tests/
│   ├── unit/
│   │   ├── test_verification.py   # Pure validation tests — no FastAPI, no filesystem
│   │   └── test_messages.py       # Pure parser tests — no FastAPI, no filesystem
│   └── integration/
│       └── test_webhook.py        # TestClient against the real app (Settings injected)
├── Dockerfile              # Container build; runs uvicorn
├── requirements.txt        # Runtime dependencies (fastapi, uvicorn, pydantic-settings)
├── requirements-dev.txt    # Dev/test dependencies (pytest, httpx, ruff)
├── pyproject.toml          # Ruff config + pytest pythonpath
├── .gitignore              # Ignores /data/ logs, __pycache__, pytest/ruff caches
└── data/
    └── leads.log           # Runtime output: timestamp | phone | message (NOT committed)
```

## Architecture

The app follows a layered structure with clear responsibility boundaries:

- **`app/config.py`** — settings via `pydantic-settings`. Reads `VERIFY_TOKEN` and `LEADS_LOG_PATH` from env vars at instantiation time (not import time), eliminating the `importlib.reload` hack in tests.
- **`app/domain/`** — pure logic, no framework dependency. `verification.py` handles the Meta handshake validation. `messages.py` parses the nested WhatsApp payload into `Lead` dataclasses.
- **`app/storage/`** — persistence. `LeadLogStore` takes an injected path, ensures the directory once at construction, and writes formatted log lines.
- **`app/web.py`** — thin FastAPI layer. Delegates to domain/storage. The `create_app(settings)` factory wires everything together.
- **`main.py`** — minimal composition: instantiates `Settings()`, calls `create_app(settings)`, exposes `app` for uvicorn.

This separation means domain logic and parser can be tested in isolation (no FastAPI, no `importlib.reload`), and persistence can be swapped out without touching HTTP handlers.

## Setup / Running locally

### Prerequisites

- Python 3.11+
- A virtual environment (recommended)

### Steps

```bash
# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set the verification token (used for the Meta webhook handshake)
export VERIFY_TOKEN="your_secret_token_here"

# Ensure the data directory exists
mkdir -p data

# Start the server
uvicorn main:app --host 0.0.0.0 --port 8000
```

The webhook endpoint will be available at `http://localhost:8000/webhook`.

If `VERIFY_TOKEN` is not set, it defaults to an empty string. The Meta handshake will fail because the empty token will not match what you configure in the Meta dashboard.

## Running with Docker

### Build the image

```bash
docker build -t inmo-webhook .
```

### Run the container

```bash
docker run -d \
  -p 8000:8000 \
  -e VERIFY_TOKEN="your_secret_token_here" \
  -v $(pwd)/data:/app/data \
  --name inmo-webhook \
  inmo-webhook
```

The `-v $(pwd)/data:/app/data` volume mount maps your local `data/` directory into the container so that `leads.log` persists across container restarts. Without this mount, log data is lost when the container is removed.

## Configuring the Meta / WhatsApp webhook

### Prerequisites

- Your Meta app must have the `whatsapp_business_messaging` permission.
- Meta requires a **publicly accessible HTTPS URL**. Localhost will not work for production webhooks.
- The app must be in **Live mode** (not Development) to receive webhooks for production phone numbers.

### Step 1: Set the callback URL and verify token

In the Meta App Dashboard, go to **WhatsApp > Configuration > Webhook**:

- **Callback URL**: `https://<your-public-domain>/webhook`
- **Verify token**: any string you choose. This **must** match the `VERIFY_TOKEN` environment variable on your server.

When you click **Save**, Meta sends a verification request to your server:

```
GET /webhook?hub.mode=subscribe&hub.challenge=<CHALLENGE>&hub.verify_token=<VERIFY_TOKEN>
```

Your server validates that `hub.mode` is `subscribe` and that `hub.verify_token` matches the configured token. If both conditions pass, it responds with the raw integer challenge value. A common mistake is wrapping the challenge in a JSON object -- this server avoids that by returning `int(challenge)` directly.

If the token does not match or the server is unreachable, Meta will report a verification failure and you will not receive any webhooks.

### Step 2: Subscribe to the `messages` field

After verification succeeds, you must subscribe to webhook events. Go to **Manage** in the webhook configuration and subscribe to:

- **messages** (required -- without this, no incoming messages are delivered)
- Optionally: `message_status`, `message_template_status_update`

Without subscribing to the `messages` field, your server will never receive POST requests even though the handshake succeeded.

### Note on the verify token

The verify token is only used during the ownership handshake. It is not the same as the App Secret, which is used to sign webhook payloads (see Security considerations below).

## Payload and log format

### Log line format

Each line in `data/leads.log` follows this format:

```
2026-08-26T18:44:14.980000 | 16315551181 | this is a text message
```

| Field         | Description                              |
|---------------|------------------------------------------|
| timestamp     | ISO 8601 timestamp of when the message was processed (`datetime.now().isoformat()`) |
| phone number  | Sender's phone number (from `msg["from"]`) |
| message body  | Text content of the message (from `msg["text"]["body"]`) |

### Webhook payload structure

Meta sends a JSON payload to `POST /webhook` with this nested structure. The server traverses it as follows:

```json
{
  "object": "whatsapp_business_account",
  "entry": [
    {
      "changes": [
        {
          "value": {
            "messages": [
              {
                "from": "16315551181",
                "text": {
                  "body": "this is a text message"
                }
              }
            ]
          }
        }
      ]
    }
  ]
}
```

The server checks that the top-level `object` is `whatsapp_business_account`, then iterates `entry[].changes[].value.messages[]` to extract each message's `from` (phone number) and `text.body` (message text). Messages without a `text` field (e.g., image or audio messages) will have an empty body in the log.

The POST handler returns `{"status": "ok"}` for all requests, including payloads that do not match the expected structure. Non-matching payloads are silently ignored (no log entry, no error).

## Security considerations and known gaps

### Credentials involved

| Credential      | Purpose                                          | Where used                                    |
|-----------------|--------------------------------------------------|-----------------------------------------------|
| Verify Token    | Proves ownership during the webhook handshake    | `GET /webhook` query param, compared against `VERIFY_TOKEN` env var |
| App Secret      | Signs webhook payloads (HMAC-SHA256)             | Should be validated on incoming `POST /webhook` -- **currently not implemented** |

### Known gap: no payload signature validation

The `POST /webhook` handler does **not** verify the `X-Hub-Signature-256` header that Meta includes on every webhook delivery. This header contains an HMAC-SHA256 signature computed using the App Secret and the raw request body. Without validating this signature, any party that can reach your endpoint can forge a POST request with arbitrary data and create fake lead entries.

**This is the most significant security gap in the current implementation.** To fix it:

1. Store the App Secret in an environment variable (e.g., `APP_SECRET`).
2. Compute the HMAC-SHA256 of the raw request body using that secret.
3. Compare it to the `X-Hub-Signature-256` header using a constant-time comparison (e.g., `hmac.compare_digest` in Python) to prevent timing attacks.
4. Reject requests where the signature does not match.

A constant-time comparison is critical -- a standard `==` comparison leaks information about the correct signature through response timing.

### Sensitive data

`data/leads.log` contains real phone numbers and message content, which constitute personal data under most privacy regulations. The file is:

- Excluded from version control via `.gitignore` (`/data/` directory)
- Persisted via Docker volume mount, not baked into the container image

Do not commit this file to any repository. Do not expose it through a web server or file share. Apply appropriate access controls and retention policies as required by your jurisdiction.

### Other gaps

- **No HTTPS**: The server itself does not terminate TLS. Deploy behind a reverse proxy (nginx, Caddy, cloud load balancer) that handles TLS termination.
- **No rate limiting**: The endpoint accepts unlimited requests. Consider rate limiting at the reverse proxy level.
- **No persistence beyond the log file**: Messages are written to a flat file. For any production use case beyond simple lead capture, a database or message queue is recommended.
- **No structured error handling**: If `leads.log` is not writable (e.g., the `/app/data` directory does not exist and no volume is mounted), the server will raise an unhandled exception and return a 500 error to Meta. The log line also assumes `msg["from"]` always exists, which will raise a `KeyError` on malformed payloads.

## Local development

Before opening a pull request, run lint and tests locally to catch issues early.

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

`requirements-dev.txt` includes both runtime dependencies (fastapi, uvicorn, pydantic-settings) and development tools (pytest, httpx, ruff).

### Lint

```bash
ruff check .
```

Ruff is configured in `pyproject.toml` with `line-length = 100` and checks for pycodestyle (`E`) and pyflakes (`F`) violations.

### Tests

```bash
pytest -q
```

The test suite in `tests/test_webhook.py` covers four scenarios: the Meta verification handshake (valid and invalid token), a valid WhatsApp payload writing a correctly-formatted log line, and an unrelated payload being silently ignored.

The log path defaults to `/app/data/leads.log`. To avoid writing to that path during local development or testing, set the `LEADS_LOG_PATH` environment variable:

```bash
export LEADS_LOG_PATH=./leads.log
```

Note that tests already override this via `monkeypatch.setenv` and `tmp_path`, so each test writes to an isolated temporary file. You only need to set the variable if you are running the server locally outside the test suite.

## GitFlow workflow

This repository follows [GitFlow](https://www.atlassian.com/git/tutorials/comparing-workflows/gitflow-workflow) as its branching model.

### Branches

| Branch | Purpose |
|--------|---------|
| `main` | Production-ready code. Only merged via release or hotfix branches. Tagged on every release (`v<version>`). |
| `develop` | Integration branch. All feature branches merge here first. |
| `feature/*` | One branch per feature or change, created from and merged back into `develop`. |
| `release/*` | Release preparation. Branched from `develop`, merged to both `main` and `develop`. |
| `hotfix/*` | Urgent fixes. Branched from `main`, merged to both `main` and `develop`. |

### Lifecycle

1. New work starts from `develop` via a `feature/<name>` branch.
2. The feature branch is merged back into `develop` through a Pull Request.
3. When `develop` is ready for release, a `release/<version>` branch is created.
4. The release branch is merged into `main` with `--no-ff` and tagged `v<version>`.
5. The release branch is also merged back into `develop` to keep it in sync.
6. Urgent fixes branch off `main` as `hotfix/<name>`, then merge back to both `main` and `develop`.

All merges use `--no-ff` (non-fast-forward) with structured commit messages to preserve a clear history of when work was integrated.

### Workflow: adding a feature

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

### Releasing

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

### Hotfixes

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
