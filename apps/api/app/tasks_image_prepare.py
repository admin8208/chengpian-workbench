from dataclasses import dataclass

from sqlmodel import select

from app.models import Project, Scene


@dataclass
class ImageGenerationPreparation:
    project: Project
    pid: int
    provider: object
    providers: list[object]
    api_key: str
    pack: object
    targets: list[Scene]


def prepare_image_generation(
    *,
    session_scope,
    project_id: int,
    scene_ids: list[int] | None,
    force: bool,
    get_default_image_provider,
    list_available_image_providers,
    get_image_api_key,
    get_pack,
    should_generate_scene,
) -> ImageGenerationPreparation:
    with session_scope() as session:
        project = session.exec(select(Project).where(Project.id == project_id)).first()
        if not project or project.id is None:
            raise RuntimeError("Project not found")
        pid = int(project.id)

        providers = list_available_image_providers(session)
        provider = providers[0] if providers else get_default_image_provider(session)
        if not provider or provider.id is None or not bool(getattr(provider, "enabled", True)):
            raise RuntimeError("未配置可用的默认生图模型（设置->生图模型）")

        api_key = get_image_api_key(session, int(provider.id))
        if str(provider.type or "") == "openai_compat" and not str(api_key or "").strip():
            raise RuntimeError("未设置生图 API Key（设置->生图模型）")
        if not str(provider.base_url or "").strip():
            raise RuntimeError("生图 base_url 未配置（设置->生图模型）")
        if not str(provider.default_model or "").strip():
            raise RuntimeError("生图 model 未配置（设置->生图模型）")

        pack = get_pack(session, project.channel_key)
        if not pack:
            raise RuntimeError("Channel pack not found")

        scenes = session.exec(select(Scene).where(Scene.project_id == pid).order_by(Scene.idx)).all()
        if scene_ids:
            keep = set(int(x) for x in scene_ids)
            scenes = [scene for scene in scenes if scene.id is not None and int(scene.id) in keep]
        targets = [scene for scene in scenes if should_generate_scene(scene=scene, force=force)]

    return ImageGenerationPreparation(
        project=project,
        pid=pid,
        provider=provider,
        providers=providers,
        api_key=api_key,
        pack=pack,
        targets=targets,
    )
