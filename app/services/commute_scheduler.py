import asyncio
import logging
from datetime import datetime, timedelta

from app.config import settings
from app.services.commute_service import CommuteService

log = logging.getLogger(__name__)


def _seconds_until_next(hour: int, now: datetime | None = None) -> float:
    now = now or datetime.now()
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


async def run_daily_commute_refresh(service: CommuteService) -> None:
    """Refresh once on startup, then every day at the configured hour.

    Single-worker design — if you ever run multiple uvicorn workers, each
    would run this loop. For a kiosk that's not a concern.
    """
    try:
        await asyncio.to_thread(service.refresh)
        log.info("commute: initial refresh complete")
    except Exception:
        log.exception("commute: initial refresh failed")

    while True:
        delay = _seconds_until_next(settings.commute_daily_refresh_hour)
        log.info("commute: next refresh in %.0fs", delay)
        await asyncio.sleep(delay)
        try:
            await asyncio.to_thread(service.refresh)
            log.info("commute: daily refresh complete")
        except Exception:
            log.exception("commute: daily refresh failed")
