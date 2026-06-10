from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.clients.calendar_client import CalendarClient
from app.config import settings
from app.main import create_app
from app.services.calendar_service import CalendarService, get_calendar_service

NOW = datetime.now(timezone.utc)


def _utc(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%SZ")


def _ymd(d: date) -> str:
    return d.strftime("%Y%m%d")


def _vevent(uid, summary, *, dtstart, dtend=None, rrule=None, all_day=False, location=None):
    lines = ["BEGIN:VEVENT", f"UID:{uid}", f"SUMMARY:{summary}"]
    if all_day:
        lines.append(f"DTSTART;VALUE=DATE:{dtstart}")
        if dtend:
            lines.append(f"DTEND;VALUE=DATE:{dtend}")
    else:
        lines.append(f"DTSTART:{dtstart}")
        if dtend:
            lines.append(f"DTEND:{dtend}")
    if rrule:
        lines.append(f"RRULE:{rrule}")
    if location:
        lines.append(f"LOCATION:{location}")
    lines.append("END:VEVENT")
    return "\r\n".join(lines)


def _ics(*vevents: str) -> str:
    body = "\r\n".join(vevents)
    return (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//test//EN\r\n"
        f"{body}\r\n"
        "END:VCALENDAR\r\n"
    )


class FakeCalendarClient(CalendarClient):
    def __init__(self, ics_by_url: dict[str, str], raise_exc: Exception | None = None) -> None:
        self._map = ics_by_url
        self._raise = raise_exc
        self.calls = 0

    def fetch_ics(self, url: str) -> str:
        self.calls += 1
        if self._raise:
            raise self._raise
        return self._map[url]


@pytest.fixture(autouse=True)
def _cal_settings(monkeypatch):
    monkeypatch.setattr(settings, "calendar_ics_urls", ["u1"], raising=False)
    monkeypatch.setattr(settings, "calendar_days_ahead", 7, raising=False)
    monkeypatch.setattr(settings, "calendar_max_events", 8, raising=False)


def _service(ics: str, **kwargs) -> CalendarService:
    client = FakeCalendarClient({"u1": ics}, **kwargs)
    return CalendarService(client=client, ttl_s=0.0)


def test_not_configured_when_no_urls(monkeypatch):
    monkeypatch.setattr(settings, "calendar_ics_urls", [], raising=False)
    resp = _service(_ics()).get_upcoming()
    assert resp.status == "not_configured"
    assert resp.events == []


def test_parses_timed_event():
    start = (NOW + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    ics = _ics(_vevent("1", "Standup", dtstart=_utc(start),
                       dtend=_utc(start + timedelta(minutes=15)), location="Room 1"))
    resp = _service(ics).get_upcoming()
    assert resp.status == "ok"
    assert len(resp.events) == 1
    ev = resp.events[0]
    assert ev.title == "Standup"
    assert ev.all_day is False
    assert ev.location == "Room 1"


def test_all_day_event():
    day = date.today() + timedelta(days=2)
    ics = _ics(_vevent("1", "Holiday", dtstart=_ymd(day),
                       dtend=_ymd(day + timedelta(days=1)), all_day=True))
    resp = _service(ics).get_upcoming()
    assert len(resp.events) == 1
    assert resp.events[0].all_day is True


def test_past_event_excluded():
    past = _vevent("old", "Done", dtstart=_utc(NOW - timedelta(hours=2)),
                   dtend=_utc(NOW - timedelta(hours=1)))
    future_start = (NOW + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    future = _vevent("new", "Later", dtstart=_utc(future_start),
                     dtend=_utc(future_start + timedelta(hours=1)))
    resp = _service(_ics(past, future)).get_upcoming()
    titles = [e.title for e in resp.events]
    assert "Later" in titles
    assert "Done" not in titles


def test_recurring_event_expanded():
    start = (NOW + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    ics = _ics(_vevent("r", "Daily Sync", dtstart=_utc(start),
                       dtend=_utc(start + timedelta(minutes=30)),
                       rrule="FREQ=DAILY;COUNT=3"))
    resp = _service(ics).get_upcoming()
    assert len(resp.events) == 3
    assert all(e.title == "Daily Sync" for e in resp.events)


def test_events_sorted_and_capped(monkeypatch):
    monkeypatch.setattr(settings, "calendar_max_events", 2, raising=False)
    base = (NOW + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
    vevents = [
        _vevent(str(i), f"E{i}", dtstart=_utc(base + timedelta(hours=3 - i)),
                dtend=_utc(base + timedelta(hours=4 - i)))
        for i in range(3)
    ]
    resp = _service(_ics(*vevents)).get_upcoming()
    assert len(resp.events) == 2
    assert resp.events[0].start <= resp.events[1].start


def test_merges_multiple_feeds(monkeypatch):
    monkeypatch.setattr(settings, "calendar_ics_urls", ["u1", "u2"], raising=False)
    start = (NOW + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    a = _ics(_vevent("a", "From A", dtstart=_utc(start), dtend=_utc(start + timedelta(hours=1))))
    b = _ics(_vevent("b", "From B", dtstart=_utc(start + timedelta(hours=2)),
                     dtend=_utc(start + timedelta(hours=3))))
    client = FakeCalendarClient({"u1": a, "u2": b})
    resp = CalendarService(client=client, ttl_s=0.0).get_upcoming()
    titles = {e.title for e in resp.events}
    assert titles == {"From A", "From B"}


def test_error_without_cache_returns_empty():
    svc = _service(_ics(), raise_exc=RuntimeError("network down"))
    resp = svc.get_upcoming()
    assert resp.status == "error"
    assert resp.events == []


def test_error_serves_stale_cache():
    start = (NOW + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    ics = _ics(_vevent("1", "Cached", dtstart=_utc(start),
                       dtend=_utc(start + timedelta(hours=1))))
    client = FakeCalendarClient({"u1": ics})
    svc = CalendarService(client=client, ttl_s=0.0)
    assert svc.get_upcoming().status == "ok"

    client._raise = RuntimeError("boom")
    resp = svc.get_upcoming()
    assert resp.status == "error"
    assert [e.title for e in resp.events] == ["Cached"]  # stale data retained


def test_endpoint_returns_events():
    start = (NOW + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    ics = _ics(_vevent("1", "Meeting", dtstart=_utc(start),
                       dtend=_utc(start + timedelta(hours=1))))
    svc = _service(ics)
    app = create_app()
    app.dependency_overrides[get_calendar_service] = lambda: svc
    with TestClient(app) as c:
        body = c.get("/api/calendar").json()
    assert body["status"] == "ok"
    assert body["events"][0]["title"] == "Meeting"
