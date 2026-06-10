from datetime import datetime

from pydantic import BaseModel


class CalendarEvent(BaseModel):
    title: str
    start: datetime
    end: datetime | None = None
    all_day: bool = False
    location: str | None = None


class CalendarResponse(BaseModel):
    events: list[CalendarEvent]
    # ok | not_configured | error
    status: str