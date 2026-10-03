from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./clinic.db"
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    m2m_access_token_expire_minutes: int = 15
    jwt_issuer: str = "clinic-api"
    jwt_audience: str = "clinic-api"
    oauth_bootstrap_client_id: str | None = None
    oauth_bootstrap_client_secret: str | None = None
    oauth_bootstrap_client_scopes: str = "partner:consultas:read"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


def get_settings() -> Settings:
    return Settings()
