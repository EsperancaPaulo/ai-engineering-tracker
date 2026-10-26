# AI Engineering Tracker

A local engineering workspace with FastAPI, PostgreSQL, secure sign-in, project teams, tasks, progress and activity history. The interface uses React with Vite, served by FastAPI. Owners can preview and import public GitHub issues. AI assistance, private GitHub connections and Slack remain on the [roadmap](ROADMAP.md).

## Setup

Use Python 3.14 and Node.js 22.12+ (Node 24 was used for verification). Build the React interface first, from the project root:

```sh
cd frontend
npm ci
npm run build
cd ..
```

Then set up the backend:

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

Open http://127.0.0.1:8000/ for the website, or http://127.0.0.1:8000/docs for API testing. FastAPI serves the built React interface from `frontend/dist`; no separate frontend server is required. If the build is missing, the home route returns a clear 503 message while API routes remain available. API status is at `/api`; `/health` remains available.

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

- `POST /auth/register`: JSON name, email, password (15–128 characters) and a fresh Turnstile `human_token`.
- `GET /auth/config`: password policy and public human-verification configuration.
- `POST /auth/login`: form `username` (email) and `password`; returns a bearer JWT.
- `GET /me`: public profile.
- `GET/POST /api/projects`, `PUT/DELETE /api/projects/{id}`.
- `GET /api/tasks?scope=mine` (default), or `scope=team`; `POST /api/tasks`.
- `PATCH/DELETE /api/tasks/{id}`; PATCH accepts partial title, description, priority, status, project and assigned user ID.
- `GET/POST /api/projects/{id}/members`; `PUT/DELETE /api/projects/{id}/members/{user_id}`.
- `POST /api/projects/{id}/github/preview`: Owner-only public repository issue preview.
- `POST /api/projects/{id}/github/import`: Owner-only import of up to 10 selected issues from the signed preview.
- `GET /api/activity`: current actor's latest 20 updates.

Send `Authorization: Bearer <access_token>`. Invalid tokens return 401; insufficient member roles return 403; nonmember access returns 404. Validation returns 422; duplicate membership and protected deletions return 409. Successful DELETE returns 204.

## Tests and dependencies

From the repository root, verify the frontend and build it before running backend asset checks:

```sh
cd frontend
npm ci
npm test
npm run build
cd ../backend
source .venv/bin/activate
python -m pytest -q
python -m pip check
```

The frontend has 29 tests for account/session behavior, viewer controls, task editing, failed saves, safe deletion, animation controls and stale-response handling. The backend has 90 tests, including checks that compiled assets load, source files are not served, and a missing frontend build returns a useful error. Frontend requests use the existing API and role checks; this migration changes no database schema or records.

Tests use isolated SQLite databases and signing secrets. Coverage includes authentication, permissions, assignments, revocation, nonmember isolation, migration/idempotency, data preservation, and project/task management. PostgreSQL migration/isolation was checked in a temporary schema that was rolled back. React browser checks cover owner and editor sign-in, editing, task progress/activity, team controls, animation and sign-out isolation. Viewer restrictions are also covered by automated frontend/backend tests and the earlier manually verified permissions.

Dependencies are bounded in `requirements.txt`; development tools in `requirements-dev.txt`. FastAPI/Pydantic provide routing/validation, SQLAlchemy/psycopg database access, python-dotenv local settings, pwdlib with Argon2 hashing, PyJWT tokens, email-validator address validation, and python-multipart login forms. Tested with Python 3.14. Python dependency ranges are not a full lockfile. React/Vite and frontend test tools are pinned in `frontend/package.json` and resolved by `frontend/package-lock.json`. Use `npm ci` to reproduce the frontend installation.

## Security and publication

Passwords are stored as Argon2id hashes. Profile/validation responses omit submitted passwords and hashes. JWT verification requires the expected issuer, algorithm and expiration. Browser tokens stay in memory; refresh requires sign-in. Sign out clears this browser's token, not a copied token. The orbit animation supports pause and reduced-motion preferences. Optional Google Fonts have local fallbacks.

