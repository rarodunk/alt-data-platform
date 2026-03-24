from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite:///./altdata.db"

    # Reddit API (optional - gracefully degrade if missing)
    REDDIT_CLIENT_ID: Optional[str] = None
    REDDIT_CLIENT_SECRET: Optional[str] = None
    REDDIT_USER_AGENT: str = "altdata-platform/1.0"

    # OpenSky Network (optional - free tier available)
    OPENSKY_USERNAME: Optional[str] = None
    OPENSKY_PASSWORD: Optional[str] = None

    # FlightAware (optional - paid)
    FLIGHTAWARE_API_KEY: Optional[str] = None

    # Cache settings
    CACHE_TTL_HOURS: int = 6

    # Logging
    LOG_LEVEL: str = "INFO"

    # CORS
    FRONTEND_URL: str = "http://localhost:3000"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
