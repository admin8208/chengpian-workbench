from sqlmodel import select

from app.models import Project, Scene


def library_asset_delete_block_reason(session, asset_id: int) -> str:
    project_ref = session.exec(
        select(Project).where(
            (Project.role_image_asset_id == int(asset_id))
            | (Project.voice_asset_id == int(asset_id))
            | (Project.subtitle_asset_id == int(asset_id))
        )
    ).first()
    if project_ref and project_ref.id is not None:
        title = (project_ref.title or "").strip() or f"#{int(project_ref.id)}"
        return f"当前素材仍被项目《{title}》直接引用，暂时不能删除"
    scene_ref = session.exec(select(Scene).where(Scene.image_asset_id == int(asset_id))).first()
    if scene_ref and scene_ref.id is not None:
        return f"当前素材仍被项目镜头引用（scene #{int(scene_ref.id)}），暂时不能删除"
    return ""
