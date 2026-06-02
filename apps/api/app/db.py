
from contextlib import contextmanager

from loguru import logger
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy import text
from sqlalchemy import inspect

from app.logging_setup import sanitize_log_text
from app.settings import settings
from app.projection_refresh import pop_scheduled_project_refreshes, run_project_refreshes


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)


def init_db() -> None:
    # Ensure all SQLModel tables are registered before create_all.
    from app import models as _models  # noqa: F401
    from app import models_revisions as _models_revisions  # noqa: F401

    SQLModel.metadata.create_all(engine)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            conn.commit()
    except Exception as e:
        logger.exception("database connectivity check failed: {}", sanitize_log_text(e))
        raise RuntimeError("数据库初始化失败：无法连接 PostgreSQL") from e

    try:
        from app.migrations import migrate

        migrate()
    except Exception as e:
        logger.exception("database migration failed: {}", sanitize_log_text(e))
        raise RuntimeError("数据库迁移失败，请检查当前数据目录或迁移逻辑") from e

    try:
        _sync_postgres_sequences()
    except Exception as e:
        logger.exception("postgres sequence sync failed: {}", sanitize_log_text(e))
        raise RuntimeError("数据库初始化失败：无法同步 PostgreSQL 主键序列") from e


def _sync_postgres_sequences() -> None:
    if not settings.database_url.lower().startswith(("postgresql://", "postgresql+psycopg://", "postgresql+psycopg2://")):
        return
    insp = inspect(engine)
    tables = insp.get_table_names()
    with engine.begin() as conn:
        for table in tables:
            pk_cols = insp.get_pk_constraint(table).get("constrained_columns") or []
            if len(pk_cols) != 1:
                continue
            pk = str(pk_cols[0])
            seq = conn.execute(text("SELECT pg_get_serial_sequence(:table, :col)"), {"table": table, "col": pk}).scalar()
            if not seq:
                continue
            conn.execute(
                text(f"SELECT setval('{seq}', GREATEST(COALESCE((SELECT MAX({pk}) FROM {table}), 0), 1), true)")
            )


@contextmanager
def session_scope():
    session = Session(engine, expire_on_commit=False)
    try:
        yield session
        refresh_ids = pop_scheduled_project_refreshes(session)
        session.commit()
        try:
            run_project_refreshes(refresh_ids)
        except Exception as e:
            logger.exception("projection refresh failed after commit: {}", sanitize_log_text(e))
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db():
    session = Session(engine, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
