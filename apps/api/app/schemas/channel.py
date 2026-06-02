from pydantic import BaseModel


class ChannelPackOut(BaseModel):
    key: str
    name: str
    description: str
