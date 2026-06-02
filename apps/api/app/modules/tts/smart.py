import os
import re
import time
from pathlib import Path

from app.ffmpeg_utils import ffmpeg_path, run_ffmpeg
from app.project_paths import project_root_path, project_tmp_dir
from app.settings import settings
from app.api_common import register_project_tts_cache_refs

from .smart_runtime import (
    _cache_file_lock,
    _ensure_wav,
    _hash_key,
    _segments_to_srt,
    _wav_duration_sec,
)
from .smart_support import (
    _de_ai_oral_text,
    _fallback_segments,
    _installed_offline_voice_ids,
    _is_drama_like,
    _llm_segments,
    _track_voice_profile,
    build_scene_captions_from_segments,
    is_drama_like,
    resolve_llm_cfg,
)
from .smart_types import SmartTtsSegment


def smart_tts_generate(
    *,
    project_title: str,
    scenes: list[tuple[int, str]],
    scene_meta_json: list[str],
    backend: str,
    offline_voice_id: str,
    edge_voice_default: str,
    edge_rate_default: str,
    audio_path: Path,
    srt_path: Path | None = None,
    track_key: str = "",
    project_id: int | None = None,
) -> tuple[str, list[str]]:
    drama = _is_drama_like(title=project_title, scenes=scenes, scene_meta_json=scene_meta_json)
    llm_cfg = resolve_llm_cfg()

    segs: list[SmartTtsSegment] = []
    if drama and llm_cfg:
        try:
            segs = _llm_segments(title=project_title, scenes=scenes, llm_cfg=llm_cfg)
        except Exception:
            segs = []
    if not segs:
        segs = _fallback_segments(scenes)

    try:
        if drama:
            uniq = []
            for s in segs:
                sp = (s.speaker or "").strip() or "旁白"
                if sp not in uniq:
                    uniq.append(sp)
            if len(uniq) == 1 and uniq[0] in ("旁白", "叙述", "narrator"):
                alt: list[SmartTtsSegment] = []
                toggle = False
                for s in segs:
                    tx = (s.text or "").strip()
                    sp = "我"
                    if re.search(r"\b你\b|你们|给你|你这|你就|你不", tx):
                        if re.search(r"(必须|立刻|马上|不行|别|现在|今天|明天|赶紧)", tx):
                            sp = "领导"
                    if re.search(r"^(所以|总之|结论|复盘|听好了)", tx):
                        sp = "旁白"
                    if sp == "我" and toggle:
                        sp = "领导"
                    toggle = not toggle
                    alt.append(SmartTtsSegment(scene_idx=s.scene_idx, speaker=sp, text=tx, pace=s.pace, emotion=s.emotion))
                segs = alt
    except Exception:
        pass

    if not drama:
        segs = [SmartTtsSegment(scene_idx=s.scene_idx, speaker="旁白", text=_de_ai_oral_text(s.text), pace=s.pace, emotion=s.emotion) for s in segs]

    speaker_set: list[str] = []
    for s in segs:
        sp = (s.speaker or "").strip() or "旁白"
        if sp not in speaker_set:
            speaker_set.append(sp)
    if not speaker_set:
        speaker_set = ["旁白"]

    backend_used = backend if backend in ("edge", "offline_piper") else "offline_piper"
    offline_ids = _installed_offline_voice_ids()
    if offline_voice_id and offline_voice_id not in offline_ids:
        offline_ids.insert(0, offline_voice_id)
    if not offline_ids:
        offline_ids = [offline_voice_id]

    tkey = (track_key or "").strip().lower()
    prof = _track_voice_profile(tkey)
    edge_voices = [str(edge_voice_default or "").strip() or "zh-CN-XiaoxiaoNeural"]
    if tkey == "emotion":
        single_offline_voice = str(offline_voice_id or (offline_ids[0] if offline_ids else "")).strip()
        offline_ids = [single_offline_voice] if single_offline_voice else offline_ids[:1]

    sp_map: dict[str, dict] = {}
    for i, sp in enumerate(speaker_set):
        if backend_used == "edge":
            sp_map[sp] = {
                "edge_voice": edge_voices[i % len(edge_voices)],
                "rate": str(prof.get("base_rate") or edge_rate_default),
                "tempo": float(prof.get("base_tempo") or 1.0),
                "pitch": float(prof.get("base_pitch") or 1.0),
            }
        else:
            vid = offline_ids[i % max(1, len(offline_ids))]
            pitch = float(prof.get("base_pitch") or 1.0)
            if tkey == "emotion":
                pitch = float(prof.get("base_pitch") or 1.0)
            elif sp in ("老板", "领导"):
                pitch = 0.92
            elif sp in ("我", "同事"):
                pitch = 1.06
            sp_map[sp] = {
                "offline_voice_id": vid,
                "tempo": float(prof.get("base_tempo") or 1.0),
                "pitch": pitch,
                "rate": str(prof.get("base_rate") or edge_rate_default),
            }

    cache_dir = settings.assets_dir / "tts_cache"
    if project_id and int(project_id) > 0:
        try:
            project_root = project_root_path(int(project_id))
            audio_parent = audio_path.resolve().parent
            if project_root == audio_parent or project_root in audio_parent.parents:
                cache_dir = project_tmp_dir(int(project_id)) / "tts_segments"
            else:
                cache_dir = audio_path.resolve().parent / "tts_segments"
        except Exception:
            cache_dir = project_tmp_dir(int(project_id)) / "tts_segments"
    cache_dir.mkdir(parents=True, exist_ok=True)
    if project_id and int(project_id) > 0:
        try:
            rels = [f"project_{int(project_id)}/tmp/tts_segments"]
            register_project_tts_cache_refs(int(project_id), rels)
        except Exception:
            pass
    total_segs = len(segs)
    seg_idx_map = {id(s): i for i, s in enumerate(segs)}

    wavs: list[Path] = []
    timed_rows: list[tuple[float, float, str]] = []
    cursor = 0.0
    for s in segs:
        tx = _de_ai_oral_text(s.text)
        if not tx:
            continue
        cfg = sp_map.get(s.speaker) or sp_map.get("旁白") or {}
        emotion = (s.emotion or "neutral").strip().lower()
        # 配音全程严格使用全局语速，分段只保留文本拆分，不再做局部变速/变调。
        tempo = 1.0
        pitch = 1.0
        pause_s = float(prof.get("pause_s") or 0.07)
        seg_idx = seg_idx_map.get(id(s), 0)
        seg_rate = str(edge_rate_default or cfg.get("rate") or "+0%")
        cur_speaker = str(s.speaker or "").strip() or "旁白"
        if backend_used == "edge":
            edge_voice = str(cfg.get("edge_voice") or edge_voice_default)
            key = _hash_key("edge", edge_voice, seg_rate, tx, emotion)
        else:
            vid = str(cfg.get("offline_voice_id") or offline_voice_id)
            key = _hash_key("offline", vid, f"{tempo:.3f}", f"{pitch:.3f}", tx)

        out_wav = cache_dir / f"seg_{key}.wav"
        needs_generate = True
        try:
            needs_generate = (not out_wav.exists()) or out_wav.stat().st_size <= 0
        except Exception:
            needs_generate = True
        if needs_generate:
            with _cache_file_lock(out_wav):
                try:
                    needs_generate = (not out_wav.exists()) or out_wav.stat().st_size <= 0
                except Exception:
                    needs_generate = True
                if needs_generate:
                    _ensure_wav(
                        backend=("edge" if backend_used == "edge" else "offline"),
                        offline_voice_id=str(cfg.get("offline_voice_id") or offline_voice_id),
                        edge_voice=str(cfg.get("edge_voice") or edge_voice_default),
                        rate=str(seg_rate),
                        text=tx,
                        tempo=float(tempo),
                        pitch=float(pitch),
                        out_wav=out_wav,
                        emotion=emotion,
                    )
        wavs.append(out_wav)
        dur = _wav_duration_sec(out_wav)
        if dur > 0:
            timed_rows.append((cursor, cursor + dur, tx))
            cursor += dur
        pause_s = max(float(pause_s), 0.09 if drama else 0.06)
        sil = cache_dir / f"sil_{int(pause_s*1000)}ms.wav"
        if not sil.exists() or sil.stat().st_size <= 0:
            with _cache_file_lock(sil):
                if not sil.exists() or sil.stat().st_size <= 0:
                    run_ffmpeg(["-y", "-f", "lavfi", "-i", f"anullsrc=r=22050:cl=mono", "-t", f"{pause_s:.3f}", ffmpeg_path(sil)])
        wavs.append(sil)
        cursor += max(0.0, float(pause_s))

    end_hold_s = 1.0
    end_sil = cache_dir / f"sil_{int(end_hold_s*1000)}ms_end.wav"
    if not end_sil.exists() or end_sil.stat().st_size <= 0:
        with _cache_file_lock(end_sil):
            if not end_sil.exists() or end_sil.stat().st_size <= 0:
                run_ffmpeg(["-y", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono", "-t", f"{end_hold_s:.3f}", ffmpeg_path(end_sil)])
    wavs.append(end_sil)
    cursor += end_hold_s

    if not wavs:
        raise RuntimeError("TTS 生成失败：没有可用的配音段落")

    list_path = cache_dir / ("concat_" + _hash_key(str(audio_path), str(len(wavs)), str(os.getpid()), str(time.time_ns())) + ".txt")
    list_path.write_text("\n".join(["file '" + str(p.resolve()).replace("\\", "/") + "'" for p in wavs]) + "\n", encoding="utf-8")
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        run_ffmpeg(["-y", "-f", "concat", "-safe", "0", "-i", ffmpeg_path(list_path), "-c:a", "libmp3lame", "-b:a", "128k", ffmpeg_path(audio_path)])
    finally:
        try:
            list_path.unlink(missing_ok=True)
        except Exception:
            pass

    if srt_path is not None and timed_rows:
        try:
            srt_path.parent.mkdir(parents=True, exist_ok=True)
            srt_path.write_text(_segments_to_srt(timed_rows), encoding="utf-8")
        except Exception:
            pass

    cap_map = build_scene_captions_from_segments(segs)
    caption_texts = [cap_map.get(int(idx)) or (nar or "") for idx, nar in scenes]
    return backend_used, caption_texts
