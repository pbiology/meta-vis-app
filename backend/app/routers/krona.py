from fastapi import APIRouter

router = APIRouter()


@router.get("/samples/{sample_id}/krona")
async def get_krona(sample_id: str):
    return {}