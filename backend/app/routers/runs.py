from fastapi import APIRouter

router = APIRouter()


@router.get("/runs")
async def list_runs():
    return []