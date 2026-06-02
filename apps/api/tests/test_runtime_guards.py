import asyncio
import os
import tempfile
import unittest
from contextlib import nullcontext
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from starlette.requests import Request

from app.api.auth_web import auth_guard, auth_status, use_secure_cookie
from app.db import init_db
from app.health_checks import check_runtime_permissions
from app.huey_app import RenderQueueManager
from app.runtime_guard import enforce_non_root_runtime
from app.tasks_registry import ensure_task_registry_loaded
from app.tasks_entries import autopilot_run
from app.tasks_helpers import fail_job
from app.tasks_autopilot import autopilot_preflight, expected_generated_tts_paths, has_reusable_generated_tts, run_autopilot_render_stage, run_autopilot_tts_stage
from app.tasks_tts_cache import build_generated_tts_cache_paths


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _Session:
    def __init__(self, rows):
        self._rows = rows
        self.added = []

    def exec(self, _query):
        return _Rows(self._rows)

    def add(self, obj):
        self.added.append(obj)


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class _FakeConnection:
    def __init__(self, slots: dict[int, bool]):
        self.slots = slots
        self.closed = False
        self.commits = 0

    def execute(self, _query, params=None):
        key = int((params or {}).get("key") or 0)
        if "pg_try_advisory_lock" in str(_query):
            if self.slots.get(key):
                return _ScalarResult(False)
            self.slots[key] = True
            return _ScalarResult(True)
        if "pg_advisory_unlock" in str(_query):
            self.slots[key] = False
            return _ScalarResult(True)
        raise AssertionError("unexpected query")

    def commit(self):
        self.commits += 1

    def close(self):
        self.closed = True


class _FakeEngine:
    def __init__(self, slots: dict[int, bool]):
        self.slots = slots
        self.connections: list[_FakeConnection] = []

    def connect(self):
        conn = _FakeConnection(self.slots)
        self.connections.append(conn)
        return conn


