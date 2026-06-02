import tempfile
import types
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.tasks_render_prepare import RenderPreparation, RenderProjectSnapshot, RenderSceneSnapshot
from app.tasks_render_runtime import render_video_impl_runtime


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def first(self):
        rows = list(self._rows)
        return rows[0] if rows else None


class _Session:
    def __init__(self, asset):
        self.asset = asset
        self.closed = False

    def exec(self, _query):
        if self.closed:
            raise AssertionError("render runtime used session after it was closed")
        return _Rows([self.asset])


class TasksRenderRuntimeTests(unittest.TestCase):
    def test_runtime_closes_db_session_before_long_render_steps(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            image_path = root / "image.jpg"
            image_path.write_bytes(b"image")
            audio_dir = root / "audio"
            subtitle_dir = root / "subtitles"
            export_dir = root / "exports"
            asset = SimpleNamespace(rel_path="image.jpg")
            fake_session = _Session(asset)
            long_steps_saw_closed_session: list[str] = []

            @contextmanager
            def session_scope():
                try:
                    yield fake_session
                finally:
                    fake_session.closed = True

            def prepare_render_context(**kwargs):
                self.assertIs(kwargs["session"], fake_session)
                self.assertFalse(fake_session.closed)
                return RenderPreparation(
                    project=RenderProjectSnapshot(
                        id=7,
                        title="测试项目",
                        workflow="mix",
                        channel_key="career",
                        script="第一句旁白",
                        voice_asset_id=None,
                        subtitle_asset_id=None,
                    ),
                    pid=7,
                    wf="mix",
                    pack=SimpleNamespace(),
                    cfg={},
                    rcfg={"material_mode": "network"},
                    scenes=[RenderSceneSnapshot(id=11, idx=1, narration="第一句旁白", duration_sec=2.0, image_asset_id=3, meta_json="{}")],
                    voice_name="voice",
                    voice_rate="+0%",
                    voice_volume=1.0,
                    subtitle_style="boxed",
                    subtitle_overrides={},
                    target_w=1280,
                    target_h=720,
                    aspect="landscape",
                    transition="none",
                    transition_sec=0.0,
                    motion_zoom=0.0,
                )

            def prepare_audio_and_subtitles(**kwargs):
                self.assertTrue(fake_session.closed)
                long_steps_saw_closed_session.append("tts")
                kwargs["audio_path"].parent.mkdir(parents=True, exist_ok=True)
                kwargs["srt_path"].parent.mkdir(parents=True, exist_ok=True)
                kwargs["audio_path"].write_bytes(b"audio")
                kwargs["srt_path"].write_text("1\n00:00:00,000 --> 00:00:02,000\n第一句旁白\n", encoding="utf-8")
                return SimpleNamespace(audio_path=kwargs["audio_path"], srt_path=kwargs["srt_path"], base_durs=kwargs["base_durs"], tts_backend_used="fake")

            def build_silent_video_track(**kwargs):
                self.assertTrue(fake_session.closed)
                long_steps_saw_closed_session.append("silent")
                kwargs["silent_path"].parent.mkdir(parents=True, exist_ok=True)
                kwargs["silent_path"].write_bytes(b"silent")
                return kwargs["silent_path"]

            def run_ffmpeg_mux_with_fallback(args, **_kwargs):
                self.assertTrue(fake_session.closed)
                long_steps_saw_closed_session.append("mux")
                out_tmp = Path(args[-1])
                out_tmp.parent.mkdir(parents=True, exist_ok=True)
                out_tmp.write_bytes(b"video")
                return {"width": 1280, "height": 720}

            def finalize_render_output_bundle(**kwargs):
                self.assertTrue(fake_session.closed)
                long_steps_saw_closed_session.append("finalize")
                return kwargs["out_file"], None

            fake_moviepy = types.SimpleNamespace(AudioFileClip=object, ImageClip=object, VideoFileClip=object, concatenate_videoclips=lambda *_args, **_kwargs: None, vfx=object())
            with patch.dict("sys.modules", {"moviepy": fake_moviepy}):
                render_video_impl_runtime(
                    5,
                    7,
                    abort_if_job_cancelled=lambda _job_id: False,
                    now_utc=lambda: SimpleNamespace(strftime=lambda _fmt: "20260101_000000_000000"),
                    update_job=lambda *_args, **_kwargs: None,
                    patch_job_payload=lambda *_args, **_kwargs: None,
                    render_queue_manager=SimpleNamespace(can_start_render=lambda **_kwargs: True),
                    is_job_cancelled=lambda _job_id: False,
                    wait_if_job_paused=lambda _job_id: None,
                    session_scope=session_scope,
                    prepare_render_context=prepare_render_context,
                    get_pack_impl=lambda *_args, **_kwargs: None,
                    get_edge_voice_id=lambda *_args, **_kwargs: None,
                    get_default_voice_rate=lambda *_args, **_kwargs: None,
                    project_material_mode=lambda _project, render_cfg=None: str((render_cfg or {}).get("material_mode") or "network"),
                    scene_binding_material_mode=lambda _scene: None,
                    material_mode_label=lambda mode: mode,
                    update_job_in_session=lambda *_args, **_kwargs: None,
                    asset_disk_path=lambda rel_path, **_kwargs: root / rel_path,
                    project_exports_dir=lambda _pid: export_dir,
                    clean_tts_text=lambda text: text,
                    stable_digest=lambda _parts: "cachekey",
                    project_audio_dir=lambda _pid: audio_dir,
                    project_subtitles_dir=lambda _pid: subtitle_dir,
                    prepare_audio_and_subtitles=prepare_audio_and_subtitles,
                    humanize_render_error=lambda msg: msg,
                    build_silent_video_track=build_silent_video_track,
                    build_output_paths=lambda out_dir, export_tag, ts: SimpleNamespace(out_file=out_dir / f"{export_tag}_{ts}.mp4", out_tmp=out_dir / f"{export_tag}_{ts}_tmp.mp4"),
                    prepare_subtitle_filters_impl=lambda *_args, **_kwargs: ("vf", "vf_retry"),
                    build_mux_plan=lambda **kwargs: SimpleNamespace(args=["ffmpeg", str(kwargs["out_tmp"])]),
                    run_ffmpeg_mux_with_fallback_impl=run_ffmpeg_mux_with_fallback,
                    extend_mux_meta=lambda **kwargs: kwargs["mux_meta"],
                    finalize_render_output_bundle=finalize_render_output_bundle,
                    finalize_render_outputs=lambda **_kwargs: None,
                    mark_project_ready_if_export=lambda **_kwargs: None,
                    project_model=object,
                    cleanup_non_cached_silent_track=lambda _path: None,
                )

            self.assertEqual(long_steps_saw_closed_session, ["tts", "silent", "mux", "finalize"])

    def test_runtime_requires_existing_tts_when_requested(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            image_path = root / "image.jpg"
            image_path.write_bytes(b"image")
            fake_session = _Session(SimpleNamespace(rel_path="image.jpg"))

            @contextmanager
            def session_scope():
                yield fake_session

            def prepare_render_context(**_kwargs):
                return RenderPreparation(
                    project=RenderProjectSnapshot(id=7, title="测试项目", workflow="mix", channel_key="career", script="第一句旁白", voice_asset_id=None, subtitle_asset_id=None),
                    pid=7,
                    wf="mix",
                    pack=SimpleNamespace(),
                    cfg={},
                    rcfg={"material_mode": "network"},
                    scenes=[RenderSceneSnapshot(id=11, idx=1, narration="第一句旁白", duration_sec=2.0, image_asset_id=3, meta_json="{}")],
                    voice_name="voice",
                    voice_rate="+0%",
                    voice_volume=1.0,
                    subtitle_style="boxed",
                    subtitle_overrides={},
                    target_w=1280,
                    target_h=720,
                    aspect="landscape",
                    transition="none",
                    transition_sec=0.0,
                    motion_zoom=0.0,
                )

            updates: list[str] = []
            render_video_impl_runtime(
                5,
                7,
                require_existing_tts=True,
                abort_if_job_cancelled=lambda _job_id: False,
                now_utc=lambda: SimpleNamespace(strftime=lambda _fmt: "20260101_000000_000000"),
                update_job=lambda *_args, **kwargs: updates.append(str(kwargs.get("message") or "")),
                patch_job_payload=lambda *_args, **_kwargs: None,
                render_queue_manager=SimpleNamespace(can_start_render=lambda **_kwargs: True),
                is_job_cancelled=lambda _job_id: False,
                wait_if_job_paused=lambda _job_id: None,
                session_scope=session_scope,
                prepare_render_context=prepare_render_context,
                get_pack_impl=lambda *_args, **_kwargs: None,
                get_edge_voice_id=lambda *_args, **_kwargs: None,
                get_default_voice_rate=lambda *_args, **_kwargs: None,
                project_material_mode=lambda _project, render_cfg=None: str((render_cfg or {}).get("material_mode") or "network"),
                scene_binding_material_mode=lambda _scene: None,
                material_mode_label=lambda mode: mode,
                update_job_in_session=lambda _session, _job_id, **kwargs: updates.append(str(kwargs.get("message") or "")),
                asset_disk_path=lambda rel_path, **_kwargs: root / rel_path,
                project_exports_dir=lambda _pid: root / "exports",
                clean_tts_text=lambda text: text,
                stable_digest=lambda _parts: "cachekey",
                project_audio_dir=lambda _pid: root / "audio",
                project_subtitles_dir=lambda _pid: root / "subtitles",
                prepare_audio_and_subtitles=lambda **_kwargs: None,
                humanize_render_error=lambda msg: msg,
                build_silent_video_track=lambda **_kwargs: None,
                build_output_paths=lambda **_kwargs: None,
                prepare_subtitle_filters_impl=lambda *_args, **_kwargs: ("vf", "vf_retry"),
                build_mux_plan=lambda **_kwargs: None,
                run_ffmpeg_mux_with_fallback_impl=lambda *_args, **_kwargs: None,
                extend_mux_meta=lambda **kwargs: kwargs.get("mux_meta"),
                finalize_render_output_bundle=lambda **_kwargs: None,
                finalize_render_outputs=lambda **_kwargs: None,
                mark_project_ready_if_export=lambda **_kwargs: None,
                project_model=object,
                cleanup_non_cached_silent_track=lambda _path: None,
            )
            self.assertTrue(any("缺少已生成的配音/字幕产物" in msg for msg in updates))

    def test_runtime_rebuilds_cached_silent_track_when_shorter_than_audio(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            image_path = root / "image.jpg"
            image_path.write_bytes(b"image")
            audio_dir = root / "audio"
            subtitle_dir = root / "subtitles"
            export_dir = root / "exports"
            cached = export_dir / "silent_cache_cachekey.mp4"
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_bytes(b"old silent")
            fake_session = _Session(SimpleNamespace(rel_path="image.jpg"))
            built: list[str] = []

            @contextmanager
            def session_scope():
                yield fake_session

            def prepare_render_context(**_kwargs):
                return RenderPreparation(
                    project=RenderProjectSnapshot(id=7, title="测试项目", workflow="mix", channel_key="career", script="第一句旁白", voice_asset_id=None, subtitle_asset_id=None),
                    pid=7,
                    wf="mix",
                    pack=SimpleNamespace(),
                    cfg={},
                    rcfg={"material_mode": "network"},
                    scenes=[RenderSceneSnapshot(id=11, idx=1, narration="第一句旁白", duration_sec=2.0, image_asset_id=3, meta_json="{}")],
                    voice_name="voice",
                    voice_rate="+0%",
                    voice_volume=1.0,
                    subtitle_style="boxed",
                    subtitle_overrides={},
                    target_w=1280,
                    target_h=720,
                    aspect="landscape",
                    transition="none",
                    transition_sec=0.0,
                    motion_zoom=0.0,
                )

            def prepare_audio_and_subtitles(**kwargs):
                kwargs["audio_path"].parent.mkdir(parents=True, exist_ok=True)
                kwargs["srt_path"].parent.mkdir(parents=True, exist_ok=True)
                kwargs["audio_path"].write_bytes(b"audio")
                kwargs["srt_path"].write_text("1\n00:00:00,000 --> 00:00:06,000\n第一句旁白\n", encoding="utf-8")
                return SimpleNamespace(audio_path=kwargs["audio_path"], srt_path=kwargs["srt_path"], base_durs=[6.0], tts_backend_used="fake")

            def build_silent_video_track(**kwargs):
                built.append("silent")
                kwargs["silent_path"].write_bytes(b"new silent")
                return kwargs["silent_path"]

            def run_ffmpeg_mux_with_fallback(args, **_kwargs):
                out = Path(args[-1])
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(b"video")
                return {}

            class FakeAudioClip:
                def __init__(self, _path):
                    self.duration = 6.0
                def close(self):
                    pass

            class FakeVideoClip:
                def __init__(self, _path):
                    self.duration = 2.0 if not built else 6.0
                def close(self):
                    pass

            fake_moviepy = types.SimpleNamespace(AudioFileClip=FakeAudioClip, ImageClip=object, VideoFileClip=FakeVideoClip, concatenate_videoclips=lambda *_args, **_kwargs: None, vfx=object())
            with patch.dict("sys.modules", {"moviepy": fake_moviepy}):
                render_video_impl_runtime(
                    5,
                    7,
                    abort_if_job_cancelled=lambda _job_id: False,
                    now_utc=lambda: SimpleNamespace(strftime=lambda _fmt: "20260101_000000_000000"),
                    update_job=lambda *_args, **_kwargs: None,
                    patch_job_payload=lambda *_args, **_kwargs: None,
                    render_queue_manager=SimpleNamespace(can_start_render=lambda **_kwargs: True),
                    is_job_cancelled=lambda _job_id: False,
                    wait_if_job_paused=lambda _job_id: None,
                    session_scope=session_scope,
                    prepare_render_context=prepare_render_context,
                    get_pack_impl=lambda *_args, **_kwargs: None,
                    get_edge_voice_id=lambda *_args, **_kwargs: None,
                    get_default_voice_rate=lambda *_args, **_kwargs: None,
                    project_material_mode=lambda _project, render_cfg=None: str((render_cfg or {}).get("material_mode") or "network"),
                    scene_binding_material_mode=lambda _scene: None,
                    material_mode_label=lambda mode: mode,
                    update_job_in_session=lambda *_args, **_kwargs: None,
                    asset_disk_path=lambda rel_path, **_kwargs: root / rel_path,
                    project_exports_dir=lambda _pid: export_dir,
                    clean_tts_text=lambda text: text,
                    stable_digest=lambda _parts: "cachekey",
                    project_audio_dir=lambda _pid: audio_dir,
                    project_subtitles_dir=lambda _pid: subtitle_dir,
                    prepare_audio_and_subtitles=prepare_audio_and_subtitles,
                    humanize_render_error=lambda msg: msg,
                    build_silent_video_track=build_silent_video_track,
                    build_output_paths=lambda out_dir, export_tag, ts: SimpleNamespace(out_file=out_dir / f"{export_tag}_{ts}.mp4", out_tmp=out_dir / f"{export_tag}_{ts}_tmp.mp4"),
                    prepare_subtitle_filters_impl=lambda *_args, **_kwargs: ("vf", "vf_retry"),
                    build_mux_plan=lambda **kwargs: SimpleNamespace(args=["ffmpeg", str(kwargs["out_tmp"])]),
                    run_ffmpeg_mux_with_fallback_impl=run_ffmpeg_mux_with_fallback,
                    extend_mux_meta=lambda **kwargs: kwargs["mux_meta"],
                    finalize_render_output_bundle=lambda **kwargs: (kwargs["out_file"].write_bytes(b"final") or (kwargs["out_file"], None)),
                    finalize_render_outputs=lambda **_kwargs: None,
                    mark_project_ready_if_export=lambda **_kwargs: None,
                    project_model=object,
                    cleanup_non_cached_silent_track=lambda _path: None,
                )

            self.assertEqual(built, ["silent"])

    def test_runtime_blocks_mux_when_silent_track_shorter_than_audio(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            image_path = root / "image.jpg"
            image_path.write_bytes(b"image")
            audio_dir = root / "audio"
            subtitle_dir = root / "subtitles"
            export_dir = root / "exports"
            fake_session = _Session(SimpleNamespace(rel_path="image.jpg"))
            updates: list[str] = []
            mux_called: list[str] = []

            @contextmanager
            def session_scope():
                yield fake_session

            def prepare_render_context(**_kwargs):
                return RenderPreparation(
                    project=RenderProjectSnapshot(id=7, title="测试项目", workflow="mix", channel_key="career", script="第一句旁白", voice_asset_id=None, subtitle_asset_id=None),
                    pid=7,
                    wf="mix",
                    pack=SimpleNamespace(),
                    cfg={},
                    rcfg={"material_mode": "network"},
                    scenes=[RenderSceneSnapshot(id=11, idx=1, narration="第一句旁白", duration_sec=2.0, image_asset_id=3, meta_json="{}")],
                    voice_name="voice",
                    voice_rate="+0%",
                    voice_volume=1.0,
                    subtitle_style="boxed",
                    subtitle_overrides={},
                    target_w=1280,
                    target_h=720,
                    aspect="landscape",
                    transition="none",
                    transition_sec=0.0,
                    motion_zoom=0.0,
                )

            def prepare_audio_and_subtitles(**kwargs):
                kwargs["audio_path"].parent.mkdir(parents=True, exist_ok=True)
                kwargs["srt_path"].parent.mkdir(parents=True, exist_ok=True)
                kwargs["audio_path"].write_bytes(b"audio")
                kwargs["srt_path"].write_text("1\n00:00:00,000 --> 00:00:08,000\n第一句旁白\n", encoding="utf-8")
                return SimpleNamespace(audio_path=kwargs["audio_path"], srt_path=kwargs["srt_path"], base_durs=[8.0], tts_backend_used="fake")

            def build_silent_video_track(**kwargs):
                kwargs["silent_path"].parent.mkdir(parents=True, exist_ok=True)
                kwargs["silent_path"].write_bytes(b"short silent")
                return kwargs["silent_path"]

            class FakeAudioClip:
                def __init__(self, _path):
                    self.duration = 8.0
                def close(self):
                    pass

            class FakeVideoClip:
                def __init__(self, _path):
                    self.duration = 3.0
                def close(self):
                    pass

            fake_moviepy = types.SimpleNamespace(AudioFileClip=FakeAudioClip, ImageClip=object, VideoFileClip=FakeVideoClip, concatenate_videoclips=lambda *_args, **_kwargs: None, vfx=object())
            with patch.dict("sys.modules", {"moviepy": fake_moviepy}):
                render_video_impl_runtime(
                    5,
                    7,
                    abort_if_job_cancelled=lambda _job_id: False,
                    now_utc=lambda: SimpleNamespace(strftime=lambda _fmt: "20260101_000000_000000"),
                    update_job=lambda *_args, **kwargs: updates.append(str(kwargs.get("message") or "")),
                    patch_job_payload=lambda *_args, **_kwargs: None,
                    render_queue_manager=SimpleNamespace(can_start_render=lambda **_kwargs: True),
                    is_job_cancelled=lambda _job_id: False,
                    wait_if_job_paused=lambda _job_id: None,
                    session_scope=session_scope,
                    prepare_render_context=prepare_render_context,
                    get_pack_impl=lambda *_args, **_kwargs: None,
                    get_edge_voice_id=lambda *_args, **_kwargs: None,
                    get_default_voice_rate=lambda *_args, **_kwargs: None,
                    project_material_mode=lambda _project, render_cfg=None: str((render_cfg or {}).get("material_mode") or "network"),
                    scene_binding_material_mode=lambda _scene: None,
                    material_mode_label=lambda mode: mode,
                    update_job_in_session=lambda *_args, **_kwargs: None,
                    asset_disk_path=lambda rel_path, **_kwargs: root / rel_path,
                    project_exports_dir=lambda _pid: export_dir,
                    clean_tts_text=lambda text: text,
                    stable_digest=lambda _parts: "cachekey2",
                    project_audio_dir=lambda _pid: audio_dir,
                    project_subtitles_dir=lambda _pid: subtitle_dir,
                    prepare_audio_and_subtitles=prepare_audio_and_subtitles,
                    humanize_render_error=lambda msg: msg,
                    build_silent_video_track=build_silent_video_track,
                    build_output_paths=lambda out_dir, export_tag, ts: SimpleNamespace(out_file=out_dir / f"{export_tag}_{ts}.mp4", out_tmp=out_dir / f"{export_tag}_{ts}_tmp.mp4"),
                    prepare_subtitle_filters_impl=lambda *_args, **_kwargs: ("vf", "vf_retry"),
                    build_mux_plan=lambda **kwargs: SimpleNamespace(args=["ffmpeg", str(kwargs["out_tmp"])]),
                    run_ffmpeg_mux_with_fallback_impl=lambda *_args, **_kwargs: mux_called.append("mux"),
                    extend_mux_meta=lambda **kwargs: kwargs["mux_meta"],
                    finalize_render_output_bundle=lambda **_kwargs: None,
                    finalize_render_outputs=lambda **_kwargs: None,
                    mark_project_ready_if_export=lambda **_kwargs: None,
                    project_model=object,
                    cleanup_non_cached_silent_track=lambda _path: None,
                )

            self.assertEqual(mux_called, [])
            self.assertTrue(any("视频轨短于主音频时间轴" in msg for msg in updates))


if __name__ == "__main__":
    unittest.main()
