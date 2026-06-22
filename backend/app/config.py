from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "DFMS"
    debug: bool = False
    database_url: str = "postgresql://dfms:dfms@localhost:5432/dfms"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480
    worker_session_expire_minutes: int = 15
    farm_timezone: str = "Africa/Nairobi"
    three_session_threshold_litres: float = 15.0


settings = Settings()
