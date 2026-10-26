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

The website currently uses plain HTML/CSS/JavaScript served by FastAPI. React has NOT yet been implemented. Projects are shared with all authenticated users; the database has no project owner or team membership yet, so all signed-in users can edit shared projects and delete empty ones. Tasks can only be changed by their assigned user. Users have a role field, but full role-based permissions and team administration are NOT implemented. Activity history is retained but is not a tamper-proof enterprise audit system. Deletion is permanent; audit entries are not an undo feature. A nonempty project cannot be deleted, even if its remaining tasks belong to another user. No existing database tables are migrated for the current management milestone.

## Next milestones

### 1. Team-ready core

- [ ] Deploy the prepared project ownership/membership update after approval of the real-database migration.
- [ ] Deploy the prepared Owner/Editor/Viewer checks, controlled assignments and team task view after the migration.
- [ ] Migrate the existing interface to React while preserving the accepted design and working API.
- [ ] Deploy the prepared task-description UI; extend issue details with the later GitHub/import workflow.
- [ ] Define backups, restore and retention before relying on this for team operations.

### 2. Secure connected sources

- [ ] Connect GitHub for issue ingestion and links, starting read-only.
- [ ] Add email/file import with previews and validation before saving.
- [ ] Add secure credential storage, minimum permissions, and clear connection management.
- [ ] Add integration error handling, bounded retries and duplicate prevention.

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


## Prepared update awaiting deployment approval

The project ownership/membership update is implemented and verified in an isolated test copy. It includes private new projects, project-level Owner/Editor/Viewer permissions, owner-managed registered members and assignments, team task views, descriptions and a versioned additive migration. Automated tests cover role restrictions, nonmember isolation, owner protection, revocation and record-preserving migration. PostgreSQL migration was checked in a temporary rolled-back schema. React, organization-wide administration, ownership transfer and external integrations remain pending.

The real database and currently running application have not been changed for this update. Automatic approval review requires explicit approval to back up the local database and make the sole existing account Owner of the existing project. The private database backup has now been created and archive-verified. Once the ownership change is explicitly authorized, apply the migration, verify original records unchanged, install the app changes, and update this roadmap's delivered status. Do not describe this prepared milestone as live before that process completes.
