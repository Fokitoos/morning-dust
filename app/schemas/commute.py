from datetime import datetime

from pydantic import BaseModel


class CommuteResponse(BaseModel):
    origin: str
    destination: str
    duration_minutes: int | None = None
    typical_duration_minutes: int | None = None
    traffic_delay_minutes: int | None = None
    distance_km: float | None = None
    last_updated: datetime | None = None
    status: str  # "ok" | "not_configured" | "no_api_key" | "error" | "stale"
