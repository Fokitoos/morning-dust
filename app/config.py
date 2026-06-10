import re
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

HOME_LAT = 52.021414448256394
HOME_LON = 5.067054724580616

WORK_LAT = 52.304560 
WORK_LON = 5.243552


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="MORNING_DUST_", extra="ignore")

    app_name: str = "morning-dust"
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    weather_lat: float = HOME_LAT
    weather_lon: float = HOME_LON
    weather_location_name: str = "Nieuwegein"
    weather_timeout_s: float = 5.0

    todo_file_path: str = "data/todos.json"

    commute_origin_lat: float | None = HOME_LAT
    commute_origin_lon: float | None = HOME_LON
    commute_destination_lat: float | None = WORK_LAT
    commute_destination_lon: float | None = WORK_LON
    commute_origin_name: str = "Home"
    commute_destination_name: str = "Work"
    commute_profile: str = "car"  # TomTom travelMode: car | bicycle | pedestrian | motorcycle | truck
    commute_timeout_s: float = 10.0
    commute_daily_refresh_hour: int = 7
    tomtom_api_key: str | None = None

    # Google Calendar via private iCal (.ics) feeds. Set one or more secret
    # URLs (comma- or whitespace-separated in .env). Read-only, no OAuth.
    # NoDecode: keep pydantic-settings from JSON-decoding the env value so the
    # validator below can accept a plain delimited string of URLs.
    calendar_ics_urls: Annotated[list[str], NoDecode] = []
    calendar_days_ahead: int = 7
    calendar_max_events: int = 8
    calendar_timeout_s: float = 8.0

    @field_validator("calendar_ics_urls", mode="before")
    @classmethod
    def _split_ics_urls(cls, v: object) -> object:
        # Allow a plain delimited string in .env instead of a JSON array.
        if isinstance(v, str):
            return [u.strip() for u in re.split(r"[\s,]+", v) if u.strip()]
        return v


settings = Settings()
