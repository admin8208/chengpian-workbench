import unittest
from contextlib import nullcontext
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException, Response
from starlette.requests import Request

from app.api.auth_web import auth_login, create_auth_user, list_auth_users, patch_auth_user, reset_auth_user_password
from app.auth import create_session_token, verify_session_token
from app.schemas import LoginIn, UserAccountCreateIn, UserAccountPatchIn, UserAccountPasswordResetIn


def _request(path: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": path,
            "headers": [],
            "scheme": "http",
            "query_string": b"",
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 12345),
        }
    )


class AuthWebAccountTests(unittest.TestCase):
    def test_session_token_roundtrip_preserves_username_role_and_user_id(self):
        token = create_session_token(username="editor01", role="member", user_id=7)
        payload = verify_session_token(token)

        self.assertEqual(payload, {"username": "editor01", "exp": payload["exp"], "role": "member", "user_id": 7})

    def test_auth_login_returns_member_role(self):
        response = Response()
        request = _request("/api/auth/login")
        principal = {"username": "editor01", "role": "member", "is_admin": False, "user_id": 7}
        with patch("app.api.auth_web.session_scope", return_value=nullcontext(object())), patch(
            "app.api.auth_web.auth_is_configured", return_value=True
        ), patch("app.api.auth_web.authenticate_login", return_value=principal):
            out = auth_login(LoginIn(username="editor01", password="secret123"), response, request)
        self.assertTrue(out.authenticated)
        self.assertEqual(out.role, "member")
        self.assertFalse(out.is_admin)
        self.assertIn("chengpian_session=", response.headers.get("set-cookie", ""))
        token = response.headers.get("set-cookie", "").split("chengpian_session=", 1)[1].split(";", 1)[0]
        payload = verify_session_token(token)
        self.assertEqual(payload.get("username"), "editor01")
        self.assertEqual(payload.get("role"), "member")
        self.assertEqual(payload.get("user_id"), 7)

    def test_create_auth_user_requires_admin(self):
        request = _request("/api/auth/users")
        with patch("app.api.auth_web.session_scope", return_value=nullcontext(object())), patch(
            "app.api.auth_web.require_admin", side_effect=HTTPException(status_code=403, detail="仅管理员可执行该操作")
        ):
            with self.assertRaises(HTTPException) as ctx:
                create_auth_user(UserAccountCreateIn(username="editor01", password="secret123"), request)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_list_and_patch_auth_users(self):
        now = datetime.now(UTC)
        user = SimpleNamespace(id=5, username="editor01", enabled=True, created_at=now, updated_at=now)
        request = _request("/api/auth/users")
        with patch("app.api.auth_web.session_scope", return_value=nullcontext(object())), patch(
            "app.api.auth_web.require_admin", return_value="admin"
        ), patch("app.api.auth_web.list_user_accounts", return_value=[user]):
            out = list_auth_users(request)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].username, "editor01")

        disabled = SimpleNamespace(id=5, username="editor01", enabled=False, created_at=now, updated_at=now)
        with patch("app.api.auth_web.session_scope", return_value=nullcontext(object())), patch(
            "app.api.auth_web.require_admin", return_value="admin"
        ), patch("app.api.auth_web.set_user_account_enabled", return_value=disabled):
            patched = patch_auth_user(5, UserAccountPatchIn(enabled=False), request)
        self.assertFalse(patched.enabled)

        rotated = SimpleNamespace(id=5, username="editor01", enabled=False, created_at=now, updated_at=now)
        with patch("app.api.auth_web.session_scope", return_value=nullcontext(object())), patch(
            "app.api.auth_web.require_admin", return_value="admin"
        ), patch("app.api.auth_web.set_user_account_password", return_value=rotated):
            reset = reset_auth_user_password(5, UserAccountPasswordResetIn(password="new-secret-123"), request)
        self.assertEqual(reset.username, "editor01")


if __name__ == "__main__":
    unittest.main()
