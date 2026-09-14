# AI Voice Transaction Support Agent

Phase 1 of a PBX-independent backend for a future telephone transaction-support agent. It provides synthetic customer data, short-lived OTP authentication, ownership-protected account balances and transaction lookup, audit events, and OpenAPI documentation. No real financial systems or irreversible actions are connected.

## Architecture

FastAPI routes call focused services over SQLAlchemy models. This HTTP API is the first mock transport; later conversation and Asterisk adapters can use the same service layer without changing financial or authentication rules.

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

Open `http://localhost:8000/docs` for Swagger UI. In development only, `/auth/start` logs the OTP to the server console. It is never returned by the API or stored in plaintext.

## Authentication example

1. `POST /auth/start` with `{"customer_reference":"CUS-1001"}`.
2. Read the development OTP from the API console.
3. `POST /auth/verify` with the challenge ID and OTP.
4. Send `Authorization: Bearer <session_token>` to protected endpoints.

Synthetic references run from `CUS-1001` through `CUS-1005`.

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

## Phase 1 endpoints

- `GET /health`
- `POST /auth/start`
- `POST /auth/verify`
- `GET /accounts/me`
- `GET /accounts/{account_id}/balance`
- `GET /accounts/{account_id}/transactions?limit=&start_date=&end_date=`
- `GET /transactions/{transaction_reference}`

## Security and scope

OTP and bearer token values are HMAC-SHA256 hashed at rest. Challenges expire, enforce retry limits, and are invalidated after use. Protected resources are queried with customer ownership predicates and sensitive reads generate audit events. Phase 1 uses `create_all` for development; production deployment will add migrations and managed secrets.



## Future phases

Conversation orchestration, deterministic states and intents, approved tool gateway, fraud cases, temporary restrictions, STT/TTS providers, mock audio transport, human handoff, Redis sessions, rate limiting, and the Asterisk ARI/External Media adapter remain deliberately outside Phase 1.
