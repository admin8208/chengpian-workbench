from typing import Optional

from pydantic import BaseModel


class AuthStatusOut(BaseModel):
    enabled: bool
    authenticated: bool
    setup_required: bool
    username: Optional[str] = None
    role: str = "admin"
    is_admin: bool = False


class LoginIn(BaseModel):
    username: str
    password: str


class SetupAdminIn(BaseModel):
    username: str
    password: str
