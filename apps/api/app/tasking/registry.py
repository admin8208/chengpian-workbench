from app import tasks_cleanup as _tasks_cleanup  # noqa: F401
from app import tasks_entries as _tasks_entries  # noqa: F401
from app import tasks_projection as _tasks_projection  # noqa: F401
from app import tasks_tts_install as _tasks_tts_install  # noqa: F401


def ensure_task_registry_loaded() -> None:
    # 通过模块导入完成 Huey 任务注册。
    return None
