"""System router extracted from the main application entrypoint."""

from fastapi import APIRouter, Query

from app.doctor import run_mix_smoke_check
from app.health_checks import check_edge_tts, check_ffmpeg, check_huey_queue, check_offline_tts, check_online_base, check_runtime_permissions, check_storage, check_worker
from app.schemas import DoctorOut, HealthComponentOut, HealthOut

router = APIRouter(tags=["system"])


@router.get("/api/health", response_model=HealthOut)
def get_health(probe: bool = Query(False)):
    comps = {
        "storage": check_storage(),
        "runtime_permissions": check_runtime_permissions(),
        "worker": check_worker(),
        "queue": check_huey_queue(),
        "ffmpeg": check_ffmpeg(),
        "online_base": check_online_base() if probe else HealthComponentOut(ok=False, status="未检测", detail="默认健康检查不访问外网，点击刷新检查可执行在线配音链路探测。"),
        "edge_tts": check_edge_tts(probe=probe),
        "offline_tts": check_offline_tts(),
    }
    base_ok = bool(comps.get("storage").ok) and bool(comps.get("ffmpeg").ok)
    tts_ok = bool(comps.get("edge_tts").ok) or bool(comps.get("offline_tts").ok)
    return HealthOut(ok=bool(base_ok and tts_ok), components=comps)


@router.post("/api/doctor/mix-smoke", response_model=DoctorOut)
def run_mix_smoke_test():
    return run_mix_smoke_check(require_llm=True, require_media=True)
