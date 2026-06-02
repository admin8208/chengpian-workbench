from sqlmodel import select

from app.db import session_scope
from app.models import ChannelPack
from app.schemas import ChannelPackOut

VISIBLE_PACKS = {"history", "emotion", "career", "family_cn"}


def list_channel_packs_api() -> list[ChannelPackOut]:
    with session_scope() as session:
        packs = session.exec(select(ChannelPack).order_by(ChannelPack.key)).all()
        return [ChannelPackOut(key=p.key, name=p.name, description=p.description) for p in packs if str(p.key or "") in VISIBLE_PACKS]
