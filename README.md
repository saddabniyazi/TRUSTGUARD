# TrustGuard AI — Day 1

Autonomous Multi-Agent Marketplace Moderation Copilot.

## What's in this drop (Day 1)

Day 1 lays the foundation everything else builds on:

- Project scaffolding (FastAPI backend, clean folder structure)
- Docker Compose: PostgreSQL + Redis
- Database schema (users, listings, reviews, policy_rules, verdicts,
  moderator_feedback, sellers) via SQLAlchemy models
- JWT authentication: register, login, refresh token, role-based
  access (`moderator`, `admin`)
- Environment variable setup (`.env.example`) — including your
  **free** Gemini API key slot, unused until Day 3+ when agents
  come online

Nothing calls an LLM yet — that starts Day 3. Today is pure
infrastructure: the part that has to be solid before any AI logic
sits on top of it.

## How to run it

1. Copy `.env.example` to `.env` and fill in the values (a random
   `SECRET_KEY`, and Postgres/Redis credentials — the defaults in
   `docker-compose.yml` work out of the box for local dev).

   ```bash
   cp backend/.env.example backend/.env
   ```

2. Start Postgres + Redis:

   ```bash
   docker compose up -d
   ```

3. Install backend dependencies and run the API:

   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```

4. Open `http://localhost:8000/docs` — you'll see the interactive
   Swagger UI with the auth endpoints ready to test:
   - `POST /api/auth/register`
   - `POST /api/auth/login`
   - `POST /api/auth/refresh`
   - `GET /api/auth/me` (requires Bearer token)

5. On first run, tables are auto-created against Postgres (see
   `app/db/session.py`). A proper Alembic migration setup will
   replace this in a later day once the schema stabilizes — noted
   as a TODO in that file so you can explain the tradeoff if asked.

## Folder structure

```
trustguard/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app entrypoint
│   │   ├── core/
│   │   │   ├── config.py      # env-driven settings
│   │   │   └── security.py    # password hashing, JWT create/verify
│   │   ├── db/
│   │   │   ├── base.py        # SQLAlchemy declarative base
│   │   │   ├── session.py     # engine, session, init_db
│   │   │   └── models.py      # all Day-1 tables
│   │   ├── schemas/
│   │   │   └── auth.py        # Pydantic request/response models
│   │   └── api/
│   │       └── auth.py        # register/login/refresh/me routes
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── docker-compose.yml
└── README.md
```

## What to actually understand before pushing this

If someone asks "why JWT + refresh token instead of just a long-lived
token", or "why did you hash passwords with bcrypt", or "why are
Postgres and Redis separate containers instead of one" — you should
be able to answer. This is the part of the project least related to
GenAI concepts and most related to "can this person build a real
backend" — interviewers probe this early precisely because it's
supposed to be the easy part.

## Next (Day 2)

Ingestion API for listings/reviews + the structured policy rule
engine + the guardrail pre-filter (prompt-injection and
text-obfuscation defense).
