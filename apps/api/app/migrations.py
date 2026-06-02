
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy import inspect

from app.db import engine
from app.settings import settings


def _has_table(table: str) -> bool:
    insp = inspect(engine)
    try:
        return bool(insp.has_table(table))
    except Exception:
        return False


def _has_column(table: str, column: str) -> bool:
    if not _has_table(table):
        return False
    insp = inspect(engine)
    try:
        cols = insp.get_columns(table)
    except Exception:
        return False
    return any(str(c.get("name") or "").lower() == column.lower() for c in cols)


def migrate() -> None:
    if not settings.database_url.lower().startswith(("postgresql://", "postgresql+psycopg://", "postgresql+psycopg2://")):
        raise RuntimeError("当前仅支持 PostgreSQL 业务数据库")
    insp = inspect(engine)
    table_cols: dict[str, set[str]] = {}
    for table in ("project", "scene", "job", "asset", "contentbaselinerevision", "storyboardrevision", "audiosubtitlerevision", "pipelinerun", "projectcenterprojection", "jobcenterprojection"):
        try:
            if insp.has_table(table):
                table_cols[table] = {str(c.get("name") or "").lower() for c in insp.get_columns(table)}
        except Exception:
            table_cols.pop(table, None)

    def has_table(table: str) -> bool:
        return table in table_cols

    def has_column(table: str, column: str) -> bool:
        return column.lower() in table_cols.get(table, set())

    with engine.begin() as conn:
        if has_table("project") and not has_column("project", "role_image_asset_id"):
            conn.execute(text("ALTER TABLE project ADD COLUMN role_image_asset_id INTEGER"))
        if has_table("project") and not has_column("project", "owner_user_id"):
            conn.execute(text("ALTER TABLE project ADD COLUMN owner_user_id INTEGER"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_project_owner_user_id ON project(owner_user_id)"))
        if has_table("project") and not has_column("project", "owner_username"):
            conn.execute(text("ALTER TABLE project ADD COLUMN owner_username TEXT DEFAULT ''"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_project_owner_username ON project(owner_username)"))
        if has_table("project") and not has_column("project", "voice_asset_id"):
            conn.execute(text("ALTER TABLE project ADD COLUMN voice_asset_id INTEGER"))
        if has_table("project") and not has_column("project", "subtitle_asset_id"):
            conn.execute(text("ALTER TABLE project ADD COLUMN subtitle_asset_id INTEGER"))
        if has_table("project") and not has_column("project", "confirmed_baseline_revision_id"):
            conn.execute(text("ALTER TABLE project ADD COLUMN confirmed_baseline_revision_id INTEGER"))
        if has_table("project") and not has_column("project", "current_pipeline_run_id"):
            conn.execute(text("ALTER TABLE project ADD COLUMN current_pipeline_run_id INTEGER"))
        if has_table("project") and not has_column("project", "source_text"):
            conn.execute(text("ALTER TABLE project ADD COLUMN source_text TEXT"))
        if has_table("project") and not has_column("project", "script_source"):
            conn.execute(text("ALTER TABLE project ADD COLUMN script_source TEXT DEFAULT ''"))
        if has_table("project") and not has_column("project", "character_profile"):
            conn.execute(text("ALTER TABLE project ADD COLUMN character_profile TEXT"))
        if has_table("project") and not has_column("project", "publish_title"):
            conn.execute(text("ALTER TABLE project ADD COLUMN publish_title TEXT"))
        if has_table("project") and not has_column("project", "publish_hashtags"):
            conn.execute(text("ALTER TABLE project ADD COLUMN publish_hashtags TEXT"))

        if has_table("project") and not has_column("project", "workflow"):
            # 当前仅支持 mix；保留历史字段用于兼容旧项目。
            conn.execute(text("ALTER TABLE project ADD COLUMN workflow TEXT"))

        # 归一历史 workflow，避免旧 anime 值继续污染当前主链。
        if has_table("project") and has_column("project", "workflow"):
            conn.execute(
                text(
                    "UPDATE project SET workflow='mix' "
                    "WHERE workflow IS NULL OR TRIM(workflow)='' OR LOWER(workflow)='anime'"
                )
            )

        if has_table("project") and not has_column("project", "render_config_json"):
            conn.execute(text("ALTER TABLE project ADD COLUMN render_config_json TEXT"))
        if has_table("project") and has_column("project", "bgm_asset_id"):
            conn.execute(text("ALTER TABLE project DROP COLUMN bgm_asset_id"))
        if has_table("project"):
            conn.execute(text("UPDATE project SET script_source='' WHERE script_source IS NULL"))

        if has_table("scene") and not has_column("scene", "image_negative"):
            conn.execute(text("ALTER TABLE scene ADD COLUMN image_negative TEXT"))
        if has_table("scene") and not has_column("scene", "storyboard_revision_id"):
            conn.execute(text("ALTER TABLE scene ADD COLUMN storyboard_revision_id INTEGER"))

        if has_table("scene") and not has_column("scene", "media_query"):
            conn.execute(text("ALTER TABLE scene ADD COLUMN media_query TEXT"))

        if has_table("scene") and not has_column("scene", "meta_json"):
            conn.execute(text("ALTER TABLE scene ADD COLUMN meta_json TEXT"))

        if has_table("job") and not has_column("job", "payload_json"):
            conn.execute(text("ALTER TABLE job ADD COLUMN payload_json TEXT"))
        if has_table("job") and not has_column("job", "parent_job_id"):
            conn.execute(text("ALTER TABLE job ADD COLUMN parent_job_id INTEGER"))
        if has_table("job") and not has_column("job", "root_job_id"):
            conn.execute(text("ALTER TABLE job ADD COLUMN root_job_id INTEGER"))
        if has_table("job") and not has_column("job", "retry_seq"):
            conn.execute(text("ALTER TABLE job ADD COLUMN retry_seq INTEGER DEFAULT 0"))
        if has_table("job") and not has_column("job", "cancel_requested"):
            conn.execute(text("ALTER TABLE job ADD COLUMN cancel_requested BOOLEAN DEFAULT FALSE"))
        if has_table("job") and not has_column("job", "pause_requested"):
            conn.execute(text("ALTER TABLE job ADD COLUMN pause_requested BOOLEAN DEFAULT FALSE"))
        if has_table("job") and not has_column("job", "cancel_source"):
            conn.execute(text("ALTER TABLE job ADD COLUMN cancel_source TEXT DEFAULT ''"))
        if has_table("job") and not has_column("job", "cancel_reason"):
            conn.execute(text("ALTER TABLE job ADD COLUMN cancel_reason TEXT DEFAULT ''"))
        if has_table("job") and not has_column("job", "worker_id"):
            conn.execute(text("ALTER TABLE job ADD COLUMN worker_id TEXT DEFAULT ''"))
        if has_table("job") and not has_column("job", "worker_pid"):
            conn.execute(text("ALTER TABLE job ADD COLUMN worker_pid INTEGER DEFAULT 0"))
        if has_table("job") and not has_column("job", "worker_started_at"):
            conn.execute(text("ALTER TABLE job ADD COLUMN worker_started_at TIMESTAMP"))
        if has_table("job") and not has_column("job", "worker_heartbeat_at"):
            conn.execute(text("ALTER TABLE job ADD COLUMN worker_heartbeat_at TIMESTAMP"))
        if has_table("job"):
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_job_parent_job_id ON job(parent_job_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_job_root_job_id ON job(root_job_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_job_retry_seq ON job(retry_seq)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_job_cancel_requested ON job(cancel_requested)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_job_pause_requested ON job(pause_requested)"))
        # Backfill existing rows for chain-friendly reads.
        if has_table("job"):
            conn.execute(text("UPDATE job SET root_job_id = id WHERE root_job_id IS NULL"))
            conn.execute(text("UPDATE job SET retry_seq = 0 WHERE retry_seq IS NULL"))
            conn.execute(text("UPDATE job SET cancel_requested = FALSE WHERE cancel_requested IS NULL"))
            conn.execute(text("UPDATE job SET pause_requested = FALSE WHERE pause_requested IS NULL"))
            conn.execute(text("UPDATE job SET cancel_source = '' WHERE cancel_source IS NULL"))
            conn.execute(text("UPDATE job SET cancel_reason = '' WHERE cancel_reason IS NULL"))
            conn.execute(text("UPDATE job SET worker_id = '' WHERE worker_id IS NULL"))
            conn.execute(text("UPDATE job SET worker_pid = 0 WHERE worker_pid IS NULL"))

        if has_table("asset") and not has_column("asset", "project_id"):
            conn.execute(text("ALTER TABLE asset ADD COLUMN project_id INTEGER"))
        if has_table("asset") and not has_column("asset", "scene_id"):
            conn.execute(text("ALTER TABLE asset ADD COLUMN scene_id INTEGER"))
        if has_table("asset") and not has_column("asset", "tag"):
            conn.execute(text("ALTER TABLE asset ADD COLUMN tag TEXT"))

        if has_table("asset") and not has_column("asset", "meta_json"):
            conn.execute(text("ALTER TABLE asset ADD COLUMN meta_json TEXT"))

        if has_table("contentbaselinerevision"):
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_contentbaselinerevision_project_id ON contentbaselinerevision(project_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_contentbaselinerevision_status ON contentbaselinerevision(status)"))
        if has_table("storyboardrevision"):
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_storyboardrevision_project_id ON storyboardrevision(project_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_storyboardrevision_baseline_revision_id ON storyboardrevision(baseline_revision_id)"))
        if has_table("audiosubtitlerevision"):
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_audiosubtitlerevision_project_id ON audiosubtitlerevision(project_id)"))
        if has_table("pipelinerun"):
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_pipelinerun_project_id ON pipelinerun(project_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_pipelinerun_status ON pipelinerun(status)"))

        if has_table("projectcenterprojection"):
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_projectcenterprojection_updated_at ON projectcenterprojection(updated_at)"))

        if has_table("jobcenterprojection"):
            if not has_column("jobcenterprojection", "job_kind"):
                conn.execute(text("ALTER TABLE jobcenterprojection ADD COLUMN job_kind TEXT DEFAULT ''"))
            if not has_column("jobcenterprojection", "status"):
                conn.execute(text("ALTER TABLE jobcenterprojection ADD COLUMN status TEXT DEFAULT ''"))
            if not has_column("jobcenterprojection", "is_active"):
                conn.execute(text("ALTER TABLE jobcenterprojection ADD COLUMN is_active BOOLEAN DEFAULT FALSE"))
            conn.execute(text("UPDATE jobcenterprojection SET job_kind = COALESCE(job_kind, '')"))
            conn.execute(text("UPDATE jobcenterprojection SET status = COALESCE(status, '')"))
            conn.execute(text("UPDATE jobcenterprojection SET is_active = COALESCE(is_active, FALSE)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_jobcenterprojection_project_id ON jobcenterprojection(project_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_jobcenterprojection_job_kind ON jobcenterprojection(job_kind)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_jobcenterprojection_status ON jobcenterprojection(status)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_jobcenterprojection_is_active ON jobcenterprojection(is_active)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_jobcenterprojection_updated_at ON jobcenterprojection(updated_at)"))

        if insp.has_table("llmprovider"):
            conn.execute(text("DELETE FROM llmprovider a USING llmprovider b WHERE a.id < b.id"))
            conn.execute(text("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = 'uq_llmprovider_singleton') THEN CREATE UNIQUE INDEX uq_llmprovider_singleton ON llmprovider ((1)); END IF; END $$;"))

        if insp.has_table("imageprovider"):
            conn.execute(text("DELETE FROM imageprovider a USING imageprovider b WHERE a.id < b.id"))
            conn.execute(text("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = 'uq_imageprovider_singleton') THEN CREATE UNIQUE INDEX uq_imageprovider_singleton ON imageprovider ((1)); END IF; END $$;"))

        # For new tables, SQLModel create_all handles them. This file only patches existing tables.
