import hashlib
import time
from datetime import date, datetime, timedelta

import icalendar
import recurring_ical_events

from app.clients.calendar_client import CalendarClient
from app.config import settings
from app.schemas.calendar import CalendarEvent, CalendarResponse
from app.schemas.morning_dust import AgendaEvent, AgendaResponse

# System local timezone, resolved once at import. All event datetimes are
# normalized to be timezone-aware so timed and all-day events compare and
# sort cleanly (mixing aware/naive datetimes raises).
LOCAL_TZ = datetime.now().astimezone().tzinfo


def _aware(value: date | datetime) -> datetime:
    """Coerce an ICS DTSTART/DTEND value to a timezone-aware datetime.
    All-day events arrive as a plain `date` → midnight local."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=LOCAL_TZ)
        return value
    return datetime(value.year, value.month, value.day, tzinfo=LOCAL_TZ)


class CalendarService:
    """Merges one or more iCal feeds into a sorted list of upcoming events.

    Caches per requested window for `ttl_s` so frequent polling from the
    dashboard doesn't re-fetch (and re-parse) every feed each time — Google
    caches the ICS server-side anyway, so sub-TTL freshness is moot. On a
    fetch/parse error the last good result is served with status "error"
    rather than blanking the widget.
    """

    def __init__(self, client: CalendarClient | None = None, ttl_s: float = 300.0) -> None:
        self._client = client or CalendarClient(timeout_s=settings.calendar_timeout_s)
        self._ttl_s = ttl_s
        self._cache: CalendarResponse | None = None
        self._fetched_at: float = 0.0
        # window cache for the morning-dust agenda: {(start, end): (monotonic, events)}
        self._range_cache: dict[tuple[str, str], tuple[float, list[CalendarEvent]]] = {}

    # ---- legacy widget endpoint: next N days, capped ----

    def get_upcoming(self) -> CalendarResponse:
        if not settings.calendar_ics_urls:
            return CalendarResponse(events=[], status="not_configured")

        now = time.monotonic()
        if self._cache is not None and (now - self._fetched_at) < self._ttl_s:
            return self._cache

        try:
            start = date.today()
            events = self._fetch_window(start, start + timedelta(days=settings.calendar_days_ahead))
        except Exception:
            if self._cache is not None:
                return CalendarResponse(events=self._cache.events, status="error")
            return CalendarResponse(events=[], status="error")

        self._cache = CalendarResponse(
            events=events[: settings.calendar_max_events], status="ok"
        )
        self._fetched_at = now
        return self._cache

    # ---- morning-dust agenda: arbitrary window, uncapped, read-only ----

    def get_range(self, start_iso: str, end_iso: str) -> AgendaResponse:
        if not settings.calendar_ics_urls:
            return AgendaResponse(events=[], status="local_only")

        key = (start_iso, end_iso)
        now = time.monotonic()
        hit = self._range_cache.get(key)
        if hit is not None and (now - hit[0]) < self._ttl_s:
            return AgendaResponse(events=[_to_agenda(e) for e in hit[1]], status="ok")

        try:
            events = self._fetch_window(date.fromisoformat(start_iso), date.fromisoformat(end_iso))
        except Exception:
            if hit is not None:
                return AgendaResponse(events=[_to_agenda(e) for e in hit[1]], status="error")
            return AgendaResponse(events=[], status="error")

        self._range_cache[key] = (now, events)
        if len(self._range_cache) > 24:  # keep the map from growing as weeks are paged
            oldest = min(self._range_cache, key=lambda k: self._range_cache[k][0])
            self._range_cache.pop(oldest, None)
        return AgendaResponse(events=[_to_agenda(e) for e in events], status="ok")

    # ---- fetching ----

    def _fetch_window(self, start: date, end: date) -> list[CalendarEvent]:
        drop_before = datetime.now(LOCAL_TZ) if start >= date.today() else None
        collected: list[CalendarEvent] = []
        for url in settings.calendar_ics_urls:
            cal = icalendar.Calendar.from_ical(self._client.fetch_ics(url))
            for comp in recurring_ical_events.of(cal).between(start, end):
                event = self._to_event(comp, drop_before)
                if event is not None:
                    collected.append(event)
        collected.sort(key=lambda e: e.start)
        return collected

    @staticmethod
    def _to_event(comp, drop_before: datetime | None) -> CalendarEvent | None:
        dtstart = comp.get("DTSTART")
        if dtstart is None:
            return None

        raw_start = dtstart.dt
        all_day = not isinstance(raw_start, datetime)
        start = _aware(raw_start)

        dtend = comp.get("DTEND")
        if dtend is not None:
            end = _aware(dtend.dt)
        elif all_day:
            end = start + timedelta(days=1)
        else:
            end = start

        # For "upcoming" views, drop events that have already finished (incl.
        # earlier-today timed events); keep all-day events for today and
        # anything ongoing. Historical windows keep everything.
        if drop_before is not None and end <= drop_before:
            return None

        location = comp.get("LOCATION")
        return CalendarEvent(
            title=str(comp.get("SUMMARY", "(no title)")),
            start=start,
            end=end,
            all_day=all_day,
            location=str(location) if location else None,
        )


def _to_agenda(event: CalendarEvent) -> AgendaEvent:
    """Flatten a feed event into the date + HH:MM shape the dashboard grid uses."""
    stamp = event.start.isoformat()
    digest = hashlib.sha1(f"{stamp}|{event.title}".encode()).hexdigest()[:12]
    return AgendaEvent(
        id=f"ics:{digest}",
        title=event.title,
        date=event.start.date().isoformat(),
        time="" if event.all_day else event.start.strftime("%H:%M"),
        location=event.location or "",
        source="ics",
        editable=False,
    )


# Module-level singleton so the TTL cache is shared across requests.
_calendar_service = CalendarService()


def get_calendar_service() -> CalendarService:
    return _calendar_service
