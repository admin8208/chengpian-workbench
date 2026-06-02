import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

from app.modules.visual.service import run_visual_stage


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _Session:
    def __init__(self, rows):
        self.rows = rows

    def exec(self, _query):
        return _Rows(self.rows)


class VisualStageContractTests(unittest.TestCase):
    def test_visual_stage_must_not_rewrite_narration(self):
        snapshots = [
            [SimpleNamespace(id=1, narration="主旁白")],
            [SimpleNamespace(id=1, narration="被视觉阶段改写")],
        ]

        def _session_scope():
            return nullcontext(_Session(snapshots.pop(0)))

        with patch("app.modules.visual.service.session_scope", side_effect=_session_scope), patch(
            "app.modules.visual.service.project_material_mode", return_value="network"
        ):
            with self.assertRaises(RuntimeError) as ctx:
                run_visual_stage(
                    job_id=1,
                    project_id=2,
                    pid=2,
                    wf="mix",
                    project=SimpleNamespace(),
                    autofill_media_local=lambda *_args, **_kwargs: None,
                    generate_images_local=lambda *_args, **_kwargs: None,
                    autopilot_mark_stage=lambda *_args, **_kwargs: None,
                    autopilot_get_job_status=lambda _job_id: "running",
                    autopilot_job_message=lambda _job_id: "",
                    autopilot_payload=lambda _job_id: {},
                    autopilot_scene_stats=lambda _pid: (0, None, 1),
                    humanize_autopilot_detail=lambda msg: msg,
                    update_job=lambda *_args, **_kwargs: None,
                    wait_if_job_paused=lambda _job_id: None,
                )

        self.assertIn("不得改写主旁白", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
