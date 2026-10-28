# Security and publication

This is an early local development project. Publishing its source does not publish the local database, users, passwords, or runtime configuration, and does not make the running application production-ready.

## Keep private

- Actual `.env` files and JWT signing secrets.
- Database credentials, backups, exports and user data.
- API tokens, SSH/private keys and service-account credentials.
- Logs, uploads and screenshots containing account information.

Only `.env.example` belongs in source control; it contains placeholders. Generate a distinct private signing secret for each environment. Keep credentials in environment settings or a secret manager. Never paste them into issues or pull requests.

Before publishing changes, stage only intended source files, review `git diff --cached`, and run from the repository root:

```sh
backend/.venv/bin/python scripts/check_public_files.py
```

The check inspects the Git index, compares it against local environment values without displaying them, rejects private/runtime paths, and detects common credential formats. It is intentionally conservative and does not guarantee detection of every kind of secret. Always review the actual diff as well. `.gitignore` does not remove a secret that has already been committed. If a credential is ever exposed, revoke/rotate it promptly, then remove it from history.

## Current application limits

The installed team update adds project-level membership and Owner/Editor/Viewer checks on each request. New projects are private until an owner adds registered members. Editors contribute their own work and viewers cannot write. Only owners manage access/assignments and delete empty projects. Owner removal/demotion is blocked; all tasks must be reassigned before removing a member. The global user role does not bypass project permissions. The additive migration needs an authorized legacy owner choice when there are multiple existing users; back up before applying it. Organization-wide administration and ownership transfer remain pending; private integrations require scoped setup and live acceptance. Changes to existing real ownership/access permissions require explicit approval before deployment; the initial local ownership migration was approved and verified.

Before public deployment, complete HTTPS, shared durable rate limiting, live email acceptance, off-device backup operations and a deployment security review. Do not expose the development server directly to the internet.

If you find a vulnerability, avoid posting credentials, user data, or exploit details in a public issue. Use a private reporting channel if one is available on the repository.


## React frontend

FastAPI serves only compiled files from `frontend/dist/assets` under `/assets`; frontend source files and package configuration are not exposed by that mount. Tokens stay in memory and are cleared on sign-out/expiration. The browser UI hides disallowed actions, but server-side project permissions remain the authority. Frontend source and lockfiles are public; never add secrets to client code, frontend environment variables or generated bundles. Production source maps are disabled. `dist` and `node_modules` remain ignored. Build the frontend before starting the app from a fresh checkout. The React migration performs no database migration or permission changes.

## Registration and public imports

Password strength checks use local zxcvbn dictionaries and patterns; no AI or external password checking service is called. Existing account hashes are preserved. Turnstile is required for new registrations with real keys in required mode; missing configuration fails closed. The backend sends only the secret and challenge token to Cloudflare, and verifies action, hostname and timestamp. Keep `TURNSTILE_SECRET_KEY` private. The site key is intentionally public. Real human completion must be tested manually; automated tests mock verification and never solve challenges. This does not replace rate limiting, email verification or recovery.

Public GitHub issue previews use a fixed GitHub API origin, bounded repository input, timeouts, a bounded retry and no GitHub credentials. Only project owners can preview/import. Signed short-lived previews bind reviewed content to the owner and project; imports require selection and confirmation. Project writes serialize duplicate checks. Provenance remains in activity records, including after task deletion; a dedicated indexed provenance table may be needed at scale. Imported text is rendered as text, with reconstructed source links. Synchronization remains unavailable. Optional private repository access and reviewed Slack updates require backend-only scoped configuration. AI calls are separately opt-in and disabled until configured.

## AI draft boundary

Keep the OpenAI API key in the backend environment. It is never included in browser configuration, signed previews or bundles. Disabled/missing AI setup returns an honest unavailable state, not simulated AI. Only owners with a valid project-bound preview and explicit consent can request drafts for up to three public issues. The request includes only issue numbers, titles and bounded descriptions, uses a fixed provider origin with no redirects/proxy environment, and never gives the model tools. No paid request is automatically retried. Local throttling is per user, per process, resets on restart and requires shared durable budgets before multi-worker or public use.

Structured output and exact source quotes are validated, but source content and model output remain untrusted; the UI renders them as text. Prompt-injection resistance relies primarily on no tools/write authority and explicit human approval, not on treating a prompt as a security boundary. Signed five-minute previews bind the reviewed draft to the owner/project. An owner must opt into each suggestion and confirm import; originals are always retained. Imported decisions record model and draft in the existing activity table. Cancelling does not retain drafts. Activity history is not immutable, and a full rejected/cancelled decision ledger and durable usage accounting remain future work.

Requests use `store:false`; this does not guarantee zero provider retention. Review account data controls and set provider-side budgets before enabling billed requests. Existing tests mock the provider; real API access and output quality must be verified separately after setup.

## CSV upload boundary

Only project owners can upload/confirm task lists. Preview accepts a raw `text/csv` body and stops streaming above 256 KB; it does not use an unbounded multipart/file store. Strict UTF-8/CSV parsing, 100-record limits, allowlisted columns and bounded field values prevent file contents from becoming assignments, statuses or executable commands. The browser renders row content as text; formulas/macros are never evaluated. File contents are not sent to any external service. Original uploads/filenames are not persisted.

