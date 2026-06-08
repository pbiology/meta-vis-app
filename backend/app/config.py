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
    # Full Mongo connection string override. When set, the host/port/user/pass
    # fields above are ignored and this URI is passed verbatim to the driver.
    # Use this in production where the URI carries query params we cannot
    # express piecemeal (replicaSet=, tls=, multiple seed hosts, etc.).
    mongodb_uri: Optional[str] = None
    # When True (default), append `directConnection=true` to the Mongo URL.
    # Works for single-node replica sets behind a port mapping (the standard
    # dev setup) — the driver talks directly to the one host we pass without
    # trying to resolve other members advertised by `rs.conf()`. Multi-document
    # transactions still work because the server reports itself as a replica
    # set primary in its hello response. Set to False if using a real mongodb+srv
    # URL or a multi-host cluster URL in production.
    mongodb_direct_connection: bool = True
    # Wrap ingest + case-mutation writes in a multi-document transaction.
    # Requires the target Mongo to be a replica set or sharded cluster — a
    # standalone mongod rejects `start_transaction()`. Set to False on
    # environments running a plain standalone mongod (e.g. the stage VM),
    # accepting that a mid-sequence failure can leave partial writes behind.
    mongodb_use_transactions: bool = True
    app_env: str = "development"
    log_level: str = "info"
    controls_taxa_path: str = "controls_taxa.json"

    # Keycloak OIDC — the realm's issuer URL. The JWKS endpoint and other OIDC
    # metadata are derived from it. Tokens are accepted only if their `iss`
    # matches this value exactly.
    keycloak_issuer: str = "http://localhost:8081/realms/meta-vis"
    # Comma-separated list of client IDs whose tokens this API accepts. The
    # `azp` claim of every incoming token must match one of these. Defaults
    # cover the SPA and the ingest CLI.
    keycloak_client_ids: str = "meta-vis-frontend,meta-vis-cli"
    # The KC client whose client-roles drive app authorization. Tokens are
    # inspected at `resource_access[<role_client>].roles`. Defaults to the
    # SPA client; point at a dedicated resource client if you'd rather host
    # the roles there.
    keycloak_role_client: str = "meta-vis-frontend"
    # JWKS endpoint override. When backend and KC live on different networks,
    # the backend cannot reach the browser-facing issuer URL — it needs an
    # in-network hostname for the certs fetch. The `iss` claim is still
    # validated against `keycloak_issuer`; only the HTTP fetch URL changes.
    # Leave unset to derive from the issuer.
    keycloak_jwks_url: Optional[str] = None

    # CORS — comma-separated list of allowed origins
    cors_origins: str = "http://localhost:5173"

    # NCBI E-utilities — optional API key, raises rate limit from 3 to 10 req/s
    ncbi_api_key: Optional[str] = None

    # Freshdesk — base URL for case ticket links. `{ticket_id}` is substituted
    # at serialisation time. Leave unset to disable the ticket link in the UI.
    freshdesk_base_url: Optional[str] = None

    # Ingest upload bundle limits. The CLI uploads a tar.gz bundle to
    # /api/v1/ingest/* — these caps protect the server from tar bombs and
    # accidental huge uploads. Compressed: rejected before extraction starts.
    # Uncompressed: enforced incrementally as members are extracted.
    ingest_upload_max_compressed_bytes: int = 2 * 1024 * 1024 * 1024  # 2 GiB
    ingest_upload_max_uncompressed_bytes: int = 8 * 1024 * 1024 * 1024  # 8 GiB

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
        except OSError as e:
            logger.error("Error reading outbreak_configs.json: %s", e, exc_info=True)
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
        except OSError as e:
            logger.error("Error reading controls_taxa.json: %s", e, exc_info=True)
            self.controls_taxa = {}


settings = Settings()
# Load configs when app starts
settings.load_outbreak_configs()
settings.load_controls_taxa()
