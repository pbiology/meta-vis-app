from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    mongodb_host: str = "localhost"
    mongodb_port: int = 27017
    mongodb_db_name: str
    mongodb_username: Optional[str] = None
    mongo_app_password: Optional[str] = None
    mongodb_auth_source: str = "admin"
    app_env: str = "development"
    log_level: str = "info"
    jwt_secret: str
    controls_taxa_path: str = "controls_taxa.json"

    # Object storage — optional, falls back to MongoDB if not set
    object_storage_endpoint: Optional[str] = None
    object_storage_access_key: Optional[str] = None
    object_storage_secret_key: Optional[str] = None
    object_storage_bucket: str = "meta-vis"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
