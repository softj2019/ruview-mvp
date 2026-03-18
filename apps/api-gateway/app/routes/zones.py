import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from supabase import create_client

router = APIRouter()


def get_sb():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        return None
    return create_client(url, key)


class ZoneCreate(BaseModel):
    name: str
    polygon: list[dict]
    floor_id: str | None = None


@router.get("/")
async def list_zones():
    sb = get_sb()
    if not sb:
        return {"data": [], "error": "Supabase not configured"}
    result = sb.table("zones").select("*").execute()
    return {"data": result.data}


@router.post("/")
async def create_zone(zone: ZoneCreate):
    sb = get_sb()
    if not sb:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    result = sb.table("zones").insert(zone.model_dump()).execute()
    return {"data": result.data}
