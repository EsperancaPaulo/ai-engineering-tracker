# AI Engineering Tracker

A local engineering workspace with FastAPI, PostgreSQL, secure sign-in, project teams, tasks, progress and activity history. The interface uses React with Vite, served by FastAPI. Owners can preview and import public GitHub issues or CSV task lists. Optional AI drafts can summarize selected public issues and suggest priorities for owner review. Saved-email imports, private assignment notifications, reports, and optional reviewed Slack updates are also available. See [service setup](SERVICE_SETUP.md) and the [roadmap](ROADMAP.md) for connection and launch limits.

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
python migrate_automation.py
python migrate_workflows.py
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

Create a private PostgreSQL backup before applying this update. Migration and preservation have been checked against isolated SQLite and temporary PostgreSQL fixtures; those checks do not replace a backup of real data. Store backups outside Git with restricted file access. For recovery, stop the app and first restore the backup into a separate database; verify its contents before changing `DATABASE_URL`. Do not automatically drop membership tables as a downgrade: that loses access configuration. The private backup utility and isolated full restore drill are documented in SERVICE_SETUP.md; off-device storage still requires operator setup.

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
- `POST /api/projects/{id}/files/preview`: Owner-only CSV body (`text/csv`), validates and previews without saving.
- `POST /api/projects/{id}/files/import`: Owner-only selected `row_numbers` from a signed `preview_token`.
- `GET /api/task-import-template.csv`: public example template containing no user data.
- `GET/POST /api/projects/{id}/rules`: Owner-only reusable import rules (new rules are drafts).
- `PUT /api/projects/{id}/rules/{rule_id}`: edit using current revision; saves as draft.
- `POST /api/projects/{id}/rules/{rule_id}/preview`: test up to five examples without saving tasks.
- `PATCH /api/projects/{id}/rules/{rule_id}/state`: pause, or enable using a matching-example preview token.
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

The frontend has 41 tests for account/session behavior, viewer controls, task editing, failed saves, safe deletion, animation controls and stale-response handling. The backend has 167 tests, including checks that compiled assets load, source files are not served, and a missing frontend build returns a useful error. Frontend requests use the existing API and role checks; migration 003 adds five empty workflow/security tables; original records and permissions are preserved.

Tests use isolated SQLite databases and signing secrets. Coverage includes authentication, permissions, assignments, revocation, nonmember isolation, migration/idempotency, data preservation, and project/task management. PostgreSQL migration/isolation was checked in a temporary schema that was rolled back. React browser checks cover owner and editor sign-in, editing, task progress/activity, team controls, animation and sign-out isolation. Viewer restrictions are also covered by automated frontend/backend tests and the earlier manually verified permissions.

Dependencies are bounded in `requirements.txt`; development tools in `requirements-dev.txt`. FastAPI/Pydantic provide routing/validation, SQLAlchemy/psycopg database access, python-dotenv local settings, pwdlib with Argon2 hashing, PyJWT tokens, email-validator address validation, and python-multipart login forms. Tested with Python 3.14. Python dependency ranges are not a full lockfile. React/Vite and frontend test tools are pinned in `frontend/package.json` and resolved by `frontend/package-lock.json`. Use `npm ci` to reproduce the frontend installation.

## Security and publication

Passwords are stored as Argon2id hashes. Profile/validation responses omit submitted passwords and hashes. JWT verification requires the expected issuer, algorithm and expiration. Browser tokens stay in memory; refresh requires sign-in. Sign out revokes the submitted token server-side and clears this browser; password reset invalidates all prior sessions. The orbit animation supports pause and reduced-motion preferences. Optional Google Fonts have local fallbacks.

Before public hosting, complete HTTPS, shared durable rate limits, real email delivery acceptance, production secrets and off-device backup operations. Registration reports duplicate emails. Lists need pagination for large datasets. Project writes serialize with membership changes; broader conflict handling remains future work. AI requests require explicit configuration and an owner action; external delivery stays disabled until configured and explicitly approved. Read [SECURITY.md](SECURITY.md) and run the staged-file secret check before publishing source. Keep real `.env`, backups, logs, uploads and database files private.

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

