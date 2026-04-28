# app/routers/config.py
#
# Public configuration endpoint — no authentication required.
# Exposes server-side constants that the frontend needs to stay in sync with.

from fastapi import APIRouter

from app.constants import HOST_TAXON_IDS

router = APIRouter(prefix="/config", tags=["config"])


@router.get("", summary="Public app configuration")
def get_config() -> dict:
    """Return configuration values that the frontend should read from the server.

    Currently exposes host_taxon_ids so the frontend does not maintain its own
    hardcoded copy of HOST_TAXON_IDS.
    """
    return {"host_taxon_ids": sorted(HOST_TAXON_IDS)}
