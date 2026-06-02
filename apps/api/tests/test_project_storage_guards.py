import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app.api_common import resolve_final_export_status
from app.modules.creator.project_deletion_service import _collect_project_asset_ids, delete_project_api
from app.modules.creator.project_mutation_service import create_project_api
from app.project_paths import ensure_project_root_dir, project_root_path
from app.schemas import ProjectCreateIn


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None


class _CreateSession:
    def __init__(self, pack, project):
        self.queue = [[pack]]
        self.project = project
        self.added = []

    def exec(self, _query):
        rows = self.queue.pop(0) if self.queue else []
        return _Rows(rows)

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        self.project.id = 7

    def refresh(self, obj):
        obj.id = self.project.id


class _DeleteSession:
    def __init__(self, project):
        self.queue = [
            [project],
            [],
            [],
            [],
            [],
            [],
            [project],
            [],
            [],
            [],
            [],
        ]
        self.deleted = []
        self.added = []

    def exec(self, _query):
        rows = self.queue.pop(0) if self.queue else []
        return _Rows(rows)

    def add(self, obj):
        self.added.append(obj)

    def delete(self, obj):
        self.deleted.append(obj)


class _DeleteSessionWithAssets:
    def __init__(self, first_queue, second_queue):
        self._queues = [list(first_queue), list(second_queue)]
        self._idx = 0
        self.deleted = []
        self.added = []

    def advance(self):
        self._idx += 1

    def exec(self, _query):
        queue = self._queues[self._idx] if self._idx < len(self._queues) else []
        rows = queue.pop(0) if queue else []
        return _Rows(rows)

    def add(self, obj):
        self.added.append(obj)

    def delete(self, obj):
        self.deleted.append(obj)


class _DeleteSessionWithPendingCancel:
    def __init__(self, project, job):
        self.project = project
        self.job = job
        self.queue = [
            [project],
            [job],
            [job],
            [],
            [],
            [],
            [],
            [],
            [project],
            [],
            [],
            [],
            [],
        ]
        self.deleted = []
        self.added = []

    def exec(self, _query):
        rows = self.queue.pop(0) if self.queue else []
        return _Rows(rows)

    def add(self, obj):
        self.added.append(obj)

    def delete(self, obj):
        self.deleted.append(obj)


