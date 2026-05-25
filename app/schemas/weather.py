from pydantic import BaseModel


class WeatherResponse(BaseModel):
    location: str
    temperature_c: float
    condition: str