Signed five-minute CSV previews use a separate issuer and bind rows to the actor and project. They contain readable source text and must stay private. Import rechecks owner permissions and duplicates under the project lock, creates selected tasks/provenance in one transaction, and preserves fingerprints after edits/deletions. Provenance uses existing activity records and scanning; a dedicated indexed import ledger, durable job processing and retention policy remain future work before large-scale operation. This importer is additive, not an automatic update/sync facility.

## Import automation boundary

Only project owners can create/edit/preview/enable/pause rules. All changes serialize on the project lock. Rule names/keywords/actions are bounded and validated, matching uses literal strings rather than executable expressions/regex, and assignments can target only existing eligible project members. Rules do not create memberships, send messages or call external services.

New/edited rules are disabled. Enabling requires a signed five-minute matching-example preview bound to actor, project, rule and revision; concurrent edits invalidate it. Import previews include a digest of enabled rules and server-signed outcomes. Final import compares the current digest and rechecks assignee eligibility under the same project lock, then writes task changes/provenance together. Original source identifiers prevent replayed actions. Rule configuration and actions are audited; history is retained but not immutable.

Migration 002 adds empty rule storage and a migration-history row without changing existing permissions or records. Back up before applying. Rule evaluation affects only confirmed new imports, not existing tasks, manual task creation or background jobs. Import changes still require owner confirmation; future scheduling/notification execution needs its own controls.

## Workflow/security storage (003)

The additive migration creates empty inbox, Slack delivery, revoked-session, user-security and email-grant tables. Existing account hashes, project permissions and task records are preserved. Sign-out stores only a token digest until expiration; password reset increments a session version. Reset/verification grants store only digests, expire after 30 minutes, are single-use, and serialize against account changes. Email links put their secret in a browser fragment, which the UI removes. SMTP requires certificate-verified TLS (465 or STARTTLS 587). Keep mandatory email verification off until delivery is accepted. Public recovery responses do not reveal account existence. Login/recovery throttles are process-local and reset on restart, so public multi-worker deployment needs a shared limiter.

Inbox notices are private to the recipient and require current membership. Slack webhooks are restricted to the fixed Slack HTTPS host and one configured project/channel. Owners preview bounded task titles/statuses/priorities/assignee names, then confirm; descriptions and email bodies are excluded. Plain-text blocks prevent injected markup/mentions. A durable delivery record is committed before sending. Uncertain/failed sends are not automatically retried, preventing duplicate attempts at the cost of requiring manual investigation. No background notifications or Slack direct messages are implemented.

Private GitHub credentials are used only for the configured project and allowlisted repositories. Imported private content becomes visible to project members and is blocked from AI drafting. Do not reuse a broad personal credential. Saved email imports parse bounded plain/HTML body text without opening attachments or fetching links/images. No automatic mailbox access is enabled. CSV exports escape formula-like strings; reports are member-only.

Backups contain sensitive records. The maintenance utility uses private filesystem permissions, checksums and record fingerprints; its restore drill creates and drops its own isolated temporary database and never restores over live data. Keep archives/manifests out of Git. Production encryption, off-device copies and operator retention controls remain operational responsibilities.

## Explicit CSV mapping

Only owners may inspect bounded column headings or submit mappings. Mappings allow only title, description and priority with distinct in-range integer positions (not booleans); no expressions, arbitrary task properties, statuses or assignments are accepted. Other source columns are ignored only in explicit mapping mode. Canonical imports retain strict headings. Mapped rows pass the same validation, signed preview, rule snapshot, final authorization and persistent duplicate checks as canonical CSV. Changing mapping choices in the UI clears the old review. No source filenames or mapping presets are persisted.

## Gmail boundary and retained data

Desktop OAuth uses a random state and PKCE S256, a temporary 127.0.0.1 callback, fixed Google authorization/token/API origins, read-only scope and human consent. Callback access logs are suppressed; tokens/provider errors are never displayed. Token files are atomically written with owner-only modes, reject symlinks/insecure permissions, bind project/owner/mailbox digest and serialize refresh with a filesystem lock. They are local secrets, not encrypted by this app; protect the host. The read-only scope covers more than the selected label, so consent must disclose that scope accurately. Use a dedicated test mailbox.

Collection rechecks project ownership and source binding, filters the configured label and rechecks message label IDs, reads bounded pages/responses, never follows redirects or trusts proxy environment variables, never calls attachments endpoints, and never writes to Gmail. A project lock serializes collection/approval/role changes. Durable cursor, failure/backoff state and unique message fingerprints survive restarts. A worker rechecks automatic mode after taking the project lock. Only the source owner can view or review draft bodies; imported task bodies become normal project-member data. There is no private email → AI path.

Migration 004 adds two empty tables and one migration marker. Pending/dismissed email bodies reside in the local database and private backups until review/operational cleanup; no automatic retention purge is configured. Processed draft bodies are cleared, while hashed message receipts are retained for deduplication after task edits/deletions. Dismissed drafts can be restored. Unsupported emails retain only a safe problem/receipt. This is local single-host polling, not a production distributed queue or encrypted mailbox archive. Explicitly pause and revoke Google consent to disconnect; deleting a project alone does not revoke its OAuth grant. `.private/`, downloaded client JSON and token JSON are blocked from publication; do not add exceptions.
