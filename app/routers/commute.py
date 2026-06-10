from fastapi import APIRouter, Depends

from app.schemas.commute import CommuteResponse
from app.services.commute_service import CommuteService, get_commute_service

router = APIRouter()


@router.get("", response_model=CommuteResponse)
def get_commute(
    service: CommuteService = Depends(get_commute_service),
) -> CommuteResponse:
    return service.get_cached()


@router.post("/refresh", response_model=CommuteResponse)
def refresh_commute(
    service: CommuteService = Depends(get_commute_service),
) -> CommuteResponse:
    return service.refresh()