As project Owner, choose **Import issues**, enter `owner/repository`, and preview open issues. Previewing saves nothing. Review details and source links, select up to 10 issues, then confirm import. Imported tasks start as To do with Medium priority and your assignment by default; enabled import rules can change priority/assignee and add checklist text as shown in preview. The original text and source link are retained. Repeated imports of the same issue into that project are skipped. Deleted imported tasks are still recorded as previously imported.

This uses public GitHub data without credentials and never changes GitHub. Pull requests are excluded. Previews expire after five minutes and are bound to the owner and project. Private repositories can use a backend-only, project-bound and repository-allowlisted credential; see SERVICE_SETUP.md. OAuth and automatic synchronization remain future work. Optional reviewed AI drafts are described below. Requests have timeouts, one bounded retry for transient failures, and rate-limit feedback. No schema migration is required for this update; provenance is stored in existing activity records.

## Optional AI drafts with owner approval

This feature is installed disabled by default. Without an API key, original issue imports continue normally and the UI says AI suggestions are not configured. It never substitutes a mock response for real AI.

For OpenAI API setup, create a project key in your OpenAI platform account and configure API billing/budget controls. ChatGPT subscriptions do not supply API credit. Save these settings only in the existing private backend `.env` and restart the backend:

```dotenv
AI_SUGGESTIONS_ENABLED=true
OPENAI_API_KEY=replace-with-your-private-project-key
OPENAI_MODEL=gpt-4.1-mini-2025-04-14
```

