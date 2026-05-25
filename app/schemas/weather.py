from pydantic import BaseModel


class WeatherResponse(BaseModel):
    location: str
    temperature_c: float
    temperature_min_c: float | None = None
    temperature_max_c: float | None = None
    condition: str
