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

The installed team update adds project-level membership and Owner/Editor/Viewer checks on each request. New projects are private until an owner adds registered members. Editors contribute their own work and viewers cannot write. Only owners manage access/assignments and delete empty projects. Owner removal/demotion is blocked; all tasks must be reassigned before removing a member. The global user role does not bypass project permissions. The additive migration needs an authorized legacy owner choice when there are multiple existing users; back up before applying it. Organization-wide administration, ownership transfer, private integrations and AI remain pending. Changes to existing real ownership/access permissions require explicit approval before deployment; the initial local ownership migration was approved and verified.

Before public deployment, add HTTPS, rate limiting, account recovery/verification, session revocation, backup/restore procedures and a deployment security review. Do not expose the development server directly to the internet.

If you find a vulnerability, avoid posting credentials, user data, or exploit details in a public issue. Use a private reporting channel if one is available on the repository.


## React frontend

FastAPI serves only compiled files from `frontend/dist/assets` under `/assets`; frontend source files and package configuration are not exposed by that mount. Tokens stay in memory and are cleared on sign-out/expiration. The browser UI hides disallowed actions, but server-side project permissions remain the authority. Frontend source and lockfiles are public; never add secrets to client code, frontend environment variables or generated bundles. Production source maps are disabled. `dist` and `node_modules` remain ignored. Build the frontend before starting the app from a fresh checkout. The React migration performs no database migration or permission changes.

## Registration and public imports

Password strength checks use local zxcvbn dictionaries and patterns; no AI or external password checking service is called. Existing account hashes are preserved. Turnstile is required for new registrations with real keys in required mode; missing configuration fails closed. The backend sends only the secret and challenge token to Cloudflare, and verifies action, hostname and timestamp. Keep `TURNSTILE_SECRET_KEY` private. The site key is intentionally public. Real human completion must be tested manually; automated tests mock verification and never solve challenges. This does not replace rate limiting, email verification or recovery.

Public GitHub issue previews use a fixed GitHub API origin, bounded repository input, timeouts, a bounded retry and no GitHub credentials. Only project owners can preview/import. Signed short-lived previews bind reviewed content to the owner and project; imports require selection and confirmation. Project writes serialize duplicate checks. Provenance remains in activity records, including after task deletion; a dedicated indexed provenance table may be needed at scale. Imported text is rendered as text, with reconstructed source links. No synchronization, private repository access or external notifications are activated. AI calls are separately opt-in and disabled until configured.

## AI draft boundary

Keep the OpenAI API key in the backend environment. It is never included in browser configuration, signed previews or bundles. Disabled/missing AI setup returns an honest unavailable state, not simulated AI. Only owners with a valid project-bound preview and explicit consent can request drafts for up to three public issues. The request includes only issue numbers, titles and bounded descriptions, uses a fixed provider origin with no redirects/proxy environment, and never gives the model tools. No paid request is automatically retried. Local throttling is per user, per process, resets on restart and requires shared durable budgets before multi-worker or public use.

Structured output and exact source quotes are validated, but source content and model output remain untrusted; the UI renders them as text. Prompt-injection resistance relies primarily on no tools/write authority and explicit human approval, not on treating a prompt as a security boundary. Signed five-minute previews bind the reviewed draft to the owner/project. An owner must opt into each suggestion and confirm import; originals are always retained. Imported decisions record model and draft in the existing activity table. Cancelling does not retain drafts. Activity history is not immutable, and a full rejected/cancelled decision ledger and durable usage accounting remain future work.

Requests use `store:false`; this does not guarantee zero provider retention. Review account data controls and set provider-side budgets before enabling billed requests. Existing tests mock the provider; real API access and output quality must be verified separately after setup.
