from fastapi import APIRouter

from app.api_channel_packs import list_channel_packs_api
from app.schemas import ChannelPackOut

router = APIRouter(tags=["channel"])


@router.get("/api/channel-packs", response_model=list[ChannelPackOut])
def list_channel_packs():
    return list_channel_packs_api()
