from pydantic import BaseModel


class OkOut(BaseModel):
    ok: bool = True
