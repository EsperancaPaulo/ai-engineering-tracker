# AI Engineering Tracker

FastAPI + PostgreSQL, with Argon2id password hashing and expiring JWT authentication. The browser interface opens at `/`; API status is at `/api`, with `/health` and `/docs` also available.

## Setup

From the project directory:

```sh
cd backend
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

Keep your existing `backend/.env` and `DATABASE_URL`. For a fresh installation only, copy `.env.example` to `.env` and replace its placeholders. Generate a private signing secret locally:

```sh
python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Add it to `backend/.env` as `JWT_SECRET_KEY=...`. Never share or commit this file. `ACCESS_TOKEN_EXPIRE_MINUTES=30` is optional (range 1–60). Missing, short, or placeholder signing secrets prevent startup. Environment variables override the local `.env`.

For a fresh database, create it in PostgreSQL and initialize the existing tables after configuring `.env`:

```sh
createdb ai_engineering_tracker
python -c 'from database import Base, engine; import models; Base.metadata.create_all(bind=engine)'
```

Skip this initialization when using an existing database. Start from `backend`:

```sh
uvicorn main:app --reload
```

## Try authentication

Open http://127.0.0.1:8000/docs.

1. Call **POST /auth/register** with JSON containing `name`, `email`, and `password`. Passwords must contain 15–128 characters. Names are trimmed, emails validated and lowercased, and extra fields rejected. New users always get the `developer` role. Duplicate emails return 409.
2. Click **Authorize** and enter your email in **username**, plus your password. **POST /auth/login** accepts form data (`username`, `password`) and returns a bearer token, valid for 30 minutes by default.
3. Call **GET /me** to see your public profile. Other clients send `Authorization: Bearer <access_token>`. Missing, invalid, or expired tokens return 401.

Only password hashes are stored. Responses exclude passwords/hashes, and validation errors omit submitted values. JWTs contain user IDs, timestamps, and issuer claims. Verification requires the expected signing algorithm, issuer, and expiration. Invalid login credentials return the same generic message for unknown users and incorrect passwords. Deleted users cannot use existing tokens.

## Tests and dependencies

From `backend`:

```sh
python -m pytest -q
python -m pip check
```

Tests use fresh in-memory SQLite databases and a temporary signing secret, never the PostgreSQL database. They check registration, actual Argon2 hashing, login, validation, duplicate emails, safe responses, protected routes, deleted users, and invalid/expired/forged tokens. These do not replace PostgreSQL integration tests.

`requirements.txt` contains bounded runtime versions; `requirements-dev.txt` adds pytest and HTTPX. FastAPI/Pydantic handle routing and validation; SQLAlchemy/psycopg provide database access; python-dotenv loads local settings; pwdlib[argon2] hashes passwords; PyJWT signs/verifies tokens; email-validator checks emails; python-multipart parses login forms. Tested using the project's Python 3.14 environment. Version ranges are not a full dependency lock.

## Public deployment

Use HTTPS, a secret manager, and login/registration rate limits at the gateway. This implementation does not include throttling, email verification, password reset, refresh tokens, or immediate logout/revocation. Tokens remain valid until expiration unless a user is deleted or the secret is rotated. Keep tokens out of URLs/logs and avoid browser localStorage. Registration reports duplicate emails, revealing whether an address is registered.

Implementation reference: [FastAPI security guide](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/).


## Visual workspace

Open http://127.0.0.1:8000/ for the website. FastAPI serves the frontend directly; no Node installation or second server is required. The previous API status message is available at `/api`; `/health` and `/docs` remain available.

Sign in with an existing account or use Create account. The dashboard displays live shared projects, your own tasks and progress, and your latest 20 activity updates. Create a project, add a task, and change its status using the task's status selector. Projects are shared across all signed-in accounts under the existing database model. Tasks and activity are restricted to their owner. No database migrations are performed.

Access tokens stay in browser memory, never localStorage or URLs. Reloading the page requires signing in again; expiration returns you to sign-in. Sign out clears this browser's token but does not revoke a token copied elsewhere. The website and API use the same origin. Frontend validation accompanies server-side validation; user content is rendered as text. External Google Fonts are optional and have local fallback fonts.

New authenticated endpoints: `GET/POST /api/projects`, `GET/POST /api/tasks`, `PATCH /api/tasks/{task_id}` for status, and `GET /api/activity`. Lists currently return all shared projects and personal tasks; add pagination before use with large datasets.


## Edit and delete

Use Edit on a project card to change its shared name and description. Use Edit next to a task to change its title, priority, or project; the current status stays unchanged. Delete opens a confirmation with the item name and focuses Keep it by default. Deletion is permanent. Shared projects can only be deleted when they contain no tasks from any user; no cascading deletion is performed. Task management is restricted to the assigned user. Activity retains edit before/after values and deleted item details; this is history, not an undo feature.

Endpoints: `PUT /api/projects/{project_id}`, `DELETE /api/projects/{project_id}`, `PATCH /api/tasks/{task_id}` (partial title, priority, project and/or status), and `DELETE /api/tasks/{task_id}`. DELETE returns 204; nonempty project deletion returns 409. Full role-based project permissions are a future milestone; current projects remain shared across authenticated users.

See [ROADMAP.md](ROADMAP.md) for the original AI-assisted team tracker scope, delivered features, and pending React, GitHub/Slack, imports, AI approvals, notifications, role permissions, retries, and usage tracking.


## Source publication

This public repository contains source code, tests, placeholder configuration, and documentation. Local environment settings, credentials, database data, exports and runtime files are excluded. Read [SECURITY.md](SECURITY.md) before publishing changes. The planned AI and GitHub/Slack integrations are not yet implemented; see the roadmap for current progress.
