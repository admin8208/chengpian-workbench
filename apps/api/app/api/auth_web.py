from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from app.auth import (
    AUTH_COOKIE_MAX_AGE,
    AUTH_COOKIE_NAME,
    AUTH_SETUP_PATHS,
    authenticate_login,
    auth_is_configured,
    create_user_account,
    create_session_token,
    get_authenticated_admin_username,
    get_authenticated_principal,
    list_user_accounts,
    set_admin_credentials,
    set_user_account_enabled,
    set_user_account_password,
)
from app.access_control import reset_current_principal, set_current_principal
from app.db import session_scope
from app.schemas import AuthStatusOut, OkOut, LoginIn, SetupAdminIn, UserAccountCreateIn, UserAccountOut, UserAccountPatchIn, UserAccountPasswordResetIn
from app.settings import settings

router = APIRouter()


def user_account_to_out(item) -> UserAccountOut:
    return UserAccountOut(
        id=int(item.id),
        username=item.username,
        enabled=bool(item.enabled),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def require_admin(request: Request, session) -> str:
    username = get_authenticated_admin_username(request, session)
    if not username:
        raise HTTPException(status_code=403, detail="仅管理员可执行该操作")
    return username


def request_scheme(request: Request) -> str:
    forwarded = str(request.headers.get("x-forwarded-proto") or "").strip().lower()
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    scope = getattr(request, "scope", None) or {}
    scope_scheme = str(scope.get("scheme") or "").strip().lower()
    if scope_scheme:
        return scope_scheme
    return str(getattr(request.url, "scheme", "") or "http").strip().lower()


def use_secure_cookie(request: Request) -> bool:
    mode = str(settings.cookie_secure_mode or "auto").strip().lower()
    if mode == "true":
        return True
    if mode == "false":
        return False
    return request_scheme(request) == "https"


def set_session_cookie(response: Response, request: Request, token: str) -> None:
    response.set_cookie(
        AUTH_COOKIE_NAME,
        token,
        max_age=AUTH_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=use_secure_cookie(request),
        path="/",
    )


def clear_session_cookie(response: Response, request: Request) -> None:
    response.delete_cookie(AUTH_COOKIE_NAME, path="/", secure=use_secure_cookie(request), samesite="lax")


async def auth_guard(request: Request, call_next):
    path = str(request.url.path or "")
    if path in ("/favicon.ico", "/vite.svg"):
        return await call_next(request)
    if path == "/api/health":
        return await call_next(request)
    if path.startswith('/api/files/s/'):
        return await call_next(request)
    if path.startswith("/ui/"):
        return await call_next(request)
    protected = (
        path.startswith("/api")
        or path.startswith("/assets")
        or path.startswith("/exports")
        or path.startswith("/docs")
        or path.startswith("/redoc")
        or path == "/openapi.json"
    )
    if not protected:
        return await call_next(request)
    if path in AUTH_SETUP_PATHS:
        return await call_next(request)
    with session_scope() as session:
        configured = auth_is_configured(session)
        if not configured:
            return JSONResponse(status_code=401, content={"detail": "请先初始化管理员账号", "code": "auth_setup_required"})
        principal = get_authenticated_principal(request, session)
        if principal:
            token = set_current_principal(principal)
            try:
                return await call_next(request)
            finally:
                reset_current_principal(token)
    return JSONResponse(status_code=401, content={"detail": "请先登录", "code": "auth_required"})


@router.get("/api/auth/status", response_model=AuthStatusOut)
def auth_status(request: Request):
    with session_scope() as session:
        configured = auth_is_configured(session)
        principal = get_authenticated_principal(request, session) if configured else None
    return AuthStatusOut(
        enabled=True,
        authenticated=bool(principal),
        setup_required=not configured,
        username=(principal or {}).get("username") or None,
        role=str((principal or {}).get("role") or "admin"),
        is_admin=bool((principal or {}).get("is_admin")),
    )


@router.post("/api/auth/setup", response_model=AuthStatusOut)
def auth_setup(body: SetupAdminIn, response: Response, request: Request):
    with session_scope() as session:
        if auth_is_configured(session):
            raise HTTPException(status_code=400, detail="管理员账号已初始化")
        username = set_admin_credentials(session, username=body.username, password=body.password)
    token = create_session_token(username=username, role="admin")
    set_session_cookie(response, request, token)
    return AuthStatusOut(enabled=True, authenticated=True, setup_required=False, username=username, role="admin", is_admin=True)


@router.post("/api/auth/login", response_model=AuthStatusOut)
def auth_login(body: LoginIn, response: Response, request: Request):
    with session_scope() as session:
        if not auth_is_configured(session):
            raise HTTPException(status_code=400, detail="请先初始化管理员账号")
        principal = authenticate_login(session, username=body.username, password=body.password)
        if not principal:
            raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_session_token(username=str(principal.get("username") or ""), role=str(principal.get("role") or "member"), user_id=principal.get("user_id"))
    set_session_cookie(response, request, token)
    return AuthStatusOut(
        enabled=True,
        authenticated=True,
        setup_required=False,
        username=str(principal.get("username") or "") or None,
        role=str(principal.get("role") or "member"),
        is_admin=bool(principal.get("is_admin")),
    )


@router.post("/api/auth/logout", response_model=OkOut)
def auth_logout(response: Response, request: Request):
    clear_session_cookie(response, request)
    return OkOut(ok=True)


@router.get("/api/auth/users", response_model=list[UserAccountOut])
def list_auth_users(request: Request):
    with session_scope() as session:
        require_admin(request, session)
        return [user_account_to_out(item) for item in list_user_accounts(session) if item.id is not None]


@router.post("/api/auth/users", response_model=UserAccountOut)
def create_auth_user(body: UserAccountCreateIn, request: Request):
    with session_scope() as session:
        require_admin(request, session)
        item = create_user_account(session, username=body.username, password=body.password)
        return user_account_to_out(item)


@router.patch("/api/auth/users/{user_id}", response_model=UserAccountOut)
def patch_auth_user(user_id: int, body: UserAccountPatchIn, request: Request):
    with session_scope() as session:
        require_admin(request, session)
        if body.enabled is None:
            raise HTTPException(status_code=400, detail="至少提供一个可更新字段")
        item = set_user_account_enabled(session, user_id, bool(body.enabled))
        return user_account_to_out(item)


@router.post("/api/auth/users/{user_id}/reset-password", response_model=UserAccountOut)
def reset_auth_user_password(user_id: int, body: UserAccountPasswordResetIn, request: Request):
    with session_scope() as session:
        require_admin(request, session)
        item = set_user_account_password(session, user_id, body.password)
        return user_account_to_out(item)
