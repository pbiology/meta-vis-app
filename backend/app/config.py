from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    mongodb_url: str
    mongodb_db_name: str
    static_files_root: str
    app_env: str = "development"
    log_level: str = "info"
    jwt_secret: str = "change-me-in-production"
    controls_taxa_path: str = "controls_taxa.json"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()