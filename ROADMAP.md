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

The website now uses React with Vite, with its compiled assets served by FastAPI. Project-level teams now have Owner, Editor and Viewer permissions. New projects are private until an owner adds registered members. The approved versioned migration added membership and migration-history tables without rewriting original records. Organization-level teams and ownership transfer are not implemented. Activity history is actor-specific, retained, and not a tamper-proof enterprise audit system. Deletion is permanent; nonempty projects cannot be deleted. Private local backups and record-preservation verification were completed before installation. Backup retention, off-device copies and a full operational restore drill remain pending.

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
- [ ] Add email/file import with previews and validation before saving.
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
