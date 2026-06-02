from sqlmodel import select

from app.llm_service import get_api_key, get_default_provider
from app.models import ChannelPack, LlmProvider, Project
from app.tasks_autopilot import get_pack as get_pack_impl
from app.tasks_helpers import fail_job as _fail_job
from app.tasks_storyboard import (
    llm_generate_storyboard as storyboard_llm_generate_storyboard,
    llm_rewrite_storyboard as storyboard_llm_rewrite_storyboard,
    storyboard_duration_profile,
)
from app.tasks_storyboard_entry_impl import (
    generate_storyboard_local as generate_storyboard_impl_local,
    rewrite_storyboard_local as rewrite_storyboard_impl_local,
)


def storyboard_duration_profile_bridge(pack: ChannelPack, cfg: dict | None = None, *, render_cfg: dict | None = None) -> dict:
    return storyboard_duration_profile(pack, cfg, render_cfg=render_cfg)


def llm_generate_storyboard_bridge(
    topic: str,
    pack: ChannelPack,
    provider: LlmProvider,
    api_key: str,
    *,
    character_profile: str = "",
    workflow: str = "mix",
    render_cfg: dict | None = None,
    material_mode: str = "",
) -> tuple[str, list[dict]]:
    return storyboard_llm_generate_storyboard(
        topic,
        pack,
        provider,
        api_key,
        character_profile=character_profile,
        workflow=workflow,
        render_cfg=render_cfg,
        material_mode=material_mode,
    )


def llm_rewrite_storyboard_bridge(
    source_text: str,
    pack: ChannelPack,
    provider: LlmProvider,
    api_key: str,
    *,
    character_profile: str = "",
    level: str = "medium",
    workflow: str = "mix",
    render_cfg: dict | None = None,
    material_mode: str = "",
) -> tuple[str, list[dict]]:
    return storyboard_llm_rewrite_storyboard(
        source_text,
        pack,
        provider,
        api_key,
        character_profile=character_profile,
        level=level,
        workflow=workflow,
        render_cfg=render_cfg,
        material_mode=material_mode,
    )


def rewrite_storyboard_local_bridge(job_id: int, project_id: int, *, level: str = "medium") -> None:
    rewrite_storyboard_impl_local(
        job_id,
        project_id,
        level=level,
        select_project=lambda session, pid: session.exec(select(Project).where(Project.id == pid)).first(),
        get_pack=get_pack_impl,
        fail_job=_fail_job,
        get_default_provider=get_default_provider,
        get_api_key=get_api_key,
        llm_rewrite_storyboard=llm_rewrite_storyboard_bridge,
    )


def generate_storyboard_local_bridge(job_id: int, project_id: int, *, topic: str | None = None) -> None:
    generate_storyboard_impl_local(
        job_id,
        project_id,
        topic=topic,
        select_project=lambda session, pid: session.exec(select(Project).where(Project.id == pid)).first(),
        get_pack=get_pack_impl,
        fail_job=_fail_job,
        get_default_provider=get_default_provider,
        get_api_key=get_api_key,
        llm_generate_storyboard=llm_generate_storyboard_bridge,
    )
