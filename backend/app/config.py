import json
import logging
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    mongodb_host: str = "localhost"
    mongodb_port: int = 27017
    mongodb_db_name: str = ""
    mongodb_username: Optional[str] = None
    mongodb_password: Optional[str] = None
    mongodb_auth_source: str = "admin"
    app_env: str = "development"
    log_level: str = "info"
    jwt_secret: str = ""
    controls_taxa_path: str = "controls_taxa.json"

    # CORS — comma-separated list of allowed origins
    cors_origins: str = "http://localhost:5173"

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

    # Controls taxa loaded from JSON at startup
    controls_taxa: dict = {}

    def load_outbreak_configs(self) -> None:
        """Load outbreak configurations from JSON file."""
        config_path = Path(__file__).parent.parent / "outbreak_configs.json"

        if not config_path.exists():
            logger.warning("outbreak_configs.json not found at %s", config_path)
            self.outbreak_configs = []
            return

        try:
            with open(config_path, "r") as f:
                data = json.load(f)
                self.outbreak_configs = data.get("configs", [])
                logger.info(
                    "Loaded %d outbreak configs from %s",
                    len(self.outbreak_configs),
                    config_path.name,
                )
        except json.JSONDecodeError as e:
            logger.error("Error parsing outbreak_configs.json: %s", e, exc_info=True)
            self.outbreak_configs = []
        except Exception as e:
            logger.error("Error loading outbreak_configs.json: %s", e, exc_info=True)
            self.outbreak_configs = []

    def load_controls_taxa(self) -> None:
        """Load controls taxa from JSON file."""
        config_path = Path(__file__).parent.parent / self.controls_taxa_path

        if not config_path.exists():
            logger.warning("controls_taxa.json not found at %s", config_path)
            self.controls_taxa = {}
            return

        try:
            with open(config_path, "r") as f:
                self.controls_taxa = json.load(f)
                logger.info("Loaded controls taxa from %s", config_path.name)
        except json.JSONDecodeError as e:
            logger.error("Error parsing controls_taxa.json: %s", e, exc_info=True)
            self.controls_taxa = {}
        except Exception as e:
            logger.error("Error loading controls_taxa.json: %s", e, exc_info=True)
            self.controls_taxa = {}


def validate_jwt_secret(jwt_secret: str) -> None:
    """
    Validate JWT secret meets minimum security requirements.

    Args:
        jwt_secret: The JWT secret string from configuration.

    Raises:
        ValueError: If jwt_secret is less than 32 characters (256 bits).

    Why 32 characters?
    - NIST recommends symmetric keys of at least 128 bits for sensitive operations
    - JWT secrets should ideally be 256+ bits (32+ chars in base64)
    - This prevents brute-force attacks on JWT tokens
    """
    min_length = 32
    if len(jwt_secret) < min_length:
        raise ValueError(
            f"JWT_SECRET must be at least {min_length} characters long. "
            "Configure it in backend/.env or set the JWT_SECRET environment variable."
        )


settings = Settings()
# Load configs when app starts
settings.load_outbreak_configs()
settings.load_controls_taxa()
