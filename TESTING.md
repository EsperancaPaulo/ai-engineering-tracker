# Testing project teams

The React interface and team update are installed locally. The frontend framework change requires no additional database migration. The membership migration was approved and applied after creating and verifying a private database backup. Existing records were verified unchanged. Use the steps below to check it in your browser.

## Interface and owner check

1. Open http://127.0.0.1:8000/ and hard-refresh (Command + Shift + R on macOS), then sign in.
2. Your existing project and task should still be present. Your project card should show Owner.
3. Click Team. Your account should be listed as Owner.
4. Create a test task with Task details and a priority. Confirm its details appear below the title.
5. Edit the task title/details/priority, save, then change its status and check progress/activity.
6. Switch My tasks to Team tasks and back. With only your account, these lists can be the same.
7. Try Pause animation and Resume animation.
8. Sign out: project/task content should disappear, and signing back in should reload it. Refresh also requires sign-in because tokens stay in memory.

## Optional second-account checks

Use only accounts and disposable tasks you created for testing. Never share your real password or access token.

1. In a separate browser profile or private window, create a second account. It should not see the first account's project.
2. In your original Owner account, open Team and add the registered test email as Editor. This grants access immediately; no email invitation is sent.
3. Sign out and back in as the Editor to refresh the view. The project should be visible.
4. The Editor should be able to create/edit their own tasks and edit the project description, but should not have project deletion or member-management controls.
5. As Owner, assign a disposable task to the Editor. It should appear under their My tasks and under your Team tasks.
6. As Owner, change the test member to Viewer. The Viewer should be able to read project/team tasks but not create, edit or delete them.
7. Reassign all test tasks from that member to yourself, then remove the member. After the next sign-in, they should no longer see the project. Existing credentials do not bypass revoked membership.

## Existing behavior

Check the rotating illustration and Pause/Resume controls, task search/status filter, status progress updates, edit/delete confirmations and Recent activity. A nonempty project must not be deletable. Permanent deletion is only appropriate for disposable test items.

## Automated checks

Build and verify the frontend first, then check the backend with its environment active:

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

The suite uses separate SQLite databases and test signing secrets. PostgreSQL migration and nonmember isolation have also been verified in a temporary schema that was rolled back. A separate private backup and full isolated PostgreSQL restore drill have also passed.

## Password and human-verification checks

1. Hard-refresh the app, sign out, and select Create account.
2. Try a common password such as `Password123456789!`. The checklist should leave the common-password check unmet and account creation blocked. Use a unique long passphrase or password-manager-generated password instead; do not reuse the example.
3. Confirm the password. Every checklist item must pass; a mismatch must prevent submission. Change a passing password back to a weak one and confirm submission is blocked again.
4. Complete the real Cloudflare human-verification widget yourself. Account creation must remain blocked without a successful check.
5. Create a disposable test account, then sign in and confirm its projects start empty. Existing accounts should still sign in normally.
6. If verification expires or fails, retry it before resubmitting. Do not share passwords, tokens or secret keys.

The automated suites cover missing configuration, invalid/expired/wrong-action/wrong-host tokens, verification outages, password validation and secret-free errors using isolated databases and mocked Cloudflare responses. A real browser challenge still needs the human tester.

## Public issue-import checks

1. Sign in as Owner and choose Import issues on a disposable project.
2. Enter a public `owner/repository` with open issues and preview. Confirm no task is saved yet.
3. Select one issue and confirm import. Check title, details, source link and To do status. With no matching rule, expect Medium priority and your assignment; otherwise compare with the rule outcomes in preview.
4. Preview again: the same issue must show as already imported. Editors and Viewers should not see import controls; the API also enforces this restriction.
5. Invalid repository input, unavailable repositories and expired previews should show useful errors without creating tasks.

Current automated verification: 39 frontend tests and 154 backend tests.

## AI review checks (after private API setup)

1. Sign in as Owner and preview a public repository with open issues. Select one issue.
2. Read the data-sharing notice, then choose Send to OpenAI & draft suggestions. This is a billed API request. No task should appear yet.
3. Compare the draft with Original issue details and the source link. The quoted evidence must be present in the source. Approval must start unchecked.
4. Import without approving AI: original text should be retained, using matching rule actions or Medium priority by default. Use a different disposable issue to test approving the AI summary/priority before final import.
5. Confirm the approved task keeps the original text and link, and Recent activity records the review decision. Preview it again and confirm duplicate import is blocked.
6. Try the flow as Editor/Viewer: import/AI controls must not be available.
7. With AI disabled or unavailable, original imports must continue; no fake AI draft should be displayed.

