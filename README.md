# AI Voice Transaction Support Agent

A PBX-independent backend for a future telephone transaction-support agent. It provides synthetic customer data, short-lived OTP authentication (with an elevated step-up level for high-risk actions), ownership-protected account balances and transaction lookup, a fraud/dispute workflow, a deterministic AI conversation orchestrator, swappable voice provider interfaces, audit events, and OpenAPI documentation. No real financial systems, real telephony, or irreversible actions are connected.

## Architecture

FastAPI routes call focused services over SQLAlchemy models. This HTTP API is the first mock transport; the conversation orchestrator (`app/ai/`) drives the same services a future Asterisk telephony adapter will eventually drive, and the TTS/STT provider interfaces (`app/voice/`) are mock-only today so a real speech provider or a custom-trained voice model can be plugged in later without touching business logic.

## Prerequisites

- Python 3.12+
- Docker and Docker Compose (optional)

## Local setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python -m scripts.seed_database
uvicorn app.main:app --reload
```

Open `http://localhost:8000/docs` for Swagger UI. In development only, `/auth/start` and `/auth/step-up/start` log the OTP to the server console. It is never returned by the API or stored in plaintext.

## Authentication example

1. `POST /auth/start` with `{"customer_reference":"CUS-1001"}`.
2. Read the development OTP from the API console.
3. `POST /auth/verify` with the challenge ID and OTP.
4. Send `Authorization: Bearer <session_token>` to protected endpoints.

Synthetic references run from `CUS-1001` through `CUS-1005`.

### Step-up (elevated) authentication example

High-risk actions such as temporarily restricting an account require a second, elevated verification on top of a standard session:

1. With a valid standard bearer token, `POST /auth/step-up/start` (no body needed).
2. Read the OTP from the console.
3. `POST /auth/step-up/verify` with the challenge ID and OTP.
4. Use the returned `session_token` (a separate, elevated token) as the bearer token for the restricted endpoint.

## Tests

```powershell
pytest -q
```

## Docker Compose

```powershell
Copy-Item .env.example .env
docker compose up --build
docker compose exec api python -m scripts.seed_database
```

PostgreSQL is used by the Compose stack. Redis is reserved for the future session abstraction and can be started with `docker compose --profile redis up`.

## Endpoints

### System
- `GET /health`

### Authentication
- `POST /auth/start`
- `POST /auth/verify`
- `POST /auth/step-up/start`
- `POST /auth/step-up/verify`

### Accounts
- `GET /accounts/me`
- `GET /accounts/{account_id}/balance`
- `POST /accounts/{account_id}/temporary-restriction` — requires elevated authentication and explicit `{"confirm": true}`
- `POST /accounts/{account_id}/lift-restriction` — requires elevated authentication and explicit `{"confirm": true}`; resolves the related support case

### Transactions
- `GET /accounts/{account_id}/transactions?limit=&start_date=&end_date=`
- `GET /transactions/{transaction_reference}`
- `POST /transactions/{transaction_reference}/report` — reports a transaction as unauthorised, requires explicit `{"confirm": true}`

### Conversation (AI orchestrator, text-only simulator)
- `POST /conversation/start`
- `POST /conversation/{call_id}/message` — drives a deterministic state machine through intent detection, authentication, confirmation, and tool execution
- `GET /conversation/{call_id}/handoff-summary` — requires an `X-Agent-Key` header matching `AGENT_API_KEY`; returns a minimized summary for a human agent

### Voice (mock providers only)
- `POST /voice/tts` — returns mock audio; no real speech synthesis is wired up yet

## Security and scope

OTP and bearer token values are HMAC-SHA256 hashed at rest. Challenges expire, enforce retry limits, and are invalidated after use. Protected resources are queried with customer ownership predicates, and sensitive reads or mutations generate audit events. High-risk actions require both elevated authentication and explicit customer confirmation, and never mutate `Customer.status` (a reported transaction or restricted account does not automatically label the customer as a fraudster). The `/conversation/{call_id}/handoff-summary` endpoint is protected only by a shared-secret header for now, since no staff/agent identity system exists yet. The current codebase uses `create_all` for schema management with no migrations; production deployment will need Alembic migrations and managed secrets.

## Future work

Real speech-to-text and text-to-speech integration (pending a decision between a hosted API and a custom-trained voice model), the Asterisk ARI/External Media telephony adapter (pending PBX access), Redis-backed session storage, rate limiting, multi-account-per-customer support in the conversation tools, and database migrations remain deliberately outside the current scope.
