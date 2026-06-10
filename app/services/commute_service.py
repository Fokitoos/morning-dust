from datetime import datetime

from app.clients.commute_client import CommuteClient
from app.config import settings
from app.schemas.commute import CommuteResponse


def _build_client() -> CommuteClient | None:
    """Construct a client from current settings. Re-reads on every call so
    config changes (.env edits + restart) take effect without needing to
    rebuild the singleton service."""
    if not settings.tomtom_api_key:
        return None
    return CommuteClient(
        api_key=settings.tomtom_api_key,
        profile=settings.commute_profile,
        timeout_s=settings.commute_timeout_s,
    )


class CommuteService:
    """Holds the latest commute snapshot in memory. Background scheduler
    and the /refresh endpoint both call refresh(); the GET endpoint just
    reads _last."""

    def __init__(self, client_factory=_build_client) -> None:
        self._client_factory = client_factory
        self._last: CommuteResponse | None = None

    def _coords_set(self) -> bool:
        return all(
            v is not None
            for v in (
                settings.commute_origin_lat,
                settings.commute_origin_lon,
                settings.commute_destination_lat,
                settings.commute_destination_lon,
            )
        )

    def get_cached(self) -> CommuteResponse:
        if self._last is not None:
            return self._last
        return CommuteResponse(
            origin=settings.commute_origin_name,
            destination=settings.commute_destination_name,
            status=self._unready_status() or "stale",
        )

    def _unready_status(self) -> str | None:
        if not settings.tomtom_api_key:
            return "no_api_key"
        if not self._coords_set():
            return "not_configured"
        return None

    def refresh(self) -> CommuteResponse:
        unready = self._unready_status()
        if unready:
            self._last = CommuteResponse(
                origin=settings.commute_origin_name,
                destination=settings.commute_destination_name,
                status=unready,
            )
            return self._last

        client = self._client_factory()
        try:
            assert client is not None
            origin_lat = settings.commute_origin_lat
            origin_lon = settings.commute_origin_lon
            dest_lat = settings.commute_destination_lat
            dest_lon = settings.commute_destination_lon
            assert origin_lat is not None and origin_lon is not None
            assert dest_lat is not None and dest_lon is not None
            data = client.fetch_route(origin_lat, origin_lon, dest_lat, dest_lon)
            summary = ((data.get("routes") or [{}])[0]).get("summary", {})
            live_s = float(summary.get("travelTimeInSeconds", 0.0))
            typical_s = float(summary.get("noTrafficTravelTimeInSeconds", live_s))
            delay_s = float(summary.get("trafficDelayInSeconds", live_s - typical_s))
            distance_m = float(summary.get("lengthInMeters", 0.0))
            self._last = CommuteResponse(
                origin=settings.commute_origin_name,
                destination=settings.commute_destination_name,
                duration_minutes=int(round(live_s / 60)),
                typical_duration_minutes=int(round(typical_s / 60)),
                traffic_delay_minutes=int(round(delay_s / 60)),
                distance_km=round(distance_m / 1000, 1),
                last_updated=datetime.now(),
                status="ok",
            )
        except Exception:
            self._last = CommuteResponse(
                origin=settings.commute_origin_name,
                destination=settings.commute_destination_name,
                last_updated=self._last.last_updated if self._last else None,
                duration_minutes=self._last.duration_minutes if self._last else None,
                typical_duration_minutes=(
                    self._last.typical_duration_minutes if self._last else None
                ),
                traffic_delay_minutes=(
                    self._last.traffic_delay_minutes if self._last else None
                ),
                distance_km=self._last.distance_km if self._last else None,
                status="error",
            )
        return self._last


# Module-level singleton — shared between scheduler and HTTP handlers so
# the in-memory cache stays consistent.
_commute_service = CommuteService()


def get_commute_service() -> CommuteService:
    return _commute_service
