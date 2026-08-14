# Outlook → WordPress "The Events Calendar" Sync

Daily one-way sync of events from a Microsoft 365 / Outlook calendar into a
WordPress site running [The Events Calendar](https://theeventscalendar.com/)
plugin, run automatically via GitHub Actions.

## How it works

1. GitHub Actions runs `sync_calendar.py` daily (and on manual trigger).
2. The script authenticates to Microsoft Graph and pulls all future events
   (up to 15 months out) from a mailbox's calendar.
3. It compares them against `state/event_mapping.json`, which maps each
   Outlook event's `iCalUId` → `{ wp_event_id, content_hash }`.
4. New events are created in WordPress, changed events are updated, and
   events removed from Outlook are deleted from WordPress.
5. The updated mapping file is committed back to the repo so state persists
   between runs.

## 1. Azure AD app registration (Microsoft Graph access)

1. Go to [portal.azure.com](https://portal.azure.com) → **Azure Active
   Directory / Microsoft Entra ID** → **App registrations** → **New
   registration**.
2. Name it (e.g. `outlook-wp-calendar-sync`), leave redirect URI blank,
   click **Register**.
3. Note the **Application (client) ID** and **Directory (tenant) ID** shown
   on the Overview page.
4. Go to **Certificates & secrets** → **New client secret**. Copy the
   secret **value** immediately (it's only shown once).
5. Go to **API permissions** → **Add a permission** → **Microsoft Graph** →
   **Application permissions** → search for `Calendars.Read` → add it.
6. Click **Grant admin consent** for your tenant (requires an admin).
   This is required — application (unattended) permissions don't work
   without admin consent.
7. Decide which mailbox to sync. Since this uses app-only (client
   credentials) auth, there's no signed-in user, so you must sync a
   specific mailbox rather than "me". Set `OUTLOOK_USER_ID` to that
   mailbox's UPN, e.g. `calendar@yourcompany.com`. If your organization
   restricts which mailboxes an app can access, scope it via an
   [application access policy](https://learn.microsoft.com/en-us/graph/auth-limit-mailbox-access).

## 2. WordPress Application Password

1. Make sure The Events Calendar plugin is installed and its REST API is
   enabled (it is by default).
2. In WordPress admin, go to **Users → Profile** (for the account that will
   run the sync — it needs permission to create/edit/delete events, e.g.
   an Editor or Administrator).
3. Scroll to **Application Passwords**, enter a name (e.g.
   `calendar-sync`), click **Add New Application Password**.
4. Copy the generated password (spaces included, e.g. `abcd 1234 efgh
   5678`) — it's only shown once.
5. Your site must be served over HTTPS for Application Passwords to work
   by default.

## 3. GitHub repository secrets

In your repo: **Settings → Secrets and variables → Actions → New repository
secret**. Add:

| Secret name         | Value                                                    |
|----------------------|-----------------------------------------------------------|
| `TENANT_ID`          | Azure AD Directory (tenant) ID                            |
| `CLIENT_ID`           | Azure AD Application (client) ID                          |
| `CLIENT_SECRET`      | Azure AD client secret value                               |
| `OUTLOOK_USER_ID`    | Mailbox to sync, e.g. `calendar@yourcompany.com`           |
| `WP_URL`              | Site base URL, e.g. `https://example.com` (no trailing `/`)|
| `WP_USERNAME`        | WordPress username tied to the Application Password        |
| `WP_APP_PASSWORD`    | The generated Application Password                         |

## 4. Enable Actions write permissions

The workflow commits the updated state file back to the repo, so under
**Settings → Actions → General → Workflow permissions**, select **Read and
write permissions** (or rely on the `permissions: contents: write` already
set in the workflow file, which is usually sufficient on its own).

## 5. Running it

- It runs automatically every day at 05:00 UTC (`.github/workflows/sync.yml`
  — edit the `cron` line to change the schedule).
- To run manually: **Actions tab → Sync Outlook Calendar to WordPress →
  Run workflow**.
- Logs (including a created/updated/deleted/failed summary) appear in the
  Actions run output and in the run's Job Summary.

## The state file

`state/event_mapping.json` looks like:

```json
{
  "040000008200E00074C5B7101A82E00...": {
    "wp_event_id": 1234,
    "content_hash": "9f2c1a...e7"
  }
}
```

- **Key**: the Outlook event's `iCalUId` — stable across edits, so it
  reliably identifies the "same" event over time (including recurring
  event occurrences).
- `wp_event_id`: the corresponding post ID of the event in WordPress, used
  for updates/deletes.
- `content_hash`: a SHA-256 hash of the fields that matter (title, start,
  end, timezone, location, description). If Outlook's copy changes, the
  hash won't match and the WordPress event gets updated.

**Do not hand-edit this file** while the workflow might run — the workflow
overwrites it each run based on what it finds. If you need to force a
full re-sync, you can reset it to `{}`, but note this will create
duplicate events in WordPress for anything already synced (the script has
no way to know an event was already created without the mapping).

## Local testing

```bash
pip install -r requirements.txt

export TENANT_ID=...
export CLIENT_ID=...
export CLIENT_SECRET=...
export OUTLOOK_USER_ID=calendar@yourcompany.com
export WP_URL=https://example.com
export WP_USERNAME=...
export WP_APP_PASSWORD=...

python sync_calendar.py
```

## Notes & limitations

- This is a **one-way** sync (Outlook → WordPress). Edits made directly in
  WordPress will be overwritten on the next run if the Outlook side hasn't
  also changed to match, since the script only compares Outlook's content
  hash against what it last pushed.
- Recurring events are expanded into individual occurrences by Graph's
  `calendarView` endpoint, so each occurrence becomes its own WordPress
  event.
- The sync window is capped at 15 months ahead (`MAX_MONTHS_AHEAD` env var)
  to keep runs fast and avoid syncing far-future placeholder events.
- If a WordPress event is deleted manually outside of this workflow, the
  script will recreate it on the next run (since Outlook's copy still
  exists and the mapping's `wp_event_id` will 404 on update — you may want
  to add extra handling for that edge case if it comes up often).