The model is configurable; use one available to your API project that supports Responses and Structured Outputs. The default snapshot is documented in the [model reference](https://developers.openai.com/api/docs/models/gpt-4.1-mini). Requests follow the [Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs), use the fixed OpenAI Responses endpoint, and set `store:false`. This setting does not itself guarantee zero provider retention; review your API account's data controls.

As Owner, preview public issues and select up to three. **Send to OpenAI & draft suggestions** explicitly sends only their public issue numbers, titles and bounded descriptions to OpenAI; API charges apply. It sends no account credentials, project descriptions or local tasks. Each request has a 40-second timeout, an 1,800-output-token cap and no automatic retries. The local single-worker guard allows at most ten attempts per user per hour, at least fifteen seconds apart, including failures; it resets on restart and is not a production spending limit. Configure provider-side budget controls before enabling it.

Drafts show a summary, priority, rationale and a source quote matched exactly against that issue's title/body. Source links are constructed by the app, not generated by the model. This checks provenance but cannot prove the draft's interpretation is correct. Review the original before checking **Approve AI summary and … priority** for each issue. Approval defaults to off; nothing is changed until final import. Unapproved issues keep the original text and use enabled rule actions, with Medium as the default priority. Approved imports retain the summary, original text and source link, and record the model, suggestion and owner decision in activity history. Cancelling discards the unsaved drafts; cancelled/unimported drafts are not retained in activity history.

The model has no tools, workspace access, notification access or write capability. Untrusted issue instructions are treated as data. Output shape, issue numbers, bounds and source quotes are checked server-side. Refused, incomplete, ungrounded or invalid output is rejected; users can still import the originals. No new tables or changes to existing records/permissions are required. Automated tests mock the provider. A configured real API request and human acceptance check are still required before calling the live AI connection verified.

## CSV task imports

As project Owner, choose **Import file** and download the CSV template. Export/save your list as CSV UTF-8 with a required `title` column and optional `description` and `priority` columns. Priorities are `low`, `medium` or `high`; blank priorities become Medium. Header names are trimmed and case-insensitive. Unknown or repeated columns are rejected so extra fields such as assignees/statuses cannot silently alter the result.

Choose a `.csv` file, then Preview file. Uploads are streamed with a 256 KB byte limit, decoded as UTF-8 (BOM accepted), and parsed strictly with at most 100 CSV data records. Quoted commas and multiline descriptions are supported. Titles are 1–200 characters on one line; descriptions are at most 8,000 characters. Blank records are ignored but count toward the 100-record bound. Preview row numbers count CSV records, with headings as row 1; multiline fields remain one record.

The preview identifies valid rows, invalid rows with reasons, and duplicates. It saves no tasks or activity records. Select up to 25 ready rows and confirm import; tasks start as To do with the reviewed priority/assignee; enabled rules can change those defaults as shown in preview. Use Select first ready rows to avoid ticking every row separately. Correct invalid rows in the source and preview again. Nothing is overwritten.

Duplicate checks compare the trimmed title, normalized description line endings and priority. Identical current project tasks or prior file-import fingerprints are skipped, as are repeated selected rows in a file. Duplicate checks run again under the project write lock at confirmation, so replays and overlapping imports do not create extra tasks. Identical imported rows stay marked as previously imported after the task is edited/deleted. Changing title, description or priority creates a different row and may create a new task; this is not synchronization or an update operation.

CSV content goes only to this app, not an AI service. The original file and filename are not stored; valid rows are returned in a signed five-minute preview bound to the owner and project, retained only in browser memory until import/close. Imported tasks and per-row provenance (fingerprint, row number, project/task IDs and actor) are saved in the existing tables. Preview tokens contain readable task content: keep them private and do not share request logs. No new tables, permission changes or paid API calls are required.

CSV is the first file source; Excel workbooks, column mapping, emails, AI processing of private files and scheduled imports remain future work. The bulk workflow removes repetitive data entry now and provides a source for later automation.

## Reusable import automation rules

Project Owners can open **Rules** on a project card. A rule matches a literal, case-insensitive keyword in the title, description, or either field of a new CSV/GitHub import. It can set priority, assign an existing eligible project member, and append checklist text. No regular expressions, AI calls, external notifications or background scheduling are involved. Manual task creation and existing tasks are unaffected.

1. Save the rule as a draft. At least one action is required.
2. Enter a matching example and choose Preview this rule. This tests the saved rule alone and saves no tasks.
3. Review the outcome, then enable it for future imports. Activation needs a project/owner/rule/revision-bound preview from the last five minutes.
4. Preview your CSV or GitHub import. Matched rows show the rule, resulting priority, assignee and checklist. Confirm the selected imports as usual.

Up to 20 reusable rules are supported per project. The first matching enabled rule wins in creation order; later matching rules are not combined. Edit existing rules to reuse them; rule deletion/reordering are not implemented. Editing always pauses a rule, requiring another preview before enabling. Pause stops future applications without undoing past work. Any change to enabled rules invalidates older import previews; re-preview to see current outcomes.

Assignees must be existing Owners or Editors in that project and are rechecked at import. Rules never grant membership or bypass permissions. If a matched rule points to an unavailable/demoted member, fix/pause it and re-preview. Checklist text has up to ten unique nonempty items of 120 characters each; it is appended as `- [ ]` lines in task details, not a separate interactive checklist component. Combined task details remain bounded to 8,000 characters.

If an owner explicitly approves an AI priority during GitHub import, that approved priority overrides the rule's priority. The rule's assignment and checklist still apply. Original source IDs/fingerprints remain the basis for duplicate checks, so transformed tasks are not imported again on retries. Applications record rule ID/revision, source, task, actor, priority/assignment before and after, and checklist in activity history.

This version adds an empty `automation_rules` table with migration `002_import_automation`. Back up the existing database before running `python migrate_automation.py` from backend. The additive, transactional/idempotent migration does not rewrite users, tasks, membership, projects or activity. Empty project deletion also removes its rule definitions while retaining activity history. Do not drop the table as an automatic downgrade; pause rules instead.

## Map existing CSV headings

For an exported spreadsheet with headings such as Summary, Notes and Importance, choose Import file → select CSV → Choose my CSV columns → Read column headings. Map a required Task title column and optional Task details/Priority columns; unselected columns are explicitly ignored. Blank details are empty, omitted/blank priorities become Medium, and mapped priority values must still be low/medium/high. Mappings use column positions so repeated heading names can be distinguished. Limits: 40 headings, 100 characters per heading, existing 256 KB/100-row/25-selected limits.

Preview and review the actual rows before selecting/importing. Changes to mappings discard the previous review; changing files clears mapping choices. Mappings are per-file and are not persisted as presets. Status/assignee columns cannot alter permissions or bypass rules. Duplicate fingerprints use the resulting title/details/priority, so mapping and canonical-column imports of identical tasks cannot silently duplicate one another. No AI or schema migration is needed.

`POST /api/projects/{id}/files/columns` accepts bounded raw CSV and returns headings/positions only, owner-only and read-only. Preview can receive an `X-CSV-Mapping` JSON header mapping title/description/priority to distinct zero-based column indexes; unsupported keys and invalid indexes are rejected. The raw upload remains bounded and no original file is stored.
