from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import json


class Settings(BaseSettings):
    mongodb_host: str = "localhost"
    mongodb_port: int = 27017
    mongodb_db_name: str = ""
    mongodb_username: Optional[str] = None
    mongo_app_password: Optional[str] = None
    mongodb_auth_source: str = "admin"
    app_env: str = "development"
    log_level: str = "info"
    jwt_secret: str = ""
    controls_taxa_path: str = "controls_taxa.json"

    # NCBI E-utilities — optional API key, raises rate limit from 3 to 10 req/s
    ncbi_api_key: Optional[str] = None

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

    # Outbreak configs loaded from JSON at startup
    outbreak_configs: list[dict] = []

    def load_outbreak_configs(self):
        """Load outbreak configurations from JSON file."""
        config_path = Path(__file__).parent.parent / "outbreak_configs.json"

        if not config_path.exists():
            print(f"Warning: outbreak_configs.json not found at {config_path}")
            self.outbreak_configs = []
            return

        try:
            with open(config_path, "r") as f:
                data = json.load(f)
                self.outbreak_configs = data.get("configs", [])
                print(
                    f"Loaded {len(self.outbreak_configs)} outbreak configs from {config_path.name}"
                )
        except json.JSONDecodeError as e:
            print(f"Error parsing outbreak_configs.json: {e}")
            self.outbreak_configs = []
        except Exception as e:
            print(f"Error loading outbreak_configs.json: {e}")
            self.outbreak_configs = []


settings = Settings()
# Load outbreak configs when app starts
settings.load_outbreak_configs()
