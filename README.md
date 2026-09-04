# inmo-webhook

A minimal FastAPI webhook server that receives WhatsApp Cloud API messages and persists incoming leads (and their messages) to Postgres.

## Overview

This server acts as a lead-capture endpoint for WhatsApp Business messaging. It exposes a single webhook endpoint that handles both the Meta verification handshake (GET) and incoming message delivery (POST). For every incoming message from the `whatsapp_business_account` object, it extracts the sender's phone number and message text, upserts a lead (keyed by phone) into Postgres and appends the message with the lead.

The server is intentionally minimal -- a single entrypoint with no messaging queue or background workers. It is designed to be deployed behind a reverse proxy or load balancer that terminates TLS. Persistence is relational (schema managed by Alembic) via injected `PostgresLeadStore`; the web layer depends only on the `LeadStore` protocol (DIP).

## Technologies

- **Python 3.11** -- runtime
- **FastAPI** -- HTTP framework; handles routing, request parsing, and JSON serialization
- **Uvicorn** -- ASGI server; runs the FastAPI application
- **PostgreSQL** -- persistent store for leads, properties, neighborhoods, and messages
- **Alembic** -- database migration engine (schema management)
- **SQLAlchemy** -- ORM models for schema + runtime storage adapters
- **Docker** -- containerization; builds a reproducible image based on `python:3.11-slim`

## Project structure

```
inmo-webhook/
├── main.py                 # Composing: Settings → PostgresLeadStore → create_app → uvicorn
├── app/
│   ├── config.py           # Settings (pydantic-settings): verify_token, app_secret, database_url
│   ├── domain/
│   │   ├── messages.py     # Lead/Message/LeadWithMessages models + WhatsApp payload parser
│   │   └── verification.py # Handshake validation logic (token + challenge)
│   ├── storage/
│   │   ├── base.py         # LeadStore / PropertyStore protocols (DIP — web depends on these)
│   │   └── postgres.py     # PostgresLeadStore / PostgresPropertyStore (SQLAlchemy 2.0)
│   ├── db/
│   │   ├── base.py         # DeclarativeBase (Base.metadata) for Alembic migrations
│   │   └── models/         # ORM models: neighborhoods.py, properties.py, leads.py, messages.py
│   └── web.py              # FastAPI handlers (GET/POST /webhook) — thin, delegates to domain/storage
├── migrations/
│   ├── env.py              # Alembic env: target_metadata + DATABASE_URL wiring
│   └── versions/           # Migration revision scripts (schema + v_leads_pipeline view)
├── alembic.ini             # Alembic configuration
├── entrypoint.sh           # Container entrypoint: alembic upgrade head + uvicorn
├── tests/
│   ├── unit/
│   │   ├── test_verification.py   # Pure validation tests — no FastAPI, no DB
│   │   ├── test_messages.py       # Pure parser tests — no FastAPI, no DB
│   │   └── test_db_models.py      # Schema-model metadata tests — no DB
│   └── integration/
│       ├── test_webhook.py        # TestClient against the real app (handshake/signature + persist)
│       ├── test_schema.py         # Schema integration tests (DB-backed)
│       └── test_storage.py        # Postgres store adapter tests (DB-backed)
├── Dockerfile              # Container build; runs alembic upgrade head + uvicorn via entrypoint
├── requirements.txt        # Runtime dependencies (fastapi, uvicorn, pydantic-settings, sqlalchemy, alembic, psycopg)
├── requirements-dev.txt    # Dev/test dependencies (pytest, httpx, ruff)
├── pyproject.toml          # Ruff config + pytest pythonpath
└── .gitignore              # Ignore /data/ logs, __pycache__, pytest/ruff caches
```

## Architecture

The app follows a layered structure with clear responsibility boundaries:

- **`app/config.py`** — settings via `pydantic-settings`. Reads `VERIFY_TOKEN`, `APP_SECRET`, and `DATABASE_URL` from env vars at instantiation time (not import time), eliminating the `importlib.reload` hack in tests.
- **`app/domain/`** — pure logic, no framework dependency. `verification.py` handles the Meta handshake validation. `messages.py` parses the nested WhatsApp payload into `LeadWithMessages` aggregates (`Lead` keyed by phone + its `Message` list).
- **`app/storage/`** — persistence adapters. `base.py` defines the `LeadStore` / `PropertyStore` protocols; `postgres.py` implements them on top of SQLAlchemy (`PostgresLeadStore`, `PostgresPropertyStore`). `PostgresLeadStore.write` upserts the lead by phone and appends its messages in one transaction.
- **`app/db/`** — schema metadata for migrations. `base.py` defines the SQLAlchemy `DeclarativeBase` consumed by `migrations/env.py`; `models/` defines the `neighborhoods`, `properties`, `leads`, and `messages` ORM tables. This is schema infrastructure; runtime persistence flows through the injected store.
- **`app/web.py`** — thin FastAPI layer. Delegates to domain/storage. The `create_app(settings, store)` factory takes an injected store (DIP).
- **`main.py`** — composition root: instantiates `Settings()`, builds `PostgresLeadStore` from `database_url`, calls `create_app(settings, store)`, exposes `app` for uvicorn.

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

# Point at a Postgres database (required — the log-file store is retired)
export DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/inmobot"

# Apply the schema
alembic upgrade head

# Start the server
uvicorn main:app --host 0.0.0.0 --port 8000
```

The webhook endpoint will be available at `http://localhost:8000/webhook`.

If `VERIFY_TOKEN` is not set, it defaults to an empty string. The Meta handshake will fail because the empty token will not match what you configure in the Meta dashboard.

`DATABASE_URL` is **required** at startup: since `LeadLogStore` was retired (issue #41), `main.py` raises a clear error if `DATABASE_URL` is empty instead of starting without persistence.

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
  -e DATABASE_URL="postgresql+psycopg://user:pass@db:5432/inmobot" \
  --name inmo-webhook \
  inmo-webhook
```

Data is persisted in Postgres (via `DATABASE_URL`); no volume mount for local files is needed.

## Migrations

Database schema is managed with **Alembic** on top of **SQLAlchemy** models
(`app/db/models/`: neighborhoods, properties, leads, messages) registered with
`Base.metadata` when `app.db` is imported. The migrations:

- `0184e017b2a8` — creates `neighborhoods`, `properties`, `leads`; the
  `update_updated_at_column()` function and its two triggers; seeds the 19
  barrios (issue #31/#37).
- `e4b438d3a245` — creates the `messages` table, makes `leads.phone` UNIQUE
  (backing the phone-keyed upsert), and adds the `v_leads_pipeline` view
  (issue #41, with the `messages` table overlapping issue #33).

### Applying migrations

```bash
# The URL comes from the DATABASE_URL environment variable
export DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/inmobot"
alembic upgrade head
```

`alembic upgrade head` runs automatically on container startup via
`entrypoint.sh` before uvicorn starts. If `DATABASE_URL` is not set, the
entrypoint skips migrations and the app fails fast because `main.py` requires
a database.

### Generating a new migration

After adding or changing a model in `app/db/`, auto-generate a revision from the
current schema:

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

Reviews the generated `migrations/versions/` file before applying it.

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

## Payload and persistence

### How leads and messages are stored

Every incoming message from a distinct sender phone upserts a `leads` row
(keyed by `phone`) and appends a `messages` row referencing that lead. The
storage adapter (`PostgresLeadStore.write(parsed: LeadWithMessages)`) does the
upsert + message append atomically in a single transaction. Message inserts are
idempotent via the unique `external_id`: a re-delivered message with an
already-stored external id is skipped rather than duplicated.

A `v_leads_pipeline` SQL view exposes each lead's pipeline stage (`status`,
`qualification_score`) plus a `message_count` for reporting.

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

The server checks that the top-level `object` is `whatsapp_business_account`, then iterates `entry[].changes[].value.messages[]` to extract each message's `from` (phone number) and `text.body` (message text). It groups messages by sender phone into `LeadWithMessages` aggregates and persists each one. Messages without a `text` field (e.g., image or audio messages) have an empty content body.

The POST handler returns `{"status": "ok"}` for all requests, including payloads that do not match the expected structure. Non-matching payloads are silently ignored (no lead is written, no error).

## Security considerations and known gaps

### Credentials involved

| Credential      | Purpose                                          | Where used                                    |
|-----------------|--------------------------------------------------|-----------------------------------------------|
| Verify Token    | Proves ownership during the webhook handshake    | `GET /webhook` query param, compared against `VERIFY_TOKEN` env var |
| App Secret      | Signs webhook payloads (HMAC-SHA256)             | Should be validated on incoming `POST /webhook` -- **currently not implemented** |

### Payload signature validation

The `POST /webhook` handler **verifies** the `X-Hub-Signature-256` header that Meta includes on every webhook delivery. This header contains an HMAC-SHA256 signature computed using the App Secret and the raw request body. The HMAC is computed over the exact raw request bytes (`await request.body()`) before JSON parsing, and compared with `hmac.compare_digest` (constant-time) to prevent timing attacks. Requests whose signature does not match, or which omit the header, are rejected with HTTP 403.

### Sensitive data

The database stores real phone numbers and message content, which constitute personal data under most privacy regulations. The rows are:

- Stored in Postgres (via `DATABASE_URL`), never in version-controlled files
- Not baked into the container image

Apply appropriate access controls (DB credentials, network isolation) and retention policies as required by your jurisdiction.

### Other gaps

- **No HTTPS**: The server itself does not terminate TLS. Deploy behind a reverse proxy (nginx, Caddy, cloud load balancer) that handles TLS termination.
- **No rate limiting**: The endpoint accepts unlimited requests. Consider rate limiting at the reverse proxy level.
- **No structured error handling**: If the database is unreachable, `store.write` raises and the handler returns a 500 error to Meta. Consider a bounded retry or a queue if durability is critical.

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

The test suite is split into **unit** suites (pure domain, schema metadata — no DB
needed) and **integration** suites (HTTP handlers via `TestClient`, plus
DB-backed store/schema tests). The handshake, signature, and request-shaping
tests use an in-memory store and run anywhere. The Postgres-backed persistence
tests (in `tests/integration/test_storage.py`, `tests/integration/test_schema.py`,
and part of `tests/integration/test_webhook.py`) run only when `DATABASE_URL` is
set; locally they are skipped:

```bash
# Local, no DB: unit + handshake/signature tests only
pytest -q

# Full suite against a real Postgres (as CI runs it)
export DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/inmobot"
alembic upgrade head
pytest -q
```

For the repository workflow (GitFlow branching, branch protection, and commit conventions), see [docs/GITFLOW.md](docs/GITFLOW.md).
