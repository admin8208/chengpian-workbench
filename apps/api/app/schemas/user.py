from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class UserAccountCreateIn(BaseModel):
    username: str
    password: str


class UserAccountPatchIn(BaseModel):
    enabled: Optional[bool] = None


class UserAccountPasswordResetIn(BaseModel):
    password: str


class UserAccountOut(BaseModel):
    id: int
    username: str
    enabled: bool
    created_at: datetime
    updated_at: datetime