class RuntimeGuardTests(unittest.TestCase):
    def test_build_generated_tts_cache_paths_uses_expected_naming(self):
        root = Path(tempfile.mkdtemp())
        audio_dir = root / "audio"
        subtitle_dir = root / "subtitles"
        key, audio_path, srt_path = build_generated_tts_cache_paths(
            pid=22,
            project_script="当前文案",
            voice_name="voice-a",
            voice_rate="+0%",
            channel_key="career",
            workflow="mix",
            stable_digest=lambda _parts: "cachekey",
            project_audio_dir=lambda _pid: audio_dir,
            project_subtitles_dir=lambda _pid: subtitle_dir,
        )
        self.assertEqual(key, "cachekey")
        self.assertEqual(audio_path, audio_dir / "voice_cache_cachekey.mp3")
        self.assertEqual(srt_path, subtitle_dir / "subtitle_cache_cachekey.srt")

    def test_has_reusable_generated_tts_ignores_orphaned_old_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            audio_dir = root / "audio"
            subtitle_dir = root / "subtitles"
            audio_dir.mkdir(parents=True, exist_ok=True)
            subtitle_dir.mkdir(parents=True, exist_ok=True)
            (audio_dir / "old.mp3").write_bytes(b"old-audio")
            (subtitle_dir / "old.srt").write_text("old", encoding="utf-8")

            prep_ctx = SimpleNamespace(
                project=SimpleNamespace(script="当前文案", channel_key="career"),
                pid=22,
                scenes=[SimpleNamespace(narration="当前文案")],
                voice_name="voice-a",
                voice_rate="+0%",
                wf="mix",
            )

            with patch("app.tasks_autopilot.session_scope", return_value=nullcontext(object())), patch(
                "app.tasks_autopilot.prepare_render_context", return_value=prep_ctx
            ), patch("app.tasks_autopilot.project_audio_dir", return_value=audio_dir), patch(
                "app.tasks_autopilot.project_subtitles_dir", return_value=subtitle_dir
            ), patch("app.tasks_autopilot.stable_digest_bridge", return_value="currentkey"):
                self.assertFalse(has_reusable_generated_tts(22))

    def test_has_reusable_generated_tts_matches_current_cache_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            audio_dir = root / "audio"
            subtitle_dir = root / "subtitles"
            audio_dir.mkdir(parents=True, exist_ok=True)
            subtitle_dir.mkdir(parents=True, exist_ok=True)
            expected_audio = audio_dir / "voice_cache_currentkey.mp3"
            expected_srt = subtitle_dir / "subtitle_cache_currentkey.srt"
            expected_audio.write_bytes(b"audio")
            expected_srt.write_text("1\n00:00:00,000 --> 00:00:01,000\n当前文案\n", encoding="utf-8")

            prep_ctx = SimpleNamespace(
                project=SimpleNamespace(script="当前文案", channel_key="career"),
                pid=22,
                scenes=[SimpleNamespace(narration="当前文案")],
                voice_name="voice-a",
                voice_rate="+0%",
                wf="mix",
            )

            with patch("app.tasks_autopilot.session_scope", return_value=nullcontext(object())), patch(
                "app.tasks_autopilot.prepare_render_context", return_value=prep_ctx
            ), patch("app.tasks_autopilot.project_audio_dir", return_value=audio_dir), patch(
                "app.tasks_autopilot.project_subtitles_dir", return_value=subtitle_dir
            ), patch("app.tasks_autopilot.stable_digest_bridge", return_value="currentkey"):
                audio_path, srt_path = expected_generated_tts_paths(22)
                self.assertEqual(audio_path, expected_audio)
                self.assertEqual(srt_path, expected_srt)
                self.assertTrue(has_reusable_generated_tts(22))

    def test_render_queue_counts_running_render_jobs(self):
        rows = [
            SimpleNamespace(id=1, kind="render", status="running", payload_json="{}"),
            SimpleNamespace(id=2, kind="images", status="running", payload_json="{}"),
            SimpleNamespace(id=3, kind="autopilot", status="running", payload_json='{"current_stage":"render"}'),
            SimpleNamespace(id=4, kind="autopilot", status="running", payload_json='{"current_stage":"media"}'),
            SimpleNamespace(id=5, kind="storyboard", status="running", payload_json="{}"),
            SimpleNamespace(id=6, kind="autopilot", status="running", payload_json='{"current_stage":"render_finalize"}'),
        ]
        manager = RenderQueueManager()
        with patch("app.huey_app.session_scope", return_value=nullcontext(_Session(rows))):
            self.assertEqual(manager.get_running_render_count(), 3)
            self.assertEqual(manager.get_running_render_count(exclude_job_id=2), 3)
            self.assertFalse(manager.can_start_render())

    def test_render_queue_acquires_and_releases_advisory_slot_atomically(self):
        manager = RenderQueueManager()
        slots: dict[int, bool] = {}
        fake_engine = _FakeEngine(slots)
        with patch("app.huey_app.engine", fake_engine):
            self.assertTrue(manager.acquire_render_slot(job_id=101))
            self.assertTrue(any(slots.values()))
            self.assertTrue(manager.acquire_render_slot(job_id=101))
            self.assertTrue(manager.acquire_render_slot(job_id=102))
            self.assertFalse(manager.acquire_render_slot(job_id=103))
            manager.release_render_slot(job_id=101)
            self.assertTrue(manager.acquire_render_slot(job_id=103))
            manager.release_render_slot(job_id=102)
            manager.release_render_slot(job_id=103)
        self.assertFalse(any(slots.values()))
        self.assertTrue(any(conn.closed for conn in fake_engine.connections))

    def test_autopilot_final_missing_keeps_precise_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fail_job = MagicMock()
            fake_settings = SimpleNamespace(exports_dir=Path(tmpdir))
            with patch("app.tasks_autopilot.settings", fake_settings), patch(
                "app.tasks_autopilot.autopilot_mark_stage"
            ) as mark_stage, patch("app.tasks_autopilot.autopilot_get_job_status", return_value="running"):
                with self.assertRaisesRegex(RuntimeError, "最终成片生成失败，请从渲染阶段继续"):
                    run_autopilot_render_stage(
                        job_id=11,
                        project_id=22,
                        pid=22,
                        candidate_batch_id="batch-1",
                        resume_from_stage=None,
                        render_video_impl=lambda *args, **kwargs: None,
                        fail_job=fail_job,
                    )
        fail_job.assert_called_once()
        self.assertEqual(fail_job.call_args.kwargs.get("error_code"), "final_missing")
        stage_calls = [(call.args, call.kwargs) for call in mark_stage.call_args_list]
        self.assertTrue(any(len(args) >= 2 and args[1] == "render" and kwargs.get("detail") == "final_missing" for args, kwargs in stage_calls))
        self.assertFalse(any(kwargs.get("detail") == "final_check_failed" for _args, kwargs in stage_calls))

    def test_autopilot_preflight_allows_render_resume_with_reusable_tts(self):
        project = SimpleNamespace(id=22, voice_asset_id=None)
        with patch("app.material_policies.project_material_mode", return_value="network"), patch(
            "app.tasks_autopilot.has_reusable_generated_tts", return_value=True
        ), patch("app.tasks_autopilot.tts_status_dict") as tts_status:
            ok, meta = autopilot_preflight(
                object(),
                project,
                resume_stage="render",
                get_default_provider=lambda _session: None,
                get_api_key=lambda _session, _provider_id: "",
                tts_status_dict=tts_status,
            )
        self.assertTrue(ok)
        self.assertTrue(meta.get("reuse_generated_tts"))
        tts_status.assert_not_called()

    def test_autopilot_tts_stage_reuses_existing_outputs(self):
        with patch("app.tasks_autopilot.has_reusable_generated_tts", return_value=True), patch("app.tasks_autopilot.autopilot_mark_stage") as mark_stage:
            run_autopilot_tts_stage(
                job_id=11,
                project_id=22,
                pid=22,
                resume_from_stage="render",
                prepare_project_tts_impl=MagicMock(),
            )
        self.assertTrue(any(len(call.args) >= 2 and call.args[1] == "tts" and call.kwargs.get("status") == "done" for call in mark_stage.call_args_list))

    def test_autopilot_run_skips_orphaned_task(self):
        with patch("app.tasks._autopilot_job_guard_reason", return_value="missing_job"), patch("app.tasks.autopilot_run_impl") as run_impl:
            autopilot_run.call_local(88888, 4)
        run_impl.assert_not_called()

    def test_task_registry_contains_tasks_entries_autopilot(self):
        ensure_task_registry_loaded()
        from app.huey_app import huey

        self.assertIn("app.tasks_entries.autopilot_run", huey._registry._registry)

    def test_runtime_permission_check_flags_foreign_owner(self):
        root = Path(tempfile.mkdtemp())
        data_dir = root / "data"
        assets_dir = data_dir / "assets"
        exports_dir = data_dir / "exports"
        huey_dir = data_dir / "huey"
        projects_dir = data_dir / "projects"
        for p in (data_dir, assets_dir, exports_dir, huey_dir, projects_dir):
            p.mkdir(parents=True, exist_ok=True)
        bad = projects_dir / "project_9"
        bad.mkdir(exist_ok=True)
        fake_settings = SimpleNamespace(data_dir=data_dir, assets_dir=assets_dir, exports_dir=exports_dir, huey_storage_dir=huey_dir)
        fake_pwd = SimpleNamespace(pw_uid=1001)
        fake_grp = SimpleNamespace(gr_gid=1001)
        real_stat = Path.stat

        def _stat(path_obj: Path, *args, **kwargs):
            if path_obj == bad:
                return SimpleNamespace(st_uid=0, st_gid=0)
            return real_stat(path_obj, *args, **kwargs)

        with patch("app.health_checks.settings", fake_settings), patch("app.health_checks.pwd.getpwnam", return_value=fake_pwd), patch(
            "app.health_checks.grp.getgrnam", return_value=fake_grp
        ), patch("pathlib.Path.iterdir", autospec=True, side_effect=lambda self: [bad] if str(self).endswith('/projects') or self == projects_dir else []), patch(
            "pathlib.Path.stat", autospec=True, side_effect=_stat
        ):
            out = check_runtime_permissions()
        self.assertFalse(out.ok)
        self.assertEqual(out.status, "属主异常")

    def test_runtime_permission_check_flags_nested_foreign_owner(self):
        root = Path(tempfile.mkdtemp())
        data_dir = root / "data"
        assets_dir = data_dir / "assets"
        exports_dir = data_dir / "exports"
        huey_dir = data_dir / "huey"
        projects_dir = data_dir / "projects"
        nested = projects_dir / "project_14" / "imported" / "audio"
        for p in (data_dir, assets_dir, exports_dir, huey_dir, projects_dir):
            p.mkdir(parents=True, exist_ok=True)
        nested.mkdir(parents=True, exist_ok=True)
        fake_settings = SimpleNamespace(data_dir=data_dir, assets_dir=assets_dir, exports_dir=exports_dir, huey_storage_dir=huey_dir)
        current_uid = os.getuid()
        current_gid = os.getgid()
        other_uid = 0 if current_uid != 0 else 1001
        other_gid = 0 if current_gid != 0 else 1001
        fake_pwd = SimpleNamespace(pw_uid=current_uid)
        fake_grp = SimpleNamespace(gr_gid=current_gid)
        real_stat = Path.stat

        def _stat(path_obj: Path, *args, **kwargs):
            st = real_stat(path_obj, *args, **kwargs)
            if path_obj == nested:
                return SimpleNamespace(st_uid=other_uid, st_gid=other_gid, st_mode=st.st_mode)
            return st

        with patch("app.health_checks.settings", fake_settings), patch("app.health_checks.pwd.getpwnam", return_value=fake_pwd), patch(
            "app.health_checks.grp.getgrnam", return_value=fake_grp
        ), patch("pathlib.Path.stat", autospec=True, side_effect=_stat):
            out = check_runtime_permissions()
        self.assertFalse(out.ok)
        self.assertEqual(out.status, "属主异常")
        self.assertIn("project_14/imported/audio", str(out.detail))

    @unittest.skipIf(os.name == "nt", "Windows 不启用 root 运行守卫")
    def test_runtime_guard_blocks_root_without_explicit_override(self):
        with patch("app.runtime_guard.os.getuid", return_value=0), patch.dict("os.environ", {}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "拒绝以 root 身份启动 API"):
                enforce_non_root_runtime(data_dir=Path("/tmp/chengpian-data"), role="API")

    @unittest.skipIf(os.name == "nt", "Windows 不启用 root 运行守卫")
    def test_runtime_guard_allows_root_with_override(self):
        with patch("app.runtime_guard.os.getuid", return_value=0), patch.dict("os.environ", {"CHENGPIAN_ALLOW_ROOT_RUNTIME": "1"}, clear=False):
            enforce_non_root_runtime(data_dir=Path("/tmp/chengpian-data"), role="Worker")

    def test_fail_job_persists_error_meta_before_marking_failed(self):
        with patch("app.jobs.patch_job_payload") as patch_payload, patch("app.jobs.update_job") as update_job:
            fail_job(
                9,
                message="生成视频失败：分镜生成失败",
                error_code="storyboard_failed",
                blocking_component="llm",
                recommended_action="go_settings_llm",
                recoverable=True,
            )

        patch_payload.assert_called_once_with(
            9,
            {
                "error_code": "storyboard_failed",
                "blocking_component": "llm",
                "recommended_action": "go_settings_llm",
                "recoverable": True,
            },
        )
        update_job.assert_called_once_with(9, status="failed", progress=100, message="生成视频失败：分镜生成失败")

    def test_init_db_raises_when_migration_fails(self):
        fake_conn = MagicMock()
        fake_ctx = MagicMock()
        fake_ctx.__enter__.return_value = fake_conn
        fake_ctx.__exit__.return_value = False
        with patch("app.db.SQLModel.metadata.create_all"), patch("app.db.engine.connect", return_value=fake_ctx), patch(
            "app.migrations.migrate", side_effect=RuntimeError("boom")
        ):
            with self.assertRaisesRegex(RuntimeError, "数据库迁移失败"):
                init_db()

    def test_use_secure_cookie_auto_respects_forwarded_proto(self):
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/api/auth/status",
                "headers": [(b"x-forwarded-proto", b"https")],
                "scheme": "http",
                "query_string": b"",
                "server": ("testserver", 80),
                "client": ("127.0.0.1", 12345),
            }
        )
        with patch("app.api.auth_web.settings", SimpleNamespace(cookie_secure_mode="auto")):
            self.assertTrue(use_secure_cookie(request))

    def test_auth_guard_blocks_when_setup_missing(self):
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/api/projects",
                "headers": [],
                "scheme": "http",
                "query_string": b"",
                "server": ("testserver", 80),
                "client": ("127.0.0.1", 12345),
            }
        )

        async def _call_next(_request):
            raise AssertionError("未认证请求不应继续进入路由")

        with patch("app.api.auth_web.session_scope", return_value=nullcontext(object())), patch(
            "app.api.auth_web.auth_is_configured", return_value=False
        ):
            resp = asyncio.run(auth_guard(request, _call_next))
        self.assertEqual(resp.status_code, 401)
        self.assertIn("auth_setup_required", resp.body.decode("utf-8"))

    def test_auth_guard_blocks_stale_admin_session(self):
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/api/projects",
                "headers": [],
                "scheme": "http",
                "query_string": b"",
                "server": ("testserver", 80),
                "client": ("127.0.0.1", 12345),
            }
        )

        async def _call_next(_request):
            raise AssertionError("旧管理员会话不应继续进入路由")

        with patch("app.api.auth_web.session_scope", return_value=nullcontext(object())), patch(
            "app.api.auth_web.auth_is_configured", return_value=True
        ), patch("app.api.auth_web.get_authenticated_admin_username", return_value=None):
            resp = asyncio.run(auth_guard(request, _call_next))
        self.assertEqual(resp.status_code, 401)
        self.assertIn("auth_required", resp.body.decode("utf-8"))

    def test_auth_guard_allows_health_without_login(self):
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/api/health",
                "headers": [],
                "scheme": "http",
                "query_string": b"",
                "server": ("testserver", 80),
                "client": ("127.0.0.1", 12345),
            }
        )

        async def _call_next(_request):
            return "ok"

        resp = asyncio.run(auth_guard(request, _call_next))
        self.assertEqual(resp, "ok")

    def test_auth_status_treats_stale_admin_session_as_logged_out(self):
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/api/auth/status",
                "headers": [],
                "scheme": "http",
                "query_string": b"",
                "server": ("testserver", 80),
                "client": ("127.0.0.1", 12345),
            }
        )
        with patch("app.api.auth_web.session_scope", return_value=nullcontext(object())), patch(
            "app.api.auth_web.auth_is_configured", return_value=True
        ), patch("app.api.auth_web.get_authenticated_admin_username", return_value=None):
            out = auth_status(request)
        self.assertFalse(out.authenticated)
        self.assertIsNone(out.username)

    def test_auth_guard_allows_member_session(self):
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/api/projects",
                "headers": [],
                "scheme": "http",
                "query_string": b"",
                "server": ("testserver", 80),
                "client": ("127.0.0.1", 12345),
            }
        )

        async def _call_next(_request):
            return "ok"

        with patch("app.api.auth_web.session_scope", return_value=nullcontext(object())), patch(
            "app.api.auth_web.auth_is_configured", return_value=True
        ), patch("app.api.auth_web.get_authenticated_principal", return_value={"username": "editor01", "role": "member", "is_admin": False, "user_id": 7}):
            resp = asyncio.run(auth_guard(request, _call_next))
        self.assertEqual(resp, "ok")


if __name__ == "__main__":
    unittest.main()
