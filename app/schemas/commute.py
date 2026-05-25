from pydantic import BaseModel


class CommuteResponse(BaseModel):
    origin: str
    destination: str
    duration_minutes: int
    traffic: str
