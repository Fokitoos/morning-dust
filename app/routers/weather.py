from fastapi import APIRouter, Depends

from app.schemas.weather import WeatherResponse
from app.services.weather_service import WeatherService, get_weather_service

router = APIRouter()


@router.get("", response_model=WeatherResponse)
def get_weather(
    service: WeatherService = Depends(get_weather_service),
) -> WeatherResponse:
    return service.get_current()
