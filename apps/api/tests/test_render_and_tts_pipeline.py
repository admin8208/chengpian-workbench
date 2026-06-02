import json
import tempfile
import types
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.models import Asset
from app.tasks_render import finalize_render_outputs


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)

    def first(self):
        rows = list(self._rows)
        return rows[0] if rows else None


class _FakeSession:
    def __init__(self):
        self.added: list[object] = []
        self.deleted: list[object] = []

    def exec(self, _query):
        return _Rows([])

    def add(self, obj):
        self.added.append(obj)

    def delete(self, obj):
        self.deleted.append(obj)


class _FakeAudioClip:
    def __init__(self, _path: str):
        self.duration = 6.0

    def close(self):
        return None


class _RowsOneShot:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)

    def first(self):
        rows = list(self._rows)
        return rows[0] if rows else None


class RenderAndTtsPipelineTests(unittest.TestCase):
    def test_tasks_tts_pipeline_imports_without_circular_dependency(self):
        from app.tasks_tts_pipeline import prepare_audio_and_subtitles

        self.assertTrue(callable(prepare_audio_and_subtitles))

    def test_finalize_render_outputs_persists_candidate_with_cleanup_warning(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            assets_dir = root / "assets"
            exports_dir = root / "exports"
            out_dir = exports_dir / "project_7" / "candidates"
            out_dir.mkdir(parents=True, exist_ok=True)
            audio_path = assets_dir / "audio" / "project_7" / "voice.mp3"
            audio_path.parent.mkdir(parents=True, exist_ok=True)
            audio_path.write_bytes(b"audio")
            srt_path = assets_dir / "subtitles" / "project_7" / "subtitle.srt"
            srt_path.parent.mkdir(parents=True, exist_ok=True)
            srt_path.write_text("1\n00:00:00,000 --> 00:00:02,000\n你好\n", encoding="utf-8")
            out_tmp = out_dir / "preview_tmp.mp4"
            out_tmp.write_bytes(b"video")
            out_file = out_dir / "preview.mp4"

            fake_session = _FakeSession()
            fake_settings = SimpleNamespace(assets_dir=assets_dir, exports_dir=exports_dir)
            real_replace = Path.replace

            def _replace_with_failure(self, target):
                if self == out_tmp:
                    raise RuntimeError("disk busy")
                return real_replace(self, target)

            def _fake_rel_to_projects_root(path: Path) -> str:
                return str(path.name)

            with patch("app.tasks_render.settings", fake_settings), patch(
                "app.tasks_render.session_scope", return_value=nullcontext(fake_session)
            ), patch("pathlib.Path.replace", _replace_with_failure), patch(
                "app.tasks_render.rel_to_projects_root", side_effect=_fake_rel_to_projects_root
            ):
                final_path, history_path = finalize_render_outputs(
                    pid=7,
                    tag="export_candidate",
                    ts="20260427_100000",
                    out_dir=out_dir,
                    out_file=out_file,
                    out_tmp=out_tmp,
                    audio_path=audio_path,
                    srt_path=srt_path,
                    candidate_batch_id="batch-7",
                    render_job_id=88,
                    render_token="token-1",
                    render_meta={"width": 1280},
                    is_generated_render_rel_path=lambda _pid, _rel: True,
                    cleanup_project_intermediate_artifacts=lambda _pid: {"ok": True},
                )

            self.assertEqual(final_path, out_tmp)
            self.assertIsNone(history_path)
            video_assets = [x for x in fake_session.added if isinstance(x, Asset) and x.kind == "video"]
            self.assertEqual(len(video_assets), 1)
            meta = json.loads(video_assets[0].meta_json)
            self.assertEqual(meta["render_job_id"], 88)
            self.assertEqual(meta["render_token"], "token-1")
            self.assertEqual(meta["width"], 1280)
            self.assertTrue(meta.get("cleanup_warnings"))
            self.assertIn("replace fallback", meta["cleanup_warnings"][0])

    def test_prepare_audio_and_subtitles_rebuilds_bad_uploaded_subtitle(self):
        from app.tasks_tts_pipeline import prepare_audio_and_subtitles
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            assets_dir = root / "assets"
            assets_dir.mkdir(parents=True, exist_ok=True)
            fake_settings = SimpleNamespace(assets_dir=assets_dir)
            audio_path = assets_dir / "audio" / "project_9" / "voice.mp3"
            srt_path = assets_dir / "subtitles" / "project_9" / "uploaded.srt"
            srt_path.parent.mkdir(parents=True, exist_ok=True)
            srt_path.write_text("1\n00:00:00,000 --> 00:00:00,100\n坏\n", encoding="utf-8")

            def _write_silent_audio(path: Path, *, duration_sec: float):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(f"audio:{duration_sec}".encode("utf-8"))

            fake_moviepy = types.SimpleNamespace(AudioFileClip=_FakeAudioClip)
            patch_calls: list[dict] = []
            updates: list[str] = []
            scenes = [
                SimpleNamespace(idx=1, narration="第一句旁白"),
                SimpleNamespace(idx=2, narration="第二句旁白"),
            ]

            with patch("app.tasks_tts_pipeline.settings", fake_settings), patch(
                "app.tasks_tts_pipeline.ensure_silent_voice_mp3", _write_silent_audio
            ), patch("app.tasks_tts_pipeline.wait_if_job_paused", lambda _job_id: None), patch(
                "app.tasks_tts_pipeline.is_job_cancelled", return_value=False
            ), patch("app.tasks_tts_pipeline.patch_job_payload", side_effect=lambda _job_id, patch: patch_calls.append(dict(patch))), patch.dict(
                "sys.modules", {"moviepy": fake_moviepy}
            ):
                result = prepare_audio_and_subtitles(
                    job_id=91,
                    target_job_id=91,
                    pid=9,
                    project=SimpleNamespace(title="测试项目", channel_key="career"),
                    scenes=scenes,
                    script_text="第一句旁白 第二句旁白",
                    audio_path=audio_path,
                    srt_path=srt_path,
                    has_voice_upload=False,
                    has_subtitle_upload=True,
                    require_tts=True,
                    planned_duration=6.0,
                    base_durs=[3.0, 3.0],
                    voice_name="voice",
                    voice_rate="+0%",
                    reuse_generated_tts=False,
                    temp_file_prefix="job91",
                    on_update=lambda **kwargs: updates.append(str(kwargs.get("message") or "")),
                    friendly_tts_failure_message=lambda msg: msg,
                    subtitle_has_visible_cues=lambda p: "-->" in p.read_text(encoding="utf-8", errors="ignore"),
                )

            self.assertEqual(result.tts_backend_used, "上传字幕（静音音轨）")
            self.assertNotEqual(result.srt_path, srt_path)
            self.assertTrue(result.srt_path.exists())
            rebuilt = result.srt_path.read_text(encoding="utf-8")
            self.assertIn("第一句旁白", rebuilt)
            self.assertIn("第二句旁白", rebuilt)
            self.assertTrue(any("自动重建字幕" in msg for msg in updates))
            self.assertIn({"render_substage": "tts_prepare"}, patch_calls)
            self.assertIn({"tts_done": True, "render_substage": "tts_ready"}, patch_calls)

    def test_prepare_audio_and_subtitles_tts_failure_raises_instead_of_silent_fallback(self):
        from app.tasks_tts_pipeline import prepare_audio_and_subtitles
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            assets_dir = root / "assets"
            assets_dir.mkdir(parents=True, exist_ok=True)
            fake_settings = SimpleNamespace(assets_dir=assets_dir)
            audio_path = assets_dir / "audio" / "project_10" / "voice.mp3"
            srt_path = assets_dir / "subtitles" / "project_10" / "voice.srt"

            fake_moviepy = types.SimpleNamespace(AudioFileClip=_FakeAudioClip)
            scenes = [SimpleNamespace(idx=1, narration="第一句旁白", meta_json="{}")]
            fake_session = SimpleNamespace(exec=lambda _query: _RowsOneShot(scenes))

            def _raise_timeout(*_args, **_kwargs):
                raise RuntimeError("edge timeout")

            with patch("app.tasks_tts_pipeline.settings", fake_settings), patch(
                "app.tasks_tts_pipeline.wait_if_job_paused", lambda _job_id: None
            ), patch("app.tasks_tts_pipeline.is_job_cancelled", return_value=False), patch(
                "app.tasks_tts_pipeline.session_scope", return_value=nullcontext(fake_session)
            ), patch.dict("sys.modules", {"moviepy": fake_moviepy}), patch(
                "app.modules.tts.service.edge_synthesis_probe_cached", return_value=(True, "ok", True)
            ), patch("app.modules.tts.service.get_tts_backend", return_value="edge"), patch(
                "app.modules.tts.service.get_offline_voice_id", return_value="zh_CN-huayan-medium"
            ), patch("app.modules.tts.smart.smart_tts_generate", side_effect=_raise_timeout):
                with self.assertRaises(RuntimeError) as ctx:
                    prepare_audio_and_subtitles(
                        job_id=92,
                        target_job_id=92,
                        pid=10,
                        project=SimpleNamespace(title="测试项目", channel_key="career"),
                        scenes=scenes,
                        script_text="第一句旁白",
                        audio_path=audio_path,
                        srt_path=srt_path,
                        has_voice_upload=False,
                        has_subtitle_upload=False,
                        require_tts=False,
                        planned_duration=6.0,
                        base_durs=[6.0],
                        voice_name="voice",
                        voice_rate="+0%",
                        reuse_generated_tts=False,
                        temp_file_prefix="job92",
                        on_update=lambda **_kwargs: None,
                        friendly_tts_failure_message=lambda msg: f"友好提示：{msg}",
                        subtitle_has_visible_cues=lambda p: p.exists(),
                    )

            self.assertIn("友好提示：edge timeout", str(ctx.exception))
            self.assertFalse(audio_path.exists())

    def test_prepare_audio_and_subtitles_uses_uploaded_audio_without_tts(self):
        from app.tasks_tts_pipeline import prepare_audio_and_subtitles
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            audio_path = root / "uploaded.mp3"
            srt_path = root / "uploaded.srt"
            audio_path.write_bytes(b"uploaded audio")
            srt_path.write_text("1\n00:00:00,000 --> 00:00:03,000\n原始语音\n\n2\n00:00:03,000 --> 00:00:06,000\n文案\n", encoding="utf-8")
            fake_moviepy = types.SimpleNamespace(AudioFileClip=_FakeAudioClip)
            scenes = [SimpleNamespace(idx=1, narration="原始语音文案", meta_json="{}")]

            with patch("app.tasks_tts_pipeline.wait_if_job_paused", lambda _job_id: None), patch(
                "app.tasks_tts_pipeline.is_job_cancelled", return_value=False
            ), patch.dict("sys.modules", {"moviepy": fake_moviepy}), patch(
                "app.modules.tts.smart.smart_tts_generate", side_effect=AssertionError("不应调用 TTS")
            ):
                result = prepare_audio_and_subtitles(
                    job_id=93,
                    target_job_id=93,
                    pid=11,
                    project=SimpleNamespace(title="音频项目", channel_key="career"),
                    scenes=scenes,
                    script_text="原始语音文案",
                    audio_path=audio_path,
                    srt_path=srt_path,
                    has_voice_upload=True,
                    has_subtitle_upload=True,
                    require_tts=True,
                    planned_duration=4.0,
                    base_durs=[4.0],
                    voice_name="voice",
                    voice_rate="+0%",
                    reuse_generated_tts=False,
                    temp_file_prefix="job93",
                    on_update=lambda **_kwargs: None,
                    friendly_tts_failure_message=lambda msg: msg,
                    subtitle_has_visible_cues=lambda p: "-->" in p.read_text(encoding="utf-8", errors="ignore"),
                )

            self.assertEqual(result.audio_path, audio_path)
            self.assertEqual(result.srt_path, srt_path)
            self.assertEqual(result.audio_duration, 6.0)


if __name__ == "__main__":
    unittest.main()
