from fastapi import APIRouter

from app.schemas.weather import WeatherResponse

router = APIRouter()


@router.get("", response_model=WeatherResponse)
def get_weather() -> WeatherResponse:
    return WeatherResponse(
        location="Unknown",
        temperature_c=0.0,
        condition="unknown",
    )