class ProjectStorageGuardTests(unittest.TestCase):
    def test_project_root_path_is_side_effect_free(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_settings = SimpleNamespace(data_dir=Path(tmpdir))
            with patch("app.project_paths.settings", fake_settings):
                path = project_root_path(42)
                self.assertFalse(path.exists())
                ensured = ensure_project_root_dir(42)
                self.assertTrue(ensured.exists())
                self.assertEqual(path, ensured)

    def test_ensure_project_root_dir_normalizes_owner_when_possible(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_settings = SimpleNamespace(data_dir=Path(tmpdir))
            fake_pwd = SimpleNamespace(pw_uid=1001)
            fake_grp = SimpleNamespace(gr_gid=1001)
            with patch("app.project_paths.settings", fake_settings), patch("app.project_paths.pwd.getpwnam", return_value=fake_pwd), patch(
                "app.project_paths.grp.getgrnam", return_value=fake_grp
            ), patch("app.project_paths.os.chown") as chown:
                path = ensure_project_root_dir(43)
            self.assertTrue(path.exists())
            chown.assert_called_once_with(path, 1001, 1001)

    def test_resolve_final_export_status_ignores_wrong_rel_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            projects_root = root / "projects"
            wrong_file = projects_root / "project_7" / "exports" / "final.mp4"
            wrong_file.parent.mkdir(parents=True, exist_ok=True)
            wrong_file.write_bytes(b"video")
            fake_settings = SimpleNamespace(data_dir=root)
            asset = SimpleNamespace(rel_path="project_8/exports/final.mp4")
            session = SimpleNamespace(exec=lambda _query: _Rows([asset]))
            with patch("app.api_common.settings", fake_settings):
                out = resolve_final_export_status(session, 7)
        self.assertFalse(out["exists"])

    def test_create_project_fails_when_same_id_storage_leftover_exists(self):
        pack = SimpleNamespace(key="career")
        project = SimpleNamespace(id=None)
        body = ProjectCreateIn(title="测试项目", channel_key="career")
        session = _CreateSession(pack, project)

        def _project_to_out(_session, obj):
            return SimpleNamespace(id=int(obj.id), title=body.title)

        with patch("app.modules.creator.project_mutation_service.validate_render_config", return_value={"aspect": "landscape", "width": 1920, "height": 1080}
        ), patch("app.modules.creator.project_mutation_service.session_scope", return_value=nullcontext(session)), patch(
            "app.modules.creator.project_mutation_service.ensure_project_storage_clean", return_value=["/tmp/project_7"]
        ), patch(
            "app.modules.creator.project_mutation_service.schedule_project_refresh"
        ):
            with self.assertRaises(HTTPException) as ctx:
                create_project_api(_project_to_out, body, normalize_subtitle_settings=lambda cfg: cfg)
        self.assertEqual(ctx.exception.status_code, 500)
        self.assertIn("旧项目残留目录", str(ctx.exception.detail))

    def test_delete_project_fails_when_storage_leftover_exists(self):
        project = SimpleNamespace(id=7)
        session = _DeleteSession(project)
        with patch("app.modules.creator.project_deletion_service.session_scope", side_effect=[nullcontext(session), nullcontext(session)]), patch(
            "app.modules.creator.project_deletion_service.ensure_project_storage_clean", return_value=["/tmp/project_7"]
        ):
            with self.assertRaises(HTTPException) as ctx:
                delete_project_api(7)
        self.assertEqual(ctx.exception.status_code, 500)
        self.assertIn("仍有残留内容未清理", str(ctx.exception.detail))

    def test_delete_project_reports_owner_hint_for_storage_leftover(self):
        project = SimpleNamespace(id=7)
        session = _DeleteSession(project)
        leftover = "/opt/chengpian-workbench/data/projects/project_7/imported/audio [uid=0 gid=0 mode=0o755]"
        with patch("app.modules.creator.project_deletion_service.session_scope", side_effect=[nullcontext(session), nullcontext(session)]), patch(
            "app.modules.creator.project_deletion_service.ensure_project_storage_clean", return_value=[leftover]
        ):
            with self.assertRaises(HTTPException) as ctx:
                delete_project_api(7)
        self.assertEqual(ctx.exception.status_code, 500)
        self.assertIn("uid=0 gid=0", str(ctx.exception.detail))

    def test_collect_project_asset_ids_includes_project_and_scene_bindings(self):
        project = SimpleNamespace(role_image_asset_id=11, voice_asset_id=None, subtitle_asset_id=13)
        scenes = [SimpleNamespace(image_asset_id=99), SimpleNamespace(image_asset_id=None), SimpleNamespace(image_asset_id=101)]
        asset_ids = _collect_project_asset_ids(project, scenes)
        self.assertEqual(asset_ids, {11, 13, 99, 101})

    def test_delete_project_fails_when_db_records_still_remain(self):
        project = SimpleNamespace(id=7, role_image_asset_id=None, voice_asset_id=None, subtitle_asset_id=None)
        lingering_asset = SimpleNamespace(id=12, project_id=7, rel_path="project_7/generated/a.png", kind="image", tag="")
        first_queue = [
            [project],
            [],
            [],
            [],
            [lingering_asset],
            [],
        ]
        second_queue = [
            [project],
            [],
            [],
            [],
            [lingering_asset],
            [],
            [lingering_asset],
            [],
            [],
            [],
            [],
            [],
        ]
        session = _DeleteSessionWithAssets(first_queue, second_queue)

        def _ensure_clean(_project_id, *, extra_file_refs=None):
            session.advance()
            return []

        with patch("app.modules.creator.project_deletion_service.session_scope", side_effect=[nullcontext(session), nullcontext(session)]), patch(
            "app.modules.creator.project_deletion_service.ensure_project_storage_clean", side_effect=_ensure_clean
        ), patch(
            "app.modules.creator.project_deletion_service.project_storage_leftovers", return_value=[]
        ):
            with self.assertRaises(HTTPException) as ctx:
                delete_project_api(7)
        self.assertEqual(ctx.exception.status_code, 500)
        self.assertIn("数据库仍有残留记录", str(ctx.exception.detail))

    def test_delete_project_finalizes_pending_cancelled_active_job_before_delete(self):
        project = SimpleNamespace(id=7, role_image_asset_id=None, voice_asset_id=None, subtitle_asset_id=None)
        job = SimpleNamespace(
            id=15,
            project_id=7,
            status="running",
            cancel_requested=True,
            worker_id="",
            worker_pid=0,
            worker_heartbeat_at=None,
            progress=85,
            message="已取消",
            updated_at=None,
            payload_json="{}",
        )
        session = _DeleteSessionWithPendingCancel(project, job)
        with patch("app.modules.creator.project_deletion_service.session_scope", side_effect=[nullcontext(session), nullcontext(session)]), patch(
            "app.modules.creator.project_deletion_service.ensure_project_storage_clean", return_value=[]
        ), patch(
            "app.modules.creator.project_deletion_service.project_storage_leftovers", return_value=[]
        ), patch(
            "app.modules.creator.project_deletion_service.delete_project_projection"
        ), patch(
            "app.modules.creator.project_deletion_service.delete_job_projections"
        ):
            out = delete_project_api(7)
        self.assertTrue(out.ok)
        self.assertEqual(job.status, "cancelled")


if __name__ == "__main__":
    unittest.main()