Before public hosting, add HTTPS, rate limiting, email verification/recovery, session revocation, production secrets and backup/restore procedures. Registration reports duplicate emails. Lists need pagination for large datasets. Project writes serialize with membership changes; broader conflict handling remains future work. No AI or external notifications are active. Read [SECURITY.md](SECURITY.md) and run the staged-file secret check before publishing source. Keep real `.env`, backups, logs, uploads and database files private.

## Development workflow

Commit and push completed, verified app changes to GitHub. Keep changes that still require a database rollout or permission approval on a feature branch until that approval and verification are complete. Run the tests, inspect the staged diff, and run `backend/.venv/bin/python scripts/check_public_files.py` before each publication. Never commit real environment settings, local backups, database files or runtime data. See [TESTING.md](TESTING.md) for manual team-permission checks after installation.


## Frontend development

React components live in `frontend/src/components`, session state in `frontend/src/App.jsx`, and the API helper in `frontend/src/api.js`. The light green stylesheet lives in `frontend/src/styles.css`. There is no parallel legacy DOM implementation. Tokens stay in React memory, not browser storage. The backend continues to enforce all permissions. Stale requests cannot repopulate a signed-out workspace, and server failures keep editable form input intact.

For optional hot reload, keep FastAPI running and run `npm run dev` from `frontend`. Vite binds to loopback and proxies API calls to port 8000. Use the development address printed in the terminal, commonly port 5173. For everyday use, rebuild after frontend source changes and keep using port 8000. Build before restarting FastAPI on a fresh checkout. Generated `dist` and `node_modules` are ignored; source and lockfiles are committed. Never put secrets into frontend environment variables or bundles. No frontend `.env` is required. Production build source maps are disabled.

The build setup follows the official [React client app guidance](https://react.dev/learn/build-a-react-app-from-scratch) and [Vite documentation](https://vite.dev/guide/).

## Passwords and human verification

New registrations require a 15–128-character password. Local zxcvbn dictionary and pattern checks reject common or easily guessed passwords, including account-related words. The browser shows a live strength rating and requirement checklist, including confirmation. Every requirement must pass before registration can be submitted; the backend independently enforces password strength. These checks do not use AI or send passwords to an external checking service. Existing passwords and sign-in continue to work. Passwords remain Argon2id-hashed; strength estimation is not a breached-password database check.

Create a Managed widget in Cloudflare Turnstile. Add `localhost` and `127.0.0.1` as separate hostnames without protocols or ports, and disable pre-clearance. Save `TURNSTILE_MODE=required`, the real `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY`, and `TURNSTILE_ALLOWED_HOSTNAMES=localhost,127.0.0.1` in the existing private backend `.env`, preserving other settings. Restart the backend after editing environment settings. The public site key is sent to the browser; the secret stays server-side. No frontend environment file is needed.

Registration fails closed when configuration is missing or verification is unavailable. The server verifies each token directly with Cloudflare and checks its registration action, allowed hostname and five-minute validity. Tokens are single use. Managed mode may verify a browser automatically; Cloudflare chooses whether an interactive checkbox is necessary. Cloudflare handles browser challenge data; passwords are not included in verification requests. Existing sign-in does not require Turnstile. Explicit `test` mode is for development only and is labelled in the UI; official dummy keys are rejected in required mode.

## Public GitHub issue import

As project Owner, choose **Import issues**, enter `owner/repository`, and preview open issues. Previewing saves nothing. Review details and source links, select up to 10 issues, then confirm import. Imported tasks start as To do with Medium priority and are assigned to you. The original text and source link are retained. Repeated imports of the same issue into that project are skipped. Deleted imported tasks are still recorded as previously imported.

This uses public GitHub data without credentials and never changes GitHub. Pull requests are excluded. Previews expire after five minutes and are bound to the owner and project. Private repositories, OAuth, automatic synchronization and AI summaries are future work. Requests have timeouts, one bounded retry for transient failures, and rate-limit feedback. No schema migration is required for this update; provenance is stored in existing activity records.
