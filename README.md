# AI Engineering Tracker

A local engineering workspace with FastAPI, PostgreSQL, secure sign-in, project teams, tasks, progress and activity history. The current interface uses HTML/CSS/JavaScript. The React migration, AI assistance, GitHub/Slack and imports remain on the [roadmap](ROADMAP.md).

## Setup

From the project root:

```sh
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

For a fresh installation, copy `.env.example` to `.env` and replace the placeholders. Preserve an existing `.env`. Generate your own secret locally:

```sh
python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Set `JWT_SECRET_KEY` to the generated value and `DATABASE_URL` to PostgreSQL. Never share or commit `.env`. Signing secrets must be at least 32 bytes. Access tokens expire after 30 minutes by default (`ACCESS_TOKEN_EXPIRE_MINUTES`, range 1–60).

For a fresh PostgreSQL database only:

```sh
createdb ai_engineering_tracker
python -c 'from database import Base, engine; import models; Base.metadata.create_all(bind=engine)'
```

Back up an existing database before migrating. From `backend`, apply the versioned membership migration and start:

```sh
python migrate.py
uvicorn main:app --reload
```

Open http://127.0.0.1:8000/ for the website, or http://127.0.0.1:8000/docs for API testing. No separate frontend server is required. API status is at `/api`; `/health` remains available.

## Project teams

New projects are private to their creator, who becomes Owner. Use **Team** on a project card to view members. Owners can add registered people by email as Editor or Viewer. Access is immediate; no invitation email is sent. Member lists expose names and roles, not emails.

| Action | Owner | Editor | Viewer |
| --- | --- | --- | --- |
| Read project, members and team tasks | Yes | Yes | Yes |
| Edit project name/description | Yes | Yes | No |
| Create own tasks | Yes | Yes | No |
| Edit/delete own tasks | Yes | Yes | No |
| Edit/delete others' tasks | Yes | No | No |
| Assign/reassign tasks | Yes | No | No |
| Manage members and roles | Yes | No | No |
| Delete an empty project | Yes | No | No |

Nonmembers cannot read project/member/task data. Rules are enforced server-side on every request. Global user roles do not bypass project permissions. Only Owners and Editors can receive new assignments. A demoted Viewer can read their existing assignments but cannot change them. Reassign all of a member's tasks before removing them. Owner removal/demotion is blocked; ownership transfer is not supported yet.

Use the **My tasks / Team tasks** selector to switch views. Progress cards remain personal. Tasks support descriptions, priorities, assignees and statuses. Moving a task requires write access to both projects and an eligible assignee in the destination. Only the appropriate owner can reassign it. Website deletion asks for confirmation and is permanent. Nonempty projects cannot be deleted. Each user sees their own latest 20 activity entries, including edit/delete/member-management details. This is not undo or a tamper-proof enterprise audit system.

## Existing database migration

`python migrate.py` adds `project_members` and `app_migrations`. It does not rewrite existing users, projects, tasks or activity records. It is transactional and idempotent. With one existing user, that user becomes Owner of old shared projects. With multiple users, it refuses to guess and requires an authorized operator to choose:

```sh
python migrate.py --legacy-owner-id USER_ID
```

Users present at migration keep Editor access to old shared projects, except the selected Owner. Later accounts are not automatically added. New projects are private until members are added. Do not select a legacy owner without authorization.

Create a private PostgreSQL backup before applying this update. Migration and preservation have been checked against isolated SQLite and temporary PostgreSQL fixtures; those checks do not replace a backup of real data. Store backups outside Git with restricted file access. For recovery, stop the app and first restore the backup into a separate database; verify its contents before changing `DATABASE_URL`. Do not automatically drop membership tables as a downgrade: that loses access configuration. Backup retention, off-device storage and a full operational restore drill remain pending.

## API

- `POST /auth/register`: JSON name, email and password (15–128 characters).
- `POST /auth/login`: form `username` (email) and `password`; returns a bearer JWT.
- `GET /me`: public profile.
- `GET/POST /api/projects`, `PUT/DELETE /api/projects/{id}`.
- `GET /api/tasks?scope=mine` (default), or `scope=team`; `POST /api/tasks`.
- `PATCH/DELETE /api/tasks/{id}`; PATCH accepts partial title, description, priority, status, project and assigned user ID.
- `GET/POST /api/projects/{id}/members`; `PUT/DELETE /api/projects/{id}/members/{user_id}`.
- `GET /api/activity`: current actor's latest 20 updates.

Send `Authorization: Bearer <access_token>`. Invalid tokens return 401; insufficient member roles return 403; nonmember access returns 404. Validation returns 422; duplicate membership and protected deletions return 409. Successful DELETE returns 204.

## Tests and dependencies

From `backend` with the virtual environment active:

```sh
python -m pytest -q
python -m pip check
```

Tests use isolated SQLite databases and signing secrets. Coverage includes authentication, permissions, assignments, revocation, nonmember isolation, migration/idempotency, data preservation, and project/task management. PostgreSQL migration/isolation was checked in a temporary schema that was rolled back. Browser checks cover project privacy copy, team management, task descriptions and assignee choices. Viewer rules are covered by automated tests; a complete multi-account browser check is still pending.

Dependencies are bounded in `requirements.txt`; development tools in `requirements-dev.txt`. FastAPI/Pydantic provide routing/validation, SQLAlchemy/psycopg database access, python-dotenv local settings, pwdlib with Argon2 hashing, PyJWT tokens, email-validator address validation, and python-multipart login forms. Tested with Python 3.14. Ranges are not a full lockfile.

## Security and publication

Passwords are stored as Argon2id hashes. Profile/validation responses omit submitted passwords and hashes. JWT verification requires the expected issuer, algorithm and expiration. Browser tokens stay in memory; refresh requires sign-in. Sign out clears this browser's token, not a copied token. The orbit animation supports pause and reduced-motion preferences. Optional Google Fonts have local fallbacks.

Before public hosting, add HTTPS, rate limiting, email verification/recovery, session revocation, production secrets and backup/restore procedures. Registration reports duplicate emails. Lists need pagination for large datasets. Project writes serialize with membership changes; broader conflict handling remains future work. No AI or external notifications are active. Read [SECURITY.md](SECURITY.md) and run the staged-file secret check before publishing source. Keep real `.env`, backups, logs, uploads and database files private.

## Development workflow

Commit and push completed, verified app changes to GitHub. Keep changes that still require a database rollout or permission approval on a feature branch until that approval and verification are complete. Run the tests, inspect the staged diff, and run `backend/.venv/bin/python scripts/check_public_files.py` before each publication. Never commit real environment settings, local backups, database files or runtime data. See [TESTING.md](TESTING.md) for manual team-permission checks after installation.
