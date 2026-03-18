import os
from fastapi import APIRouter, Query
from supabase import create_client

router = APIRouter()


def get_sb():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        return None
    return create_client(url, key)


@router.get("/")
async def list_events(
    limit: int = Query(50, le=200),
    device_id: str | None = None,
    event_type: str | None = None,
):
    sb = get_sb()
    if not sb:
        return {"data": [], "error": "Supabase not configured"}

    query = sb.table("events").select("*").order("timestamp", desc=True).limit(limit)

    if device_id:
        query = query.eq("device_id", device_id)
    if event_type:
        query = query.eq("type", event_type)

    result = query.execute()
    return {"data": result.data}


@router.get("/stats")
async def event_stats():
    sb = get_sb()
    if not sb:
        return {"data": {}, "error": "Supabase not configured"}

    result = sb.table("events").select("type", count="exact").execute()
    return {"data": result.data, "count": result.count}
