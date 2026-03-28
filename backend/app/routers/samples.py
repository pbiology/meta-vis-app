from fastapi import APIRouter

router = APIRouter()


@router.get("/samples/{sample_id}")
async def get_sample(sample_id: str):
    return {}