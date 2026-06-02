from __future__ import annotations

from app.image_service import get_default_image_provider, get_image_api_key, list_available_image_providers
from app.llm_client import openai_compat_generate_image
from app.models import ChannelPack, Project, Scene
from app.material_policies import project_material_mode
from app.tasks_autopilot import get_pack as get_pack_impl
from app.tasks_image_bridge import (
    download_or_decode_image_bridge,
    generate_images_impl_bridge,
    generate_scene_image_via_provider_bridge,
    guess_image_ext_bridge,
    image_generate_attempts_bridge,
    image_generate_timeout_s_bridge,
    is_retryable_image_generation_error_bridge,
    normalize_image_size_bridge,
    scene_prompt_for_provider_bridge,
    should_generate_scene_bridge,
)


def pack_prompts(pack: ChannelPack, scene: Scene) -> tuple[str, str]:
    from app.prompts import build_image_prompts

    return build_image_prompts(pack, scene, aspect="landscape")


def project_material_mode_local(project: Project | None) -> str:
    return project_material_mode(project)


def normalize_image_size_local(project: Project | None) -> str:
    return normalize_image_size_bridge(project)


def image_generate_timeout_s_local() -> int:
    return image_generate_timeout_s_bridge()


def image_generate_attempts_local() -> int:
    return image_generate_attempts_bridge()


def scene_prompt_for_provider_local(pack: ChannelPack, scene: Scene) -> str:
    return scene_prompt_for_provider_bridge(pack, scene)


def download_or_decode_image_local(obj: dict) -> tuple[bytes, str]:
    return download_or_decode_image_bridge(obj)


def guess_image_ext_local(mime: str, obj: dict) -> str:
    return guess_image_ext_bridge(mime, obj)


def is_retryable_image_generation_error_local(detail: str) -> bool:
    return is_retryable_image_generation_error_bridge(detail)


def generate_scene_image_via_provider_local(*, session, provider, api_key: str, project: Project, pack: ChannelPack, scene: Scene) -> tuple[bytes, str, dict]:
    return generate_scene_image_via_provider_bridge(session=session, provider=provider, api_key=api_key, project=project, pack=pack, scene=scene)


def generate_images_impl_local(*, job_id: int, project_id: int, scene_ids: list[int] | None, force: bool, manage_job_state: bool = True) -> None:
    generate_images_impl_bridge(job_id=job_id, project_id=project_id, scene_ids=scene_ids, force=force, manage_job_state=manage_job_state)


__all__ = [
    "pack_prompts",
    "project_material_mode_local",
    "normalize_image_size_local",
    "image_generate_timeout_s_local",
    "image_generate_attempts_local",
    "scene_prompt_for_provider_local",
    "download_or_decode_image_local",
    "guess_image_ext_local",
    "is_retryable_image_generation_error_local",
    "generate_scene_image_via_provider_local",
    "generate_images_impl_local",
    "get_default_image_provider",
    "list_available_image_providers",
    "get_image_api_key",
    "get_pack_impl",
    "openai_compat_generate_image",
    "should_generate_scene_bridge",
]
