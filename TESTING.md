# Testing project teams

The team update is installed locally. The membership migration was approved and applied after creating and verifying a private database backup. Existing records were verified unchanged. Use the steps below to check it in your browser.

## Owner check

1. Open http://127.0.0.1:8000/ and hard-refresh (Command + Shift + R on macOS), then sign in.
2. Your existing project and task should still be present. Your project card should show Owner.
3. Click Team. Your account should be listed as Owner.
4. Create a test task with Task details and a priority. Confirm its details appear below the title.
5. Switch My tasks to Team tasks and back. With only your account, these lists can be the same.

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

From backend with the environment active:

```sh
python -m pytest -q
python -m pip check
```

The suite uses separate SQLite databases and test signing secrets. PostgreSQL migration and nonmember isolation have also been verified in a temporary schema that was rolled back. These checks do not substitute for a backup or full operational restore drill.
