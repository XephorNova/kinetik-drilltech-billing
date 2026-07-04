from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    MONGO_URL: str = "mongodb://localhost:27017"
    MONGO_DB_NAME: str = "billing"
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440
    ADMIN_USERNAME: str
    ADMIN_PASSWORD: str
    COOKIE_SECURE: bool = False
    CORS_ORIGINS: str = "http://localhost:5173"


settings = Settings()
