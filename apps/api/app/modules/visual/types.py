from __future__ import annotations

from typing import Any, Protocol


class VisualPipeline(Protocol):
    def media_preflight(self, session, project=None) -> tuple[bool, dict]: ...

    def run_media_stage(self, **kwargs: Any) -> None: ...
