from fastapi import APIRouter, Depends

from app.schemas.calendar import CalendarResponse
from app.services.calendar_service import CalendarService, get_calendar_service

router = APIRouter()


@router.get("", response_model=CalendarResponse)
def get_calendar(
    service: CalendarService = Depends(get_calendar_service),
) -> CalendarResponse:
    return service.get_upcoming()
