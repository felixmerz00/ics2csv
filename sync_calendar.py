#!/usr/bin/env python3
"""
sync_calendar.py

Syncs events from a Microsoft Outlook / Microsoft 365 calendar into a
WordPress site running "The Events Calendar" plugin.

Flow:
  1. Authenticate to Microsoft Graph (client credentials flow) and pull all
     future events from the target mailbox's calendar.
  2. Load the local state/event_mapping.json file, which maps each Outlook
     event's stable iCalUId -> { wp_event_id, content_hash }.
  3. Diff Outlook events against the mapping:
       - New Outlook events (not in mapping)         -> CREATE in WordPress
       - Existing events whose content hash changed   -> UPDATE in WordPress
       - Mapping entries with no matching Outlook evt -> DELETE from WordPress
  4. Save the updated mapping back to disk.

Every event is processed inside its own try/except so a single bad event
can't abort the whole run. A summary is logged (and also written to
GITHUB_STEP_SUMMARY when running inside GitHub Actions).

Required environment variables:
  TENANT_ID, CLIENT_ID, CLIENT_SECRET   - Azure AD app registration (Graph API)
  WP_URL, WP_USERNAME, WP_APP_PASSWORD  - WordPress REST API (Application Password)

Optional environment variables:
  OUTLOOK_USER_ID   - mailbox to read (UPN or object id). Defaults to "me",
                       but client-credentials flow has no signed-in user, so
                       for app-only auth you MUST set this to a real mailbox,
                       e.g. "calendar@yourcompany.com".
  MAPPING_FILE       - path to the JSON state file (default: state/event_mapping.json)
  MAX_MONTHS_AHEAD   - how far into the future to sync (default: 15)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

import requests
from dateutil.relativedelta import relativedelta


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("sync_calendar")

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPE = "https://graph.microsoft.com/.default"  # app-only: scope comes from granted app permissions (Calendars.Read)

MAPPING_FILE = os.environ.get("MAPPING_FILE", "state/event_mapping.json")
MAX_MONTHS_AHEAD = int(os.environ.get("MAX_MONTHS_AHEAD", "15"))
OUTLOOK_USER_ID = os.environ.get("OUTLOOK_USER_ID", "me")

REQUEST_TIMEOUT = 30  # seconds

LOCAL_TZ = ZoneInfo("Europe/Zurich")  # CET/CEST, DST-aware


def env_or_die(name: str) -> str:
    """Fetch a required environment variable or exit with a clear error."""
    value = os.environ.get(name)
    if not value:
        log.error("Missing required environment variable: %s", name)
        sys.exit(1)
    return value


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------

@dataclass
class OutlookEvent:
    """Normalized representation of the Outlook fields we care about."""
    ical_uid: str
    subject: str
    start: str          # ISO 8601, includes timezone offset
    end: str             # ISO 8601, includes timezone offset
    all_day: bool
    location: str
    description_html: str

    def content_hash(self) -> str:
        """Stable hash of the fields that matter for detecting changes."""
        payload = json.dumps(
            {
                "subject": self.subject,
                "start": self.start,
                "end": self.end,
                "all_day": self.all_day,
                "location": self.location,
                "description_html": self.description_html,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Microsoft Graph client
# --------------------------------------------------------------------------

class GraphClient:
    """Minimal Microsoft Graph client using OAuth2 client-credentials flow."""

    def __init__(self, tenant_id: str, client_id: str, client_secret: str):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: Optional[str] = None
        self._token_expiry: datetime = datetime.min.replace(tzinfo=LOCAL_TZ)

    def _get_token(self) -> str:
        """Return a cached access token, refreshing it if expired/near expiry."""
        if self._token and datetime.now(LOCAL_TZ) < self._token_expiry:
            return self._token

        url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": GRAPH_SCOPE,
        }
        resp = requests.post(url, data=data, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        payload = resp.json()

        self._token = payload["access_token"]
        expires_in = int(payload.get("expires_in", 3600))
        # Refresh a little early to avoid edge-of-expiry failures mid-run.
        self._token_expiry = datetime.now(LOCAL_TZ) + timedelta(seconds=expires_in - 60)
        return self._token

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json",
            "Prefer": 'outlook.timezone="Romance Standard Time"',
        }

    def fetch_future_events(self, user_id: str, months_ahead: int) -> list[OutlookEvent]:
        """
        Fetch all events for `user_id` from now through `months_ahead` months
        out, using the calendarView endpoint (which expands recurring events
        into their individual occurrences).
        """
        al_calendar_id = "AAMkADk5M2EwMjk5LTJjMjctNDA1Ny04YjU2LWZiNDM2ZjVmMWE3OQBGAAAAAABu7tmZD2SnSrHoabtBfmdUBwC8CfXxCB4iSqPeKEOALkJFAAAAAAEGAAC8CfXxCB4iSqPeKEOALkJFAABpsmohAAA="
        # --- TEMP TEST OVERRIDE ---
        # now = datetime(2026, 8, 18, 0, 0, 0, tzinfo=LOCAL_TZ)
        # end_window = datetime(2026, 8, 19, 0, 0, 0, tzinfo=LOCAL_TZ)
        end_window = datetime(2026, 9, 6, 0, 0, 0, tzinfo=LOCAL_TZ)
        now = datetime.now(LOCAL_TZ)
        # end_window = now + relativedelta(months=months_ahead)

        start_str = now.strftime("%Y-%m-%dT%H:%M:%S")
        end_str = end_window.strftime("%Y-%m-%dT%H:%M:%S")

        url = (
            f"{GRAPH_BASE}/users/{user_id}/calendars/{al_calendar_id}/calendarView"
        )
        params = {
            "startDateTime": start_str,
            "endDateTime": end_str,
            "$select": "iCalUId,subject,start,end,isAllDay,location,bodyPreview,body",
            "$top": "100",
            "$orderby": "start/dateTime",
        }

        events: list[OutlookEvent] = []
        while url:
            resp = requests.get(url, headers=self._headers(), params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            payload = resp.json()

            for raw in payload.get("value", []):
                try:
                    events.append(self._parse_event(raw))
                except Exception:
                    log.exception("Failed to parse Outlook event: %s", raw.get("iCalUId", "<unknown>"))

            # Follow pagination if present; params are already baked into nextLink.
            url = payload.get("@odata.nextLink")
            params = None

        return events

    @staticmethod
    def _parse_event(raw: dict) -> OutlookEvent:
        start = raw.get("start", {})
        end = raw.get("end", {})
        all_day = raw.get("isAllDay", False)
        location = (raw.get("location") or {}).get("displayName", "") or ""
        body = raw.get("body") or {}
        description_html = body.get("content", "") if body.get("contentType") == "html" else raw.get("bodyPreview", "")

        end_datetime_str = end.get("dateTime", "")
        if all_day and end_datetime_str:
            # Graph's end.dateTime for all-day events is exclusive (midnight
            # of the day *after* the event ends). TEC expects an inclusive
            # end date, so shift it back by one day.
            end_dt = datetime.fromisoformat(end_datetime_str)
            end_dt -= timedelta(days=1)
            end_datetime_str = end_dt.isoformat()

        return OutlookEvent(
            ical_uid=raw["iCalUId"],
            subject=raw.get("subject", "(No subject)"),
            start=start.get("dateTime", ""),
            end=end_datetime_str,
            all_day=all_day,
            location=location,
            description_html=description_html or "",
        )


# --------------------------------------------------------------------------
# WordPress / The Events Calendar client
# --------------------------------------------------------------------------

class TECClient:
    """Client for The Events Calendar REST API on a WordPress site."""

    def __init__(self, base_url: str, username: str, app_password: str):
        self.base_url = base_url.rstrip("/")
        self.auth = (username, app_password)

    @property
    def events_url(self) -> str:
        return f"{self.base_url}/wp-json/tribe/events/v1/events"

    def create_event(self, event: OutlookEvent) -> int:
        """POST a new event to WordPress. Returns the new WP event ID."""
        resp = requests.post(
            self.events_url,
            auth=self.auth,
            json=self._to_payload(event),
            timeout=REQUEST_TIMEOUT,
        )
        if not resp.ok:
            log.error("Tribe API error %s: %s", resp.status_code, resp.text)
        resp.raise_for_status()
        return resp.json()["id"]

    def update_event(self, wp_event_id: int, event: OutlookEvent) -> None:
        """PUT/update an existing WordPress event."""
        url = f"{self.events_url}/{wp_event_id}"
        resp = requests.put(
            url,
            auth=self.auth,
            json=self._to_payload(event),
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()

    def delete_event(self, wp_event_id: int) -> None:
        """DELETE a WordPress event. Treats 'already gone' (404) as success."""
        url = f"{self.events_url}/{wp_event_id}"
        resp = requests.delete(url, auth=self.auth, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 404:
            log.warning("WP event %s already deleted; skipping.", wp_event_id)
            return
        resp.raise_for_status()

    @staticmethod
    def _to_payload(event: OutlookEvent) -> dict:
        """
        Map our normalized OutlookEvent to The Events Calendar's expected
        request body. TEC expects local start/end date strings plus an
        explicit timezone field, so we strip the offset from the ISO string
        (Graph returns naive-looking local time when a timeZone is given)
        and pass timezone separately.
        """
        payload = {
            "title": event.subject,
            "start_date": _to_tec_datetime(event.start),
            "end_date": _to_tec_datetime(event.end),
            "all_day": event.all_day,
            "timezone": "Europe/Zurich",
            "venue": {"venue": event.location} if event.location else {},
            # Custom field to store the Outlook UID on the WP side too, handy
            # for manual reconciliation / debugging via the WP admin UI.
            "meta": {"_outlook_ical_uid": event.ical_uid},
        }
        if event.description_html:
            payload["description"] = event.description_html
        return payload


def _to_tec_datetime(iso_dt: str) -> str:
    """Convert a Graph ISO datetime (possibly with fractional seconds) into
    the 'YYYY-MM-DD HH:MM:SS' format TEC's REST API expects."""
    if not iso_dt:
        return ""
    # Graph datetimes look like '2026-08-09T14:00:00.0000000'
    cleaned = iso_dt.split(".")[0]
    dt = datetime.fromisoformat(cleaned)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


# --------------------------------------------------------------------------
# State / mapping file
# --------------------------------------------------------------------------

def load_mapping(path: str) -> dict[str, dict]:
    """Load the mapping file, tolerating a missing/empty file on first run."""
    if not os.path.exists(path):
        log.info("No existing mapping file at %s; starting fresh.", path)
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        log.exception("Mapping file at %s is unreadable; starting fresh.", path)
        return {}


def save_mapping(path: str, mapping: dict[str, dict]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2, sort_keys=True)
        f.write("\n")


# --------------------------------------------------------------------------
# Sync orchestration
# --------------------------------------------------------------------------

@dataclass
class SyncSummary:
    created: list[str] = None
    updated: list[str] = None
    deleted: list[str] = None
    failed: list[str] = None

    def __post_init__(self):
        self.created = self.created or []
        self.updated = self.updated or []
        self.deleted = self.deleted or []
        self.failed = self.failed or []

    def log_report(self) -> None:
        log.info(
            "Sync complete: %d created, %d updated, %d deleted, %d failed",
            len(self.created), len(self.updated), len(self.deleted), len(self.failed),
        )
        for label, items in (
            ("Created", self.created),
            ("Updated", self.updated),
            ("Deleted", self.deleted),
            ("Failed", self.failed),
        ):
            for item in items:
                log.info("  %s: %s", label, item)

    def write_github_summary(self) -> None:
        """If running in GitHub Actions, append a nice markdown summary."""
        summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        if not summary_path:
            return
        lines = [
            "## Calendar Sync Summary",
            f"- Created: {len(self.created)}",
            f"- Updated: {len(self.updated)}",
            f"- Deleted: {len(self.deleted)}",
            f"- Failed: {len(self.failed)}",
        ]
        if self.failed:
            lines.append("\n### Failures")
            lines += [f"- {item}" for item in self.failed]
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


def run_sync() -> SyncSummary:
    # --- Load credentials ---
    tenant_id = env_or_die("TENANT_ID")
    client_id = env_or_die("CLIENT_ID")
    client_secret = env_or_die("CLIENT_SECRET")
    wp_url = env_or_die("WP_URL")
    wp_username = env_or_die("WP_USERNAME")
    wp_app_password = env_or_die("WP_APP_PASSWORD")

    graph = GraphClient(tenant_id, client_id, client_secret)
    tec = TECClient(wp_url, wp_username, wp_app_password)
    summary = SyncSummary()

    # --- Fetch source data ---
    log.info("Fetching future Outlook events (up to %s months ahead)...", MAX_MONTHS_AHEAD)
    outlook_events = graph.fetch_future_events(OUTLOOK_USER_ID, MAX_MONTHS_AHEAD)
    log.info("Fetched %d Outlook events.", len(outlook_events))

    outlook_events_by_uid = {e.ical_uid: e for e in outlook_events}

    mapping = load_mapping(MAPPING_FILE)

    # --- Create / update ---
    for uid, event in outlook_events_by_uid.items():
        try:
            new_hash = event.content_hash()
            entry = mapping.get(uid)

            if entry is None:
                wp_id = tec.create_event(event)
                mapping[uid] = {"wp_event_id": wp_id, "content_hash": new_hash}
                summary.created.append(f"{event.subject} ({uid})")
                log.info("Created WP event %s for '%s'", wp_id, event.subject)

            elif entry.get("content_hash") != new_hash:
                tec.update_event(entry["wp_event_id"], event)
                entry["content_hash"] = new_hash    # entry is a reference
                summary.updated.append(f"{event.subject} ({uid})")
                log.info("Updated WP event %s for '%s'", entry["wp_event_id"], event.subject)

            # else: unchanged, nothing to do

        except Exception as exc:
            log.exception("Failed to sync event '%s' (%s)", event.subject, uid)
            summary.failed.append(f"{event.subject} ({uid}): {exc}")

    # --- Delete: mapping entries with no corresponding Outlook event ---
    for uid in list(mapping.keys()):
        if uid in outlook_events_by_uid:
            continue
        entry = mapping[uid]
        try:
            tec.delete_event(entry["wp_event_id"])
            summary.deleted.append(f"{uid} (WP id {entry['wp_event_id']})")
            log.info("Deleted WP event %s (Outlook event %s no longer exists)", entry["wp_event_id"], uid)
            del mapping[uid]
        except Exception as exc:
            log.exception("Failed to delete WP event for stale Outlook uid %s", uid)
            summary.failed.append(f"delete {uid}: {exc}")
            # Leave the mapping entry in place so we retry deletion next run.

    save_mapping(MAPPING_FILE, mapping)
    return summary


def main() -> None:
    summary = run_sync()
    summary.log_report()
    summary.write_github_summary()
    # Exit non-zero if anything failed, so the Actions run is flagged red.
    if summary.failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
