import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app.api.cloud import CloudImportIn, import_from_cloud
from app.modules.cloud.onedrive_client import OneDriveClient


class _Session:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        for idx, obj in enumerate(self.added, start=1):
            if getattr(obj, "id", None) is None:
                obj.id = idx

    def refresh(self, _obj):
        return None


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def _write_download(file_id, local_path):
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(str(file_id).encode("utf-8"))
    return True


class CloudRouterTests(unittest.TestCase):
    def test_import_from_cloud_rejects_video_kind_for_non_video_extension(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_settings = SimpleNamespace(assets_dir=Path(tmpdir) / "assets")
            with patch("app.api.cloud.settings", fake_settings), patch("app.api.cloud._get_client"):
                with self.assertRaises(HTTPException) as ctx:
                    import_from_cloud(
                        CloudImportIn(
                            storage_type="webdav",
                            config={"url": "https://dav.example.com"},
                            remote_path="/docs/readme.txt",
                            file_id="",
                            kind="video",
                        )
                    )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("当前视频素材页只允许导入视频文件", str(ctx.exception.detail))

    def test_import_from_cloud_onedrive_uses_file_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            assets_dir = Path(tmpdir) / "assets"
            fake_settings = SimpleNamespace(assets_dir=assets_dir)
            client = SimpleNamespace(download_file=_write_download)
            session = _Session()
            with patch("app.api.cloud.settings", fake_settings), patch("app.api.cloud._get_client", return_value=client), patch(
                "app.api.cloud.session_scope", return_value=nullcontext(session)
            ):
                out = import_from_cloud(
                    CloudImportIn(
                        storage_type="onedrive",
                        config={"access_token": "token"},
                        remote_path="/videos/demo.mp4",
                        file_id="onedrive-file-7",
                        kind="video",
                    )
                )
        self.assertTrue(out.success)
        self.assertEqual(out.asset_id, 1)
        self.assertEqual(len(session.added), 1)
        self.assertEqual(session.added[0].kind, "video")
        self.assertIn("videos/demo.mp4", str(session.added[0].meta_json))


class OneDriveClientTests(unittest.TestCase):
    def test_list_files_maps_id_to_file_id(self):
        client = OneDriveClient("token")
        payload = {
            "value": [
                {
                    "id": "item-1",
                    "name": "demo.mp4",
                    "size": 12,
                    "file": {"mimeType": "video/mp4"},
                    "lastModifiedDateTime": "2026-05-03T00:00:00Z",
                }
            ]
        }
        with patch.object(client.session, "get", return_value=_FakeResponse(payload, status_code=200)):
            out = client.list_files("/")
        self.assertEqual(out[0]["id"], "item-1")
        self.assertEqual(out[0]["file_id"], "item-1")
        self.assertEqual(out[0]["type"], "video")


if __name__ == "__main__":
    unittest.main()
