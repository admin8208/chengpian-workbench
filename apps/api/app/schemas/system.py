from pydantic import BaseModel


class HealthComponentOut(BaseModel):
    ok: bool
    status: str
    detail: str | None = None
    hint: str | None = None


class HealthOut(BaseModel):
    ok: bool
    components: dict[str, HealthComponentOut]


class DoctorItemOut(BaseModel):
    ok: bool
    name: str
    status: str
    detail: str | None = None
    hint: str | None = None


class DoctorOut(BaseModel):
    ok: bool
    started_at: str
    finished_at: str
    duration_ms: int
    items: list[DoctorItemOut]


class OfflineVoiceCleanupOut(BaseModel):
    ok: bool
    deleted_voice_ids: list[str] = []
    freed_bytes: int = 0


class StorageCleanupOut(BaseModel):
    ok: bool
    project_count: int = 0
    removed_db: int = 0
    removed_files: int = 0
    removed_previews: int = 0
