from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440
    ANTHROPIC_API_KEY: str
    RESEND_API_KEY: str
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    APP_ENV: str = "production"
    CORS_ORIGINS: str = "https://guiame.pro"

    class Config:
        env_file = ".env"

settings = Settings()
