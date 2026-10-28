# AI Engineering Tracker — product roadmap

This is the source of truth for the broader product, not just the current screen. Update it as milestones are delivered. Do not mark a feature complete based only on a mockup.

## Original product brief

Build an AI-assisted task and issue tracking system for engineering teams. Use React for the interface, a backend API, and PostgreSQL for tasks, users, and activity history. Connect GitHub and Slack securely; process emails or exported files with AI to summarize issues and suggest priorities. Send important updates to a shared Slack channel and urgent issues to the responsible team member, while avoiding unnecessary notifications. Track usage. Provide audit logs, role-based permissions, error handling and automatic integration retries. Require human approval before important AI-generated changes. The goal is practical time savings and better communication, with personally reviewed and tested code.

## Delivered foundation

- [x] Local FastAPI application connected to PostgreSQL.
- [x] User, Project, Task, and ActivityLog tables.
- [x] Registration and login: Argon2id password hashes, validated inputs, signed expiring JWTs, protected profile route.
- [x] Responsive local website: registration, login, overview, shared projects, personal tasks, progress and recent activity.
- [x] Light green design with warm white and sage surfaces.
- [x] Animated orbital illustration with connected nodes, pause/resume, and reduced-motion support.
- [x] Create projects/tasks, task statuses and priorities, task search and status filter.
- [x] Edit shared project name/description; edit own task title, priority and project.
- [x] Delete own tasks and empty shared projects with confirmation in the website.
- [x] Keep activity and before/after details for edits and deletions.
- [x] Automated authentication, tracker, validation and account-isolation tests.

## Important limits of the current foundation

The website now uses React with Vite, with its compiled assets served by FastAPI. Project-level teams now have Owner, Editor and Viewer permissions. New projects are private until an owner adds registered members. The approved versioned migration added membership and migration-history tables without rewriting original records. Organization-level teams and ownership transfer are not implemented. Activity history is actor-specific, retained, and not a tamper-proof enterprise audit system. Deletion is permanent; nonempty projects cannot be deleted. Private local backups and record-preservation verification were completed before installation. A private backup utility and full isolated restore drill are verified; off-device copies and operational retention remain pending.

## Next milestones

### 1. Team-ready core

- [x] Deploy project ownership/membership with an approved, versioned additive migration and private database backup.
- [x] Enforce Owner/Editor/Viewer permissions, controlled assignments and a team task view.
- [x] Migrate the interface to React while preserving the accepted green design, animation, API and permissions.
- [x] Add task descriptions and assignee names to the UI.
- [x] Extend issue details with reviewed public GitHub imports and source links.
- [ ] Define backups, restore and retention before relying on this for team operations.

### 2. Secure connected sources

- [x] Import selected public GitHub issues with preview, source links and duplicate prevention.
- [ ] Connect private GitHub repositories with minimum-permission credentials.
- [x] Add CSV task import with previews, validation, owner confirmation and duplicate prevention.
- [ ] Extend sources to email and other file formats.
- [ ] Add secure credential storage, minimum permissions, and clear connection management.
- [x] Add GitHub import error handling, bounded retries and duplicate prevention.

### 3. AI assistance with human control

- [ ] Summarize imported issues with source references.
- [ ] Suggest priorities with a clear explanation.
- [ ] Review and explicitly approve important changes before applying them; retain the decision history.

### 4. Useful, restrained notifications

- [ ] Connect Slack, select the shared channel and responsible recipients.
- [ ] Preview notification rules before activation; send only authorized updates.
- [ ] Send important updates to the channel and urgent issues to the responsible member.
- [ ] Deduplicate updates and provide notification preferences to avoid noise.

### 5. Reliability, usage and launch

- [ ] Add useful, privacy-conscious usage and time-saving measures.
- [ ] Add pagination and stronger concurrency safeguards for larger teams.
- [ ] Add password recovery, email verification and session revocation.
- [ ] Add HTTPS hosting, production secrets, rate limits, backups and deployment checks.
- [ ] Review real team feedback and improve the workflow based on evidence.

## Working rules

Preserve existing user records and secrets. Do not publish the local database or credentials. Keep important AI decisions subject to human approval. Do not activate external notifications without the user's authorization. Keep the UI plain and useful. Finish and verify one milestone before describing it as delivered.


## Team-permissions milestone delivered

The approved team update is installed locally: private new projects, Owner/Editor/Viewer roles, registered-member management, owner-controlled assignments, team task views and task descriptions. The pre-existing sole account became Owner of its existing project. A private PostgreSQL backup was archive-verified before migration; full fingerprints confirmed every original user, project, task and activity row remained unchanged.

Verification: 62 automated tests passed; PostgreSQL migration/idempotency and isolation passed in a temporary rolled-back schema; browser checks covered the owner/editor screen, descriptions and assignee choices. Live website/API checks confirmed the existing project and task remain, owner membership is correct, team/personal task views work, and unauthenticated access is blocked. A full multi-account browser check is still pending; role restrictions and revocation are covered by automated tests.

Keep completed, verified app updates committed and pushed to GitHub. Exclude real environment settings, database contents, backups and runtime data. The remaining integrations/AI milestones above are still pending.


## React interface milestone

The complete website is implemented in React components with a locked Vite build. FastAPI serves compiled assets at the existing port 8000 address. The old DOM implementation is removed. This milestone changes no database schema, credentials, existing records or permission rules. The existing green design, orbit animation, account flows, project/task editing and deletion, memberships and assignment controls are preserved.

Verification: 17 frontend tests and 63 backend tests pass. Browser checks covered the built owner/editor interface, saved task edits, completion/progress/activity, team controls, animation and sign-out isolation using copied demo data. Viewer restrictions are covered by automated tests. No AI calls or external notifications have been activated. Next: GitHub issue/import foundations, followed by AI summaries and suggestions with approval controls.

## Registration security and public import milestone

New-account passwords are checked locally for length and guessability without AI. Password confirmation and feedback are included; existing credentials are preserved. Real Cloudflare Turnstile is required for new registrations when configured, with server-side token validation and fail-closed setup. Real challenge completion is a manual acceptance check. Owners can review and explicitly import selected open issues from public GitHub repositories; imports preserve source links and skip duplicates. No database migration, private GitHub access, AI processing or notifications are part of this milestone. Automated verification: 27 frontend tests and 90 backend tests.

## Reviewed AI draft implementation — awaiting live API acceptance

The optional owner-only public-issue AI workflow is implemented with structured summaries, explained priority suggestions, exact source quotes, separate per-issue approval and final import confirmation. It preserves originals and records imported review decisions without a database migration. It remains disabled without private OpenAI API configuration; no simulated AI is shown. Automated validation uses mocked provider responses. The AI milestones above remain unchecked until a real configured API request and human acceptance test pass. Durable usage accounting, cancelled-draft history and production spending/rate safeguards remain pending.

## CSV bulk-import milestone

Owners can preview bounded CSV UTF-8 task lists, inspect errors/duplicates, select up to 25 rows at once and confirm additive imports. Titles/details/priorities are copied automatically, tasks start as To do assigned to the owner, and original import fingerprints prevent accidental repeated entry. No AI credit, external upload, schema migration or existing record changes are needed. Automated validation: 34 frontend tests and 127 backend tests.

Automation direction remains source ingestion → validation/deduplication → optional AI summary/priority drafts → human approval of important changes → controlled assignments/notifications and audit history. Next candidates are reusable import rules and mappings, then email ingestion and queued jobs. AI activation remains pending available credits and live acceptance; its implementation is retained.

## Reusable import rules milestone

Owner-managed draft rules now support case-insensitive literal keyword matches, priorities, existing-member assignment and standard checklist text for CSV/GitHub imports. Matching-example preview is required before activation. First matching enabled rule wins; changes invalidate old import previews, and edits pause the rule. Final imports recheck eligible assignees and write rule-action history atomically with tasks, preserving source duplicate protection. Existing tasks and permissions remain unchanged.

The 002 migration adds empty rule storage after a private archive-verified backup. Migration/idempotency/preservation are checked with SQLite fixtures and temporary rolled-back PostgreSQL schemas. Verification: 36 frontend tests and 139 backend tests, plus browser draft/preview/activation/import checks using isolated demo records.

Next automation work: incoming email/queued source ingestion, column mappings and scheduling, then controlled Slack notifications and durable usage metrics. AI summaries/priorities remain implemented but live acceptance awaits API credits. Rules reduce repetitive triage now; they do not replace the planned AI understanding of less predictable work.

## Non-AI workflow milestone (003)

Implemented: saved-email `.eml` previews/imports through existing rules, member-only project reports and CSV exports, paged project browsing, private assignment notices and preferences, logout revocation, strong-password reset and email-verification flows over optional TLS SMTP, reviewed/deduplicated Slack channel updates, and project/repository-scoped private GitHub credentials with AI blocked for private imports. Migration 003 adds empty storage without rewriting existing records. Current automated checks: 154 backend and 39 frontend tests. A private archive and full isolated restore drill passed. External services are mocked in tests; live connection acceptance remains pending configuration.

Remaining non-AI work: choose/configure the email provider; automatic mailbox collection with a durable queue, scheduling/retry and review controls; flexible source-column mappings; live Slack/private-GitHub acceptance, controlled notification rules/direct recipients; durable usage measures; broader list pagination; hosting/HTTPS/shared throttling; off-device backup retention and real team feedback. Current Slack sending is an explicit owner-reviewed action, not a background automation. Email-file imports do not read a mailbox. Reports count records and do not invent time savings. AI activation/quality acceptance still awaits API credits. Do not mark the connected-source, notification or launch milestones fully complete yet.

## Flexible CSV mapping milestone

Owner-reviewed per-file column mapping now accepts existing spreadsheet headings, explicitly ignores unrelated columns and preserves validation, rule actions, role checks and canonical duplicate fingerprints. Header inspection is read-only and bounded. Mapping changes clear previous previews; saved presets/value translations remain future work. No database migration or paid service is needed. Verification: 167 backend and 41 frontend tests plus isolated browser acceptance. Gmail/Google Workspace is selected; outgoing SMTP instructions are documented, while incoming OAuth/queue implementation and live service acceptance remain pending.

## Gmail draft collection milestone

Implemented local Desktop OAuth connection with human consent, project/owner/mailbox binding, fixed Tracker Inbox filtering, a durable paged owner-only review queue, explicit rule-aware import approval, persistent source receipts, dismiss/restore, bounded polling and durable backoff. Optional automatic draft polling requires both owner opt-in and a running local worker; it never creates tasks without review. Migration 004 is additive. Current checks: 181 backend/44 frontend tests and sample-message browser acceptance. Real Google OAuth/labelled collection awaits human consent; SMTP verification and password recovery were separately reported passing.

Remaining: real Gmail acceptance, public OAuth verification/production hosting, installed worker supervision, retention operations, live Slack/private-GitHub acceptance and controlled background notification rules/direct recipients; durable usage measures and broader list pagination; production shared rate limits/off-device backups; real team feedback. AI remains implemented with paid live acceptance pending credits.
