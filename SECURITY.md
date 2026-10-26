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

Authentication, task ownership checks, validated inputs, safe public profile responses, and browser response headers are implemented. Team/project ownership and full role-based permissions are still pending: all signed-in users currently share projects, may edit them, and may delete empty projects. Tasks are restricted to their assigned user. AI and third-party integrations are not yet connected.

Before public deployment, add HTTPS, rate limiting, account recovery/verification, session revocation, team permissions, backup/restore procedures and a deployment security review. Do not expose the development server directly to the internet.

If you find a vulnerability, avoid posting credentials, user data, or exploit details in a public issue. Use a private reporting channel if one is available on the repository.
