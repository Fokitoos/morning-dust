from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="MORNING_DUST_", extra="ignore")

    app_name: str = "morning-dust"
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False


settings = Settings()