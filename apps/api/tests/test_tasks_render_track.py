import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from app.tasks_render_track import build_silent_video_track


class TasksRenderTrackTests(unittest.TestCase):
    def test_build_silent_video_track_preserves_cancelled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            img = root / 'scene.jpg'
            img.write_bytes(b'img')

            with self.assertRaisesRegex(RuntimeError, 'cancelled'):
                build_silent_video_track(
                    job_id=1,
                    target_job_id=1,
                    project_title='test',
                    scenes=[SimpleNamespace(id=1)],
                    image_paths=[img],
                    base_durs=[2.0],
                    target_w=1280,
                    target_h=720,
                    transition='none',
                    transition_sec=0.0,
                    motion_zoom=0.0,
                    out_dir=root,
                    silent_path=root / 'silent.mp4',
                    on_update=lambda **_kwargs: None,
                    scenes_meta=[{}],
                    wait_if_job_paused=lambda _job_id: None,
                    is_job_cancelled=lambda _job_id: True,
                )

    def test_build_silent_video_track_uses_xfade_for_continue_transition(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            img1 = root / 'scene1.jpg'
            img2 = root / 'scene2.jpg'
            img1.write_bytes(b'img1')
            img2.write_bytes(b'img2')
            ffmpeg_calls: list[list[str]] = []

            def fake_run_ffmpeg(args, timeout_s):
                ffmpeg_calls.append(list(args))
                out_path = Path(args[-1])
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(b'video')

            with patch('app.tasks_render_track.run_ffmpeg', side_effect=fake_run_ffmpeg):
                out = build_silent_video_track(
                    job_id=1,
                    target_job_id=1,
                    project_title='test',
                    scenes=[SimpleNamespace(id=1, meta_json='{}'), SimpleNamespace(id=2, meta_json='{}')],
                    image_paths=[img1, img2],
                    base_durs=[2.0, 2.0],
                    target_w=1280,
                    target_h=720,
                    transition='crossfade',
                    transition_sec=0.24,
                    motion_zoom=0.06,
                    out_dir=root,
                    silent_path=root / 'silent.mp4',
                    on_update=lambda **_kwargs: None,
                    scenes_meta=[{'transition_hint': 'continue'}, {'transition_hint': 'continue'}],
                    wait_if_job_paused=lambda _job_id: None,
                    is_job_cancelled=lambda _job_id: False,
                )

            self.assertTrue(out.exists())
            self.assertTrue(any('-filter_complex' in call for call in ffmpeg_calls[-1:]))
            self.assertIn('xfade=transition=fade', ' '.join(ffmpeg_calls[-1]))

    def test_build_silent_video_track_adds_zoompan_for_images(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            img = root / 'scene.jpg'
            img.write_bytes(b'img')
            ffmpeg_calls: list[list[str]] = []

            def fake_run_ffmpeg(args, timeout_s):
                ffmpeg_calls.append(list(args))
                out_path = Path(args[-1])
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(b'video')

            with patch('app.tasks_render_track.run_ffmpeg', side_effect=fake_run_ffmpeg):
                build_silent_video_track(
                    job_id=1,
                    target_job_id=1,
                    project_title='test',
                    scenes=[SimpleNamespace(id=1, meta_json='{}')],
                    image_paths=[img],
                    base_durs=[2.0],
                    target_w=1280,
                    target_h=720,
                    transition='none',
                    transition_sec=0.0,
                    motion_zoom=0.08,
                    out_dir=root,
                    silent_path=root / 'silent.mp4',
                    on_update=lambda **_kwargs: None,
                    scenes_meta=[{'transition_hint': 'continue'}],
                    wait_if_job_paused=lambda _job_id: None,
                    is_job_cancelled=lambda _job_id: False,
                )

            render_call = ffmpeg_calls[0]
            self.assertIn('zoompan=', ' '.join(render_call))


if __name__ == '__main__':
    unittest.main()
