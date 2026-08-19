from datetime import datetime, timezone

from fastapi import APIRouter


router = APIRouter(tags=["System"])


@router.get("/")
async def root():
    return {"name": "たすけの輪 Mock API", "version": "0.1.0", "docs": "/docs"}


@router.get("/health")
async def health():
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {"status": "ok", "time": timestamp}
