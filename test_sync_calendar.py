from sync_calendar import OutlookEvent, TECClient


def test_tec_payload_uses_content_field():
    event = OutlookEvent(
        ical_uid="uid-1",
        subject="Test event",
        start="2026-08-14T10:00:00",
        end="2026-08-14T11:00:00",
        timezone="UTC",
        location="Test venue",
        description_html="<p>Test description</p>",
    )

    payload = TECClient._to_payload(event)

    assert payload["content"] == "<p>Test description</p>"
    assert "description" not in payload