Automated checks use mocked provider responses and cover owner-only access, project-bound/expired/tampered previews, explicit consent, no saving during generation, approval/default-original behavior, duplicate prevention, safe failures, local request limits, strict output validation and exact source quotes. Live AI quality and billed API access remain a separate manual check.

## CSV bulk-import checks

1. Hard-refresh, sign in as Owner, and choose Import file on a disposable project. Download CSV template.
2. Open/save the template as CSV UTF-8, choose it, then Preview file. Confirm tasks/activity have not changed yet and no rows are selected automatically.
3. Choose Select first ready rows, then Import selected tasks. Check titles, descriptions, priorities, To do status and your assignment.
4. Preview the same file again: identical rows must be disabled as duplicates. No extra tasks should be created by retrying an import.
5. Add a row with a missing title or an unsupported priority. Preview should identify that row and keep it unselectable, while allowing valid rows.
6. Change files after preview: the old preview and selection must disappear. Files over 256 KB should be rejected.
7. As Editor/Viewer, confirm Import file controls are absent and file-import API access is blocked.

Automated tests cover UTF-8/BOM, quoted commas/multiline fields, malformed/binary uploads, size/row/selection limits, unknown columns, per-row errors, readable Unicode preview sizes, owner authorization, tampered/expired/wrong-project and wrong-workflow tokens, repeated/manual duplicates, replay protection, and preservation of duplicate provenance after edits/deletions. Browser testing uses an isolated demo database. No AI credit or external service is needed.

## Import automation acceptance checks

1. Hard-refresh and open Rules on a project you own. Create a rule named Outage triage, keyword `outage`, Look in Title, Priority High, and two checklist items. Leave assignee as Person importing, or choose an existing Editor.
2. Save draft. It must not apply to imports yet, and Enable must remain blocked.
3. Preview an example titled Investigate service outage. Check the High priority, assignee and checklist, then enable. Existing tasks must remain unchanged.
4. Preview a CSV containing that title with Low priority and a second unrelated task. Only the matching row should show the rule actions. Confirm import and inspect tasks/Recent activity.
5. Preview/import the same source again: it must not create another task or apply the checklist twice.
6. Create an import preview, then pause/edit the rule in another tab. Importing the old preview should be blocked until you re-preview. Edited rules become drafts.
7. Test overlapping rules: the earliest-created enabled match wins. Nonmatching rows retain their source values/defaults. A deliberately approved AI priority takes precedence over rule priority.
8. Test an assignee who becomes Viewer before import: assignment must be rejected. Owner/Editor/Viewer restrictions must remain enforced; only Owners manage rules.

Automated checks cover activation gating, revision/expiry/subject binding, first-match priority, assignment eligibility/rechecks, checklist application, source-dedup preservation, audit-once behavior, stale import previews, invalid actions, role/project isolation and additive migration. PostgreSQL migration/idempotency/draft defaults/cascade behavior are tested in a temporary rolled-back schema. Browser checks use demo records.

## Non-AI workflows (migration 003)

Use disposable project records. Open Report & updates, compare totals/statuses with tasks, search the paged task list and download CSV. Only members can access reports/exports. Formula-like task text is escaped for spreadsheets. Counts reflect records, not estimated hours saved.

Import a saved `.eml` message through Import file. Preview must show subject/body without saving, ignore attachments/remote images, and apply enabled rules. Confirm one selected row, then repeat preview to check duplicates. No mailbox is read automatically.

Assign a new task to another Editor; their Notifications should show it, with no other user's notices. Mark it read. Account can disable future assignment notices. Removing membership hides old project notices.

Forgot password and email verification require configured TLS SMTP. After private setup, the human tester requests a link to their own mailbox and completes it. Links expire after 30 minutes and work once. Strong password checks apply to resets; resetting invalidates older sessions. Existing sign-in remains available while verification enforcement is off.

Slack preview is separate from sending. Before any live test, verify the bound project/channel, review the exact text, and explicitly enable sending privately. Check one approved update arrives once. A failed/uncertain attempt must not automatically retry; check the channel first. Automated tests mock external delivery. Real Slack/email/private-GitHub acceptance is pending service setup.

This is a milestone checklist. Full-system acceptance will follow the remaining non-AI workflows and service decisions; paid AI checks remain separate.
