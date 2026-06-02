
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _repo_root() -> Path:
    # apps/api/app/settings.py -> apps/api/app -> apps/api -> apps -> repo
    return Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    database_url: str
    assets_dir: Path
    exports_dir: Path
    huey_storage_dir: Path
    redis_url: str
    worker_count: int

    web_dist_dir: Path

    api_host: str
    api_port: int
    cors_allow_origins: tuple[str, ...]
    cookie_secure_mode: str

    tts_cache_max_age_days: int
    tts_cache_max_size_gb: float
    temp_file_max_age_hours: int
    cleanup_interval_hours: int
    auto_cleanup_enabled: bool


def get_settings() -> Settings:
    root = _repo_root()
    for env_name in (".env.local", ".env.prod"):
        env_path = root / env_name
        if env_path.exists():
            load_dotenv(env_path, override=False)
    data_dir = Path(os.environ.get("CHENGPIAN_DATA_DIR", str(root / "data"))).resolve()

    assets_dir = data_dir / "assets"
    exports_dir = data_dir / "exports"
    huey_storage_dir = data_dir / "huey"
    redis_url = (os.environ.get("CHENGPIAN_REDIS_URL", "redis://127.0.0.1:6379/0") or "redis://127.0.0.1:6379/0").strip()
    database_url = (os.environ.get("CHENGPIAN_DATABASE_URL", "") or "").strip()
    if not database_url:
        raise RuntimeError("未设置 CHENGPIAN_DATABASE_URL，当前仅支持 PostgreSQL 作为业务数据库")
    if not database_url.lower().startswith(("postgresql://", "postgresql+psycopg://", "postgresql+psycopg2://")):
        raise RuntimeError("CHENGPIAN_DATABASE_URL 必须是 PostgreSQL 连接串")

    try:
        worker_count = max(1, int(os.environ.get("CHENGPIAN_WORKER_COUNT", "1") or "1"))
    except Exception:
        worker_count = 1

    assets_dir.mkdir(parents=True, exist_ok=True)
    exports_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    api_host = os.environ.get("CHENGPIAN_API_HOST", "127.0.0.1").strip() or "127.0.0.1"
    try:
        api_port = int(os.environ.get("CHENGPIAN_API_PORT", "8010"))
    except Exception:
        api_port = 8010

    web_dist_dir = Path(
        os.environ.get(
            "CHENGPIAN_WEB_DIST_DIR",
            str(root / "apps" / "web" / "dist"),
        )
    ).resolve()

    cors = os.environ.get("CHENGPIAN_CORS", "").strip()
    if cors:
        cors_allow_origins = tuple([x.strip() for x in cors.split(",") if x.strip() and x.strip() != "*"])
    else:
        cors_allow_origins = (
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5188",
            "http://127.0.0.1:5188",
        )

    cookie_secure_mode = (os.environ.get("CHENGPIAN_COOKIE_SECURE", "auto") or "auto").strip().lower()
    if cookie_secure_mode not in ("auto", "true", "false"):
        cookie_secure_mode = "auto"

    try:
        tts_cache_max_age_days = int(os.environ.get("CHENGPIAN_TTS_CACHE_MAX_AGE_DAYS", "7"))
    except Exception:
        tts_cache_max_age_days = 7

    try:
        tts_cache_max_size_gb = float(os.environ.get("CHENGPIAN_TTS_CACHE_MAX_SIZE_GB", "5.0"))
    except Exception:
        tts_cache_max_size_gb = 5.0

    try:
        temp_file_max_age_hours = int(os.environ.get("CHENGPIAN_TEMP_FILE_MAX_AGE_HOURS", "24"))
    except Exception:
        temp_file_max_age_hours = 24

    try:
        cleanup_interval_hours = int(os.environ.get("CHENGPIAN_CLEANUP_INTERVAL_HOURS", "6"))
    except Exception:
        cleanup_interval_hours = 6

    auto_cleanup_enabled = os.environ.get("CHENGPIAN_AUTO_CLEANUP_ENABLED", "true").strip().lower() in ("true", "1", "yes")

    return Settings(
        data_dir=data_dir,
        database_url=database_url,
        assets_dir=assets_dir,
        exports_dir=exports_dir,
        huey_storage_dir=huey_storage_dir,
        redis_url=redis_url,
        worker_count=worker_count,
        web_dist_dir=web_dist_dir,
        api_host=api_host,
        api_port=api_port,
        cors_allow_origins=cors_allow_origins,
        cookie_secure_mode=cookie_secure_mode,
        tts_cache_max_age_days=tts_cache_max_age_days,
        tts_cache_max_size_gb=tts_cache_max_size_gb,
        temp_file_max_age_hours=temp_file_max_age_hours,
        cleanup_interval_hours=cleanup_interval_hours,
        auto_cleanup_enabled=auto_cleanup_enabled,
    )


settings = get_settings()
