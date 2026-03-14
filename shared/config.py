from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://catcar:catcar@localhost:5432/catcar"
    REDIS_URL: str = "redis://localhost:6379/0"
    ADMIN_API_KEY: str = "change-me-in-production"
    LOG_LEVEL: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
