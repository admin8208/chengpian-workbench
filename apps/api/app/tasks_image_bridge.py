from app.image_service import get_default_image_provider, get_image_api_key, list_available_image_providers
from app.llm_client import openai_compat_generate_image
from app.models import ChannelPack, Project, Scene
from app.tasks_autopilot import get_pack as get_pack_impl
from app.tasks_image_entry_impl import (
    generate_images_impl as generate_images_impl_local,
    generate_project_images_local as generate_project_images_impl_local,
    generate_scene_image_local as generate_scene_image_impl_local,
)
from app.tasks_image_provider import (
    download_or_decode_image as download_or_decode_image_helper,
    generate_scene_image_via_provider as generate_scene_image_via_provider_helper,
    guess_image_ext as guess_image_ext_helper,
    image_generate_attempts as image_generate_attempts_helper,
    image_generate_timeout_s as image_generate_timeout_s_helper,
    is_retryable_image_generation_error as is_retryable_image_generation_error_helper,
    normalize_image_size as normalize_image_size_helper,
    scene_prompt_for_provider as scene_prompt_for_provider_helper,
)


def should_generate_scene_bridge(*, scene: Scene, force: bool) -> bool:
    if force:
        return True
    return not bool(getattr(scene, "image_asset_id", None))


def normalize_image_size_bridge(project: Project | None) -> str:
    return normalize_image_size_helper(project)


def image_generate_timeout_s_bridge() -> int:
    return image_generate_timeout_s_helper()


def image_generate_attempts_bridge() -> int:
    return image_generate_attempts_helper()


def scene_prompt_for_provider_bridge(pack: ChannelPack, scene: Scene) -> str:
    return scene_prompt_for_provider_helper(pack, scene)


def download_or_decode_image_bridge(obj: dict) -> tuple[bytes, str]:
    return download_or_decode_image_helper(obj)


def guess_image_ext_bridge(mime: str, obj: dict) -> str:
    return guess_image_ext_helper(mime, obj)


def is_retryable_image_generation_error_bridge(detail: str) -> bool:
    return is_retryable_image_generation_error_helper(detail)


def generate_scene_image_via_provider_bridge(*, session, provider, api_key: str, project: Project, pack: ChannelPack, scene: Scene) -> tuple[bytes, str, dict]:
    providers = list_available_image_providers(session)
    return generate_scene_image_via_provider_helper(
        session=session,
        provider=provider,
        providers=providers,
        get_image_api_key=get_image_api_key,
        api_key=api_key,
        project=project,
        pack=pack,
        scene=scene,
        openai_compat_generate_image=openai_compat_generate_image,
    )


def generate_images_impl_bridge(
    *,
    job_id: int,
    project_id: int,
    scene_ids: list[int] | None,
    force: bool,
    manage_job_state: bool = True,
) -> None:
    generate_images_impl_local(
        job_id=job_id,
        project_id=project_id,
        scene_ids=scene_ids,
        force=force,
        get_default_image_provider=get_default_image_provider,
        list_available_image_providers=list_available_image_providers,
        get_image_api_key=get_image_api_key,
        get_pack=get_pack_impl,
        generate_scene_image_via_provider=generate_scene_image_via_provider_bridge,
        guess_image_ext=guess_image_ext_bridge,
        should_generate_scene=should_generate_scene_bridge,
        manage_job_state=manage_job_state,
    )


def generate_project_images_local_bridge(
    job_id: int,
    project_id: int,
    *,
    force: bool = False,
    manage_job_state: bool = True,
) -> None:
    generate_project_images_impl_local(
        job_id,
        project_id,
        force=force,
        generate_images_impl=generate_images_impl_bridge,
        manage_job_state=manage_job_state,
    )


def generate_scene_image_local_bridge(
    job_id: int,
    scene_id: int,
    *,
    force: bool = True,
    manage_job_state: bool = True,
) -> None:
    generate_scene_image_impl_local(
        job_id,
        scene_id,
        force=force,
        generate_images_impl=generate_images_impl_bridge,
        manage_job_state=manage_job_state,
    )
