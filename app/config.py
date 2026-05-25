from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="MORNING_DUST_", extra="ignore")

    app_name: str = "morning-dust"
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    weather_lat: float = 52.021414448256394
    weather_lon: float = 5.067054724580616
    weather_location_name: str = "Nieuwegein"
    weather_timeout_s: float = 5.0

    todo_file_path: str = "data/todos.json"


settings = Settings()
