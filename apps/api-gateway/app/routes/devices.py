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


class DeviceCreate(BaseModel):
    name: str
    mac: str
    x: float = 0.0
    y: float = 0.0
    firmware_version: str = "0.5.0"


@router.get("/")
async def list_devices():
    sb = get_sb()
    if not sb:
        return {"data": [], "error": "Supabase not configured"}
    result = sb.table("devices").select("*").execute()
    return {"data": result.data}


@router.post("/")
async def create_device(device: DeviceCreate):
    sb = get_sb()
    if not sb:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    result = sb.table("devices").insert(device.model_dump()).execute()
    return {"data": result.data}


@router.get("/{device_id}")
async def get_device(device_id: str):
    sb = get_sb()
    if not sb:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    result = sb.table("devices").select("*").eq("id", device_id).single().execute()
    return {"data": result.data}
