import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.modules.tts.smart import smart_tts_generate
from app.modules.tts.smart_runtime import _ensure_wav
from app.modules.tts.smart_types import SmartTtsSegment
from app.tasks_render_compose import build_mux_plan


class TtsFixedRateTests(unittest.TestCase):
    def test_smart_tts_generate_uses_single_global_rate_for_all_segments(self):
        captured_rates: list[str] = []

        def _fake_ensure_wav(**kwargs):
            captured_rates.append(str(kwargs["rate"]))
            out_wav = Path(kwargs["out_wav"])
            out_wav.parent.mkdir(parents=True, exist_ok=True)
            out_wav.write_bytes(b"wav")

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            audio_path = root / "out.mp3"
            srt_path = root / "out.srt"
            segs = [
                SmartTtsSegment(scene_idx=1, speaker="旁白", text="第一句", pace="very_fast", emotion="excited"),
                SmartTtsSegment(scene_idx=2, speaker="旁白", text="第二句", pace="very_slow", emotion="sad"),
            ]
            with patch("app.modules.tts.smart.resolve_llm_cfg", return_value=None), patch(
                "app.modules.tts.smart._fallback_segments", return_value=segs
            ), patch("app.modules.tts.smart._ensure_wav", side_effect=_fake_ensure_wav), patch(
                "app.modules.tts.smart._wav_duration_sec", return_value=1.0
            ), patch("app.modules.tts.smart.run_ffmpeg", side_effect=lambda args: Path(args[-1]).write_bytes(b"mp3")):
                smart_tts_generate(
                    project_title="测试项目",
                    scenes=[(1, "第一句"), (2, "第二句")],
                    scene_meta_json=["{}", "{}"],
                    backend="edge",
                    offline_voice_id="zh_CN-huayan-medium",
                    edge_voice_default="zh-CN-XiaoxiaoNeural",
                    edge_rate_default="+7%",
                    audio_path=audio_path,
                    srt_path=srt_path,
                    track_key="career",
                    project_id=1,
                )

        self.assertEqual(captured_rates, ["+7%", "+7%"])

    def test_ensure_wav_offline_ignores_tempo_length_scale(self):
        captured: dict[str, object] = {}

        def _fake_offline_audio_only(**kwargs):
            captured.update(kwargs)
            wav_path = Path(kwargs["wav_path"])
            wav_path.parent.mkdir(parents=True, exist_ok=True)
            wav_path.write_bytes(b"wav")

        with tempfile.TemporaryDirectory() as tmpdir:
            out_wav = Path(tmpdir) / "seg.wav"
            with patch("app.modules.tts.smart_runtime.offline_piper_audio_only", side_effect=_fake_offline_audio_only):
                _ensure_wav(
                    backend="offline",
                    offline_voice_id="zh_CN-huayan-medium",
                    edge_voice="zh-CN-XiaoxiaoNeural",
                    rate="+9%",
                    text="测试文本",
                    tempo=1.23,
                    pitch=0.87,
                    out_wav=out_wav,
                    emotion="excited",
                )
            self.assertTrue(out_wav.exists())

        self.assertIn("length_scale", captured)
        self.assertIsNone(captured["length_scale"])

    def test_build_mux_plan_does_not_include_audio_speed_filters(self):
        plan = build_mux_plan(
            silent_path=Path("silent.mp4"),
            audio_path=Path("voice.mp3"),
            out_tmp=Path("out.mp4"),
            voice_volume=1.0,
            vf="subtitles=test.srt",
        )

        joined = " ".join(plan.args)
        self.assertNotIn("atempo", joined)
        self.assertNotIn("rubberband", joined)
        self.assertNotIn("setpts", joined)


if __name__ == "__main__":
    unittest.main()
