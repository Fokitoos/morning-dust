from fastapi import APIRouter

from app.schemas.commute import CommuteResponse

router = APIRouter()


@router.get("", response_model=CommuteResponse)
def get_commute() -> CommuteResponse:
    return CommuteResponse(
        origin="",
        destination="",
        duration_minutes=0,
        traffic="unknown",
    )
