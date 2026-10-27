# Private service setup

Preserve existing `backend/.env`; add settings from `.env.example` privately. Never put keys in frontend files, chat, GitHub or screenshots. Restart the backend after changing settings. All integrations are optional; local task/rule/file workflows need no paid AI API.

## Slack: one project, one test channel

1. At https://api.slack.com/apps create an app From scratch in your workspace.
2. Enable Incoming Webhooks, choose Add New Webhook to Workspace, and select a dedicated test channel. Complete authorization yourself.
3. Save its secret URL as `SLACK_WEBHOOK_URL` privately. Set `SLACK_CHANNEL_LABEL` to the actual channel name, and `SLACK_PROJECT_ID` to the project number shown in Report & updates.
4. Keep `SLACK_SENDING_ENABLED=false`. Open Report & updates to preview the exact update and destination without sending.
5. After deciding to send to that channel, set the flag true and restart. Review again and use the explicit confirmation button yourself. Only owners send. The same message is attempted once; check the channel after any uncertain result.

A webhook is bound to its selected channel. Changing the label alone does not change the destination. No automatic background posts or direct messages are active. Official setup: https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks/

## Email: Gmail / Google Workspace selected

Gmail / Google Workspace is the selected provider. Incoming mailbox collection and outgoing account emails are separate capabilities. The current app supports saved `.eml` imports and outgoing certificate-verified SMTP; it does not collect mail automatically or implement OAuth mailbox access yet.

Ask your provider for its supported authenticated SMTP configuration. Populate `SMTP_HOST`, port 465 or 587, `SMTP_USERNAME`, `SMTP_PASSWORD` and `SMTP_FROM` privately. Use a dedicated least-privilege app credential only if supported by that provider; never disable account protections to make SMTP work. OAuth-only policies need a provider-specific adapter before activation.

`APP_PUBLIC_URL` must be the address you actually open, such as `http://127.0.0.1:8000` locally; production needs HTTPS. Leave `REQUIRE_VERIFIED_EMAIL=false` until a human tests delivery to their own mailbox, single-use verification and password reset. Resetting the password invalidates old sessions. No AI is involved. Mail may carry provider costs or limits; choose before activation.

## Private GitHub: optional

Create a fine-grained credential restricted to the selected repository with Issues read access and the required metadata access. Configure `GITHUB_READ_TOKEN`, `GITHUB_PROJECT_ID` and comma-separated `GITHUB_ALLOWED_REPOSITORIES=owner/repository` privately. Do not reuse a broad CLI credential. Current scope is issue reading only, not repository writes or synchronization. Confirm project membership before import: private imported text is shared with those members. Private imports cannot be sent to AI drafting. Live acceptance requires a disposable issue in your authorized repository.

## Backups and restore verification

Run from the project root with the existing backend environment:

```sh
backend/.venv/bin/python scripts/database_maintenance.py backup
backend/.venv/bin/python scripts/database_maintenance.py verify-restore --archive backups/ARCHIVE_NAME.dump
```

Use the archive name printed by the first command. Archives and matching manifests are private and ignored by Git. The tool verifies a full restore in its own temporary database, compares record fingerprints, then removes only that temporary database. It never overwrites the live database. PostgreSQL command-line tools and permission to create a temporary database are required. Pause writes during backups for a stable snapshot.

Operational policy: back up before every migration and at the end of an active workday; retain at least the five latest verified copies plus the pre-migration copy until acceptance. Review old copies manually; nothing is automatically deleted. Set up an encrypted off-device copy under your control before relying on the app for a team. A backup on this laptop alone does not protect against losing the laptop.

## Hosting remains a separate setup

Do not expose the development server. Choose a hosting provider, database/backup plan, domain and spending limit first. HTTPS, production secrets, shared persistent rate limiting, scheduled backups and provider acceptance checks are still required. Docker/hosting deployment has not been verified in this local environment. Paid AI activation remains separate and disabled without funded API access.

### Gmail outgoing recovery emails

1. Open https://myaccount.google.com/security and enable 2-Step Verification yourself if needed.
2. Open https://myaccount.google.com/apppasswords. If available, create an app password named AI Engineering Tracker. If your Workspace administrator or account policy blocks this, stop and use an OAuth adapter instead; do not weaken protections. Google recommends Sign in with Google when supported.
3. In the existing private backend `.env`, preserve all other settings and set:

```dotenv
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-sending-email@example.com
SMTP_PASSWORD=your-private-google-app-password
SMTP_FROM=your-sending-email@example.com
APP_PUBLIC_URL=http://127.0.0.1:8000
REQUIRE_VERIFIED_EMAIL=false
```

Replace the example addresses with the same actual Gmail sender account. Store the generated app password (without display spacing), never your normal Google password. This is outgoing mail only; it grants no automatic inbox collection in this app. Restart the backend after saving. Then the human tester uses Account → Email me a verification link to their own registered mailbox and completes it themselves. Do not enable mandatory verification until delivery is accepted. Google may restrict sending; a Workspace administrator may require different settings.

Official references: [App passwords](https://support.google.com/mail/answer/185833?hl=en), [SMTP settings](https://support.google.com/mail/answer/7104828?hl=en).

Incoming Gmail collection will use a separate OAuth connection with explicit review of mailbox permissions, dedicated project/label binding and a durable ingestion queue. It is not enabled by SMTP setup. Read-only Gmail scope can read the mailbox broadly even when the app filters a label; Google classifies that scope as restricted. Use a dedicated test mailbox before real team mail. OAuth setup and consent will be guided when that adapter is ready; do not create broad mailbox credentials now. [Google scope reference](https://developers.google.com/workspace/gmail/api/auth/scopes).
