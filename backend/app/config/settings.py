from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://simplesave:simplesave@localhost:5432/simplesave"

    # Firebase
    firebase_credentials_path: str = "firebase-credentials.json"
    firebase_storage_bucket: str = ""

    # SendGrid
    sendgrid_api_key: str = ""
    sendgrid_from_email: str = "noreply@simplesave.co.il"
    sendgrid_from_name: str = "SimpleSave"

    # App
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    environment: str = "development"

    # Dev-only sanity-check switch. When true (and NOT production), the backend
    # accepts an "Authorization: Bearer dev-<role>" token and resolves it to a
    # seeded dev user of that role — no Firebase registration/verification needed.
    # Mirror of the frontend VITE_AUTH_BYPASS flag. MUST be false in production.
    auth_bypass: bool = False


settings = Settings()
