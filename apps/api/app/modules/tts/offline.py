
import io
import json
import os
import shutil
import subprocess
import tarfile
import time
import uuid
import wave
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from app.ffmpeg_utils import ffmpeg_path, run_ffmpeg
from app.modules.tts.catalog import DEFAULT_VOICE_ID, PIPER_BINARIES, discover_zh_cn_voice_ids, voice_urls_for
from app.settings import settings


@dataclass(frozen=True)
class OfflineTtsStatus:
    installed: bool
    ok: bool
    backend: str
    voice_id: str
    detail: str = ""


_VOICE_META_CACHE: dict[str, dict] = {}
_PY_PIPER_ZH_READY: bool | None = None
_PY_PIPER_VOICE_CACHE: dict[str, Any] = {}


def _installed_voice_config(voice_id: str) -> dict:
    _model, cfg = piper_voice_paths(voice_id)
    if not cfg.exists():
        return {}
    try:
        obj = json.loads(cfg.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _voice_phoneme_type_from_config(obj: dict | None = None) -> str:
    if not isinstance(obj, dict):
        return ""
    return str(obj.get("phoneme_type") or "").strip().lower()


def _python_piper_zh_ready() -> bool:
    global _PY_PIPER_ZH_READY
    if _PY_PIPER_ZH_READY is not None:
        return bool(_PY_PIPER_ZH_READY)
    try:
        import importlib

        importlib.import_module("g2pw")
        importlib.import_module("torch")
        importlib.import_module("piper")

        _PY_PIPER_ZH_READY = True
    except Exception:
        _PY_PIPER_ZH_READY = False
    return bool(_PY_PIPER_ZH_READY)


def _voice_runtime_compatible(phoneme_type: str) -> bool:
    pt = str(phoneme_type or "").strip().lower()
    if pt != "pinyin":
        return True
    return _python_piper_zh_ready()


def _compat_reason_for_phoneme_type(phoneme_type: str) -> str:
    pt = str(phoneme_type or "").strip().lower()
    if pt != "pinyin":
        return "兼容"
    if _python_piper_zh_ready():
        return "兼容（Python Piper 中文扩展）"
    return "当前环境未安装 piper-tts 中文依赖（g2pw/torch）"


def _load_python_piper_voice(voice_id: str):
    import importlib

    vid = (voice_id or "").strip() or DEFAULT_VOICE_ID
    model, cfg = piper_voice_paths(vid)
    cache_key = f"{model}:{cfg}"
    cached = _PY_PIPER_VOICE_CACHE.get(cache_key)
    if cached is not None:
        return cached
    PiperVoice = importlib.import_module("piper").PiperVoice
    voice = PiperVoice.load(model, config_path=cfg, use_cuda=False)
    _PY_PIPER_VOICE_CACHE[cache_key] = voice
    return voice


def _python_piper_audio_only(
    *,
    text: str,
    voice_id: str,
    wav_path: Path,
    length_scale: float | None = None,
    noise_scale: float | None = None,
    noise_w: float | None = None,
) -> None:
    import importlib

    if not _python_piper_zh_ready():
        raise RuntimeError("离线中文增强音色依赖未安装：缺少 piper-tts 中文扩展")

    voice = _load_python_piper_voice(voice_id)
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = wav_path.with_suffix(wav_path.suffix + ".tmp")
    if tmp.exists():
        tmp.unlink(missing_ok=True)
    SynthesisConfig = importlib.import_module("piper.config").SynthesisConfig
    syn_cfg = SynthesisConfig(
        length_scale=(float(length_scale) if length_scale is not None else None),
        noise_scale=(float(noise_scale) if noise_scale is not None else None),
        noise_w_scale=(float(noise_w) if noise_w is not None else None),
    )
    chunks = list(voice.synthesize(str(text or ""), syn_config=syn_cfg))
    if not chunks:
        raise RuntimeError("piper-tts 未生成有效音频")
    sample_rate = int(getattr(chunks[0], "sample_rate", 0) or 0)
    if sample_rate <= 0:
        raise RuntimeError("piper-tts 返回了无效采样率")
    with wave.open(str(tmp), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for chunk in chunks:
            buf = getattr(chunk, "audio_int16_bytes", b"") or b""
            if buf:
                wf.writeframes(buf)
    if (not tmp.exists()) or tmp.stat().st_size <= 0:
        raise RuntimeError("piper-tts 未生成有效音频")
    tmp.replace(wav_path)


def _read_json_from_url(url: str) -> dict:
    req = Request(url, headers={"User-Agent": "chengpian-workbench/1.0"})
    with urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")
    data = json.loads(raw or "{}")
    return data if isinstance(data, dict) else {}


def inspect_remote_voice(voice_id: str, *, force: bool = False) -> dict:
    vid = (voice_id or "").strip() or DEFAULT_VOICE_ID
    if not force and vid in _VOICE_META_CACHE:
        return dict(_VOICE_META_CACHE[vid])

    voice = voice_urls_for(vid)
    meta = {
        "voice_id": vid,
        "label": getattr(voice, "label", vid),
        "quality": getattr(voice, "quality", ""),
        "sample_rate": int(getattr(voice, "sample_rate", 0) or 0),
        "compatible": False,
        "reason": "未检测",
        "source": "huggingface",
    }
    last_err = ""
    for url in [voice.config_url_primary, voice.config_url_fallback]:
        try:
            obj = _read_json_from_url(url)
            pt = str(obj.get("phoneme_type") or "").strip().lower()
            pv = str(obj.get("piper_version") or "").strip()
            sr = int((obj.get("audio") or {}).get("sample_rate") or meta["sample_rate"] or 0)
            compatible = _voice_runtime_compatible(pt)
            meta.update(
                {
                    "sample_rate": sr,
                    "phoneme_type": pt,
                    "piper_version": pv,
                    "compatible": bool(compatible),
                    "reason": _compat_reason_for_phoneme_type(pt),
                }
            )
            _VOICE_META_CACHE[vid] = dict(meta)
            return dict(meta)
        except Exception as e:
            last_err = str(e)
            continue
    meta["reason"] = f"无法读取音色配置：{last_err[:160]}" if last_err else "无法读取音色配置"
    _VOICE_META_CACHE[vid] = dict(meta)
    return dict(meta)


def list_available_offline_voices(*, force: bool = False) -> list[dict]:
    installed_rows = list_offline_voices(include_incompatible=True)
    installed_map = {str(row.get("voice_id") or "").strip(): row for row in installed_rows if str(row.get("voice_id") or "").strip()}
    voice_ids = set(discover_zh_cn_voice_ids(force=force))
    voice_ids.update(installed_map.keys())
    out: list[dict] = []
    for vid in sorted(voice_ids):
        remote = inspect_remote_voice(vid, force=force)
        installed = installed_map.get(vid)
        installed_compatible = bool(installed.get("compatible")) if installed else False
        compatible = installed_compatible or bool(remote.get("compatible"))
        reason = ""
        if installed and not installed_compatible:
            reason = f"已安装，但当前引擎不兼容（{installed.get('reason') or 'bad_config'}）"
        elif not compatible:
            reason = str(remote.get("reason") or "不兼容")
        out.append(
            {
                "voice_id": vid,
                "label": str(remote.get("label") or vid),
                "quality": str(remote.get("quality") or ""),
                "sample_rate": int(remote.get("sample_rate") or installed.get("sample_rate") or 0) if installed else int(remote.get("sample_rate") or 0),
                "installed": bool(installed),
                "compatible": bool(compatible),
                "reason": reason,
                "phoneme_type": str(remote.get("phoneme_type") or installed.get("phoneme_type") or "") if installed else str(remote.get("phoneme_type") or ""),
                "piper_version": str(remote.get("piper_version") or installed.get("piper_version") or "") if installed else str(remote.get("piper_version") or ""),
            }
        )
    return out


def piper_root_dir() -> Path:
    return settings.assets_dir / "tts_offline" / "piper"


def piper_bin_dir() -> Path:
    return piper_root_dir() / "bin"


def piper_models_dir() -> Path:
    return piper_root_dir() / "models"


def piper_exe_path() -> Path:
    # Windows: prefer bundled folder layout where DLLs live next to exe.
    # Official Piper archives typically extract into a folder that contains
    # piper(.exe) + espeak-ng.dll + onnxruntime.dll, etc.
    name = "piper.exe" if os.name == "nt" else "piper"
    nested = piper_bin_dir() / "piper" / name
    if nested.exists():
        return nested
    return piper_bin_dir() / name


def piper_voice_paths(voice_id: str) -> tuple[Path, Path]:
    vid = (voice_id or "").strip() or DEFAULT_VOICE_ID
    model = piper_models_dir() / f"{vid}.onnx"
    cfg = piper_models_dir() / f"{vid}.onnx.json"
    return model, cfg


def list_offline_voices(*, include_incompatible: bool = False) -> list[dict]:
    """List installed offline voice ids with basic compatibility metadata."""

    out: list[dict] = []
    mdir = piper_models_dir()
    if not mdir.exists():
        return out

    for mp in sorted(mdir.glob("*.onnx")):
        vid = mp.stem
        cfg = mdir / f"{vid}.onnx.json"
        if not cfg.exists():
            if include_incompatible:
                out.append({"voice_id": vid, "compatible": False, "reason": "missing_config"})
            continue
        try:
            obj = json.loads(cfg.read_text(encoding="utf-8"))
            pt = str(obj.get("phoneme_type") or "").strip().lower()
            pv = str(obj.get("piper_version") or "").strip()
            sr = int((obj.get("audio") or {}).get("sample_rate") or 0)
        except Exception:
            if include_incompatible:
                out.append({"voice_id": vid, "compatible": False, "reason": "bad_config"})
            continue
        compatible = _voice_runtime_compatible(pt)
        if not compatible and not include_incompatible:
            continue
        out.append({"voice_id": vid, "compatible": bool(compatible), "phoneme_type": pt, "piper_version": pv, "sample_rate": sr, "reason": _compat_reason_for_phoneme_type(pt)})
    return out


def cleanup_incompatible_offline_voices() -> dict:
    """Remove installed voices that are incompatible with the bundled Piper engine.

    Currently we treat phoneme_type=pinyin as incompatible because it can crash
    with errors like: '"ai" is not a single codepoint'.
    """

    mdir = piper_models_dir()
    if not mdir.exists():
        return {"deleted_voice_ids": [], "freed_bytes": 0}

    deleted: list[str] = []
    freed = 0
    for cfg in sorted(mdir.glob("*.onnx.json")):
        vid = cfg.name.replace(".onnx.json", "")
        if not vid:
            continue
        try:
            obj = json.loads(cfg.read_text(encoding="utf-8"))
            pt = str(obj.get("phoneme_type") or "").strip().lower()
        except Exception:
            pt = ""

        if pt != "pinyin" or _python_piper_zh_ready():
            continue

        model = mdir / f"{vid}.onnx"
        # delete model + config
        for p in (model, cfg):
            try:
                if p.exists() and p.is_file():
                    try:
                        freed += int(p.stat().st_size)
                    except Exception:
                        pass
                    p.unlink(missing_ok=True)
            except Exception:
                pass
        deleted.append(vid)

    return {"deleted_voice_ids": deleted, "freed_bytes": int(freed)}


def _platform_key() -> str:
    import platform
    import sys

    sysname = sys.platform
    machine = (platform.machine() or "").lower()
    if sysname.startswith("win"):
        # Piper only provides amd64 zip in the official release.
        return "win32_amd64"
    if sysname.startswith("linux"):
        if machine in ("x86_64", "amd64"):
            return "linux_x86_64"
    if sysname == "darwin":
        if machine in ("arm64", "aarch64"):
            return "darwin_aarch64"
        return "darwin_x64"
    # fallback
    return "win32_amd64"


def _download_to(url: str, dst: Path, *, job_cb=None) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    if tmp.exists():
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
    req = Request(url, headers={"User-Agent": "chengpian-workbench/1.0"})
    with urlopen(req, timeout=60) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        got = 0
        with open(tmp, "wb") as f:
            while True:
                buf = resp.read(1024 * 256)
                if not buf:
                    break
                f.write(buf)
                got += len(buf)
                if callable(job_cb) and total > 0:
                    job_cb(got, total)
    tmp.replace(dst)


def _extract_archive(archive: Path, dst_dir: Path) -> None:
    dst_dir.mkdir(parents=True, exist_ok=True)
    name = archive.name.lower()
    if name.endswith(".zip"):
        with zipfile.ZipFile(archive, "r") as z:
            z.extractall(dst_dir)
        return
    if name.endswith(".tar.gz") or name.endswith(".tgz"):
        with tarfile.open(archive, "r:gz") as t:
            t.extractall(dst_dir)
        return
    raise RuntimeError(f"unsupported archive: {archive.name}")


def install_piper_from_archive(*, archive_path: Path) -> None:
    """Install/refresh Piper binary from a user-provided archive."""

    root = piper_root_dir()
    bdir = piper_bin_dir()
    root.mkdir(parents=True, exist_ok=True)
    bdir.mkdir(parents=True, exist_ok=True)

    tmp_extract = root / "_extract_tmp"
    if tmp_extract.exists():
        shutil.rmtree(tmp_extract, ignore_errors=True)
    tmp_extract.mkdir(parents=True, exist_ok=True)
    _extract_archive(archive_path, tmp_extract)

    exe_name = "piper.exe" if os.name == "nt" else "piper"
    found = None
    for p in tmp_extract.rglob(exe_name):
        if p.is_file():
            found = p
            break
    if not found:
        raise RuntimeError("安装包中未找到 piper 可执行文件")

    # Clear bin dir then copy extracted tree.
    for child in bdir.iterdir() if bdir.exists() else []:
        try:
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)
        except Exception:
            pass
    for item in tmp_extract.iterdir():
        dst = bdir / item.name
        try:
            if item.is_dir():
                shutil.copytree(item, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dst)
        except Exception:
            pass

    exe_dst = piper_exe_path()
    if not exe_dst.exists():
        try:
            shutil.copy2(found, exe_dst)
        except Exception:
            pass

    try:
        shutil.rmtree(tmp_extract, ignore_errors=True)
    except Exception:
        pass


def install_voice_files(*, voice_id: str, model_bytes: bytes, config_bytes: bytes) -> None:
    vid = (voice_id or "").strip() or DEFAULT_VOICE_ID
    mdir = piper_models_dir()
    mdir.mkdir(parents=True, exist_ok=True)
    model_path, cfg_path = piper_voice_paths(vid)
    tmp1 = model_path.with_suffix(model_path.suffix + ".tmp")
    tmp2 = cfg_path.with_suffix(cfg_path.suffix + ".tmp")
    tmp1.write_bytes(model_bytes)
    tmp2.write_bytes(config_bytes)
    tmp1.replace(model_path)
    tmp2.replace(cfg_path)


def offline_tts_status(*, voice_id: str | None = None, probe: bool = False) -> OfflineTtsStatus:
    vid = (voice_id or "").strip() or DEFAULT_VOICE_ID
    exe = piper_exe_path()
    model, cfg = piper_voice_paths(vid)
    cfg_obj = _installed_voice_config(vid)
    pt = _voice_phoneme_type_from_config(cfg_obj)
    runtime_ready = (model.exists() and cfg.exists() and _python_piper_zh_ready()) if pt == "pinyin" else exe.exists()
    installed = bool(runtime_ready and model.exists() and cfg.exists())
    if not installed:
        detail = "未安装离线配音（需要可用运行时和中文模型）。"
        return OfflineTtsStatus(installed=False, ok=False, backend="offline_piper", voice_id=vid, detail=detail)

    if not probe:
        return OfflineTtsStatus(installed=True, ok=True, backend="offline_piper", voice_id=vid, detail="已安装")

    # Probe synthesis quickly.
    try:
        out_dir = settings.exports_dir / "tts_previews"
        out_dir.mkdir(parents=True, exist_ok=True)
        probe_id = f"{os.getpid()}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
        wav = out_dir / f"_offline_probe_{probe_id}.wav"
        mp3 = out_dir / f"_offline_probe_{probe_id}.mp3"
        if wav.exists():
            wav.unlink(missing_ok=True)
        if mp3.exists():
            mp3.unlink(missing_ok=True)
        offline_piper_audio_only(text="你好", voice_id=vid, wav_path=wav)
        # Convert to mp3 (render expects mp3)
        run_ffmpeg(["-y", "-i", ffmpeg_path(wav), "-c:a", "libmp3lame", "-b:a", "128k", ffmpeg_path(mp3)])
        ok = mp3.exists() and mp3.stat().st_size > 0
        try:
            wav.unlink(missing_ok=True)
            mp3.unlink(missing_ok=True)
        except Exception:
            pass
        return OfflineTtsStatus(installed=True, ok=bool(ok), backend="offline_piper", voice_id=vid, detail="合成正常" if ok else "合成失败")
    except Exception as e:
        return OfflineTtsStatus(installed=True, ok=False, backend="offline_piper", voice_id=vid, detail=str(e)[:300])


def install_offline_piper(
    *,
    voice_id: str | None = None,
    progress_cb=None,
) -> None:
    """Install Piper binary and a voice model into data/assets.

    progress_cb(got, total, phase) is optional.
    """

    vid = (voice_id or "").strip() or DEFAULT_VOICE_ID
    # voice_id can be any known voice in catalog.

    install_piper_engine(progress_cb=progress_cb)
    install_piper_voice(voice_id=vid, progress_cb=progress_cb)


def install_piper_engine(*, progress_cb=None) -> None:
    plat = _platform_key()
    asset = PIPER_BINARIES.get(plat)
    if not asset:
        raise RuntimeError(f"unsupported platform: {plat}")

    # Prefer nested exe where DLLs are colocated.
    if piper_exe_path().exists():
        return

    override_url = os.environ.get("CHENGPIAN_PIPER_BIN_URL", "").strip()

    root = piper_root_dir()
    bdir = piper_bin_dir()
    bdir.mkdir(parents=True, exist_ok=True)

    archive = root / asset.name

    def _dl_cb(got, total):
        if callable(progress_cb):
            progress_cb(got, total, "download_piper")

    try:
        _download_to((override_url or asset.url), archive, job_cb=_dl_cb)
    except Exception:
        if not override_url:
            proxy = "https://ghproxy.com/"
            _download_to(proxy + asset.url, archive, job_cb=_dl_cb)
        else:
            raise

    tmp_extract = root / "_extract_tmp"
    if tmp_extract.exists():
        shutil.rmtree(tmp_extract, ignore_errors=True)
    tmp_extract.mkdir(parents=True, exist_ok=True)
    _extract_archive(archive, tmp_extract)

    exe_name = "piper.exe" if os.name == "nt" else "piper"
    found = None
    for p in tmp_extract.rglob(exe_name):
        if p.is_file():
            found = p
            break
    if not found:
        raise RuntimeError("piper 安装包中未找到可执行文件")

    for child in bdir.iterdir() if bdir.exists() else []:
        try:
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)
        except Exception:
            pass
    for item in tmp_extract.iterdir():
        dst = bdir / item.name
        try:
            if item.is_dir():
                shutil.copytree(item, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dst)
        except Exception:
            pass

    exe_dst = piper_exe_path()
    if not exe_dst.exists():
        try:
            exe_dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(found, exe_dst)
        except Exception:
            pass

    try:
        shutil.rmtree(tmp_extract, ignore_errors=True)
    except Exception:
        pass


def install_piper_voice(*, voice_id: str, progress_cb=None) -> None:
    vid = (voice_id or "").strip() or DEFAULT_VOICE_ID
    voice = voice_urls_for(vid)
    model_path, cfg_path = piper_voice_paths(vid)

    def _dl_voice_cb(got, total):
        if callable(progress_cb):
            progress_cb(got, total, "download_voice")

    if not model_path.exists() or model_path.stat().st_size <= 0:
        try:
            _download_to(voice.model_url_primary, model_path, job_cb=_dl_voice_cb)
        except Exception:
            _download_to(voice.model_url_fallback, model_path, job_cb=_dl_voice_cb)
    if not cfg_path.exists() or cfg_path.stat().st_size <= 0:
        try:
            _download_to(voice.config_url_primary, cfg_path)
        except Exception:
            _download_to(voice.config_url_fallback, cfg_path)


def install_all_compatible_offline_voices(*, progress_cb=None) -> dict:
    voices = list_available_offline_voices(force=True)
    compatible_rows = [row for row in voices if bool(row.get("compatible"))]

    install_piper_engine(
        progress_cb=lambda got, total, phase: progress_cb(
            {
                "phase": phase,
                "voice_id": "piper",
                "index": 0,
                "total": len(compatible_rows),
                "got": int(got or 0),
                "size_total": int(total or 0),
                "status": "engine",
                "message": "下载引擎",
            }
        )
        if callable(progress_cb)
        else None
    )

    installed: list[str] = []
    skipped: list[dict] = []
    failed: list[dict] = []

    for row in voices:
      vid = str(row.get("voice_id") or "").strip()
      if not vid:
          continue
      if not bool(row.get("compatible")):
          skipped.append({"voice_id": vid, "reason": str(row.get("reason") or "不兼容")})
          continue
      idx = len(installed) + len(failed)

      def _cb(got: int, total: int, phase: str):
          if callable(progress_cb):
              progress_cb(
                  {
                      "phase": phase,
                      "voice_id": vid,
                      "index": idx + 1,
                      "total": len(compatible_rows),
                      "got": int(got or 0),
                      "size_total": int(total or 0),
                      "status": "voice",
                      "message": "安装音色",
                  }
              )

      try:
          install_piper_voice(voice_id=vid, progress_cb=_cb)
          installed.append(vid)
      except Exception as e:
          failed.append({"voice_id": vid, "reason": str(e)[:240]})

    return {
        "discovered_count": len(voices),
        "compatible_count": len(compatible_rows),
        "installed_voice_ids": installed,
        "skipped": skipped,
        "failed": failed,
    }


def offline_piper_audio_only(
    *,
    text: str,
    voice_id: str | None = None,
    wav_path: Path,
    length_scale: float | None = None,
    noise_scale: float | None = None,
    noise_w: float | None = None,
) -> None:
    """Synthesize audio to wav using Piper.

    Piper reads text from stdin.
    """

    vid = (voice_id or "").strip() or DEFAULT_VOICE_ID
    exe = piper_exe_path()
    model, cfg = piper_voice_paths(vid)
    cfg_obj = _installed_voice_config(vid)
    pt = _voice_phoneme_type_from_config(cfg_obj)
    if pt == "pinyin":
        if not _python_piper_zh_ready():
            raise RuntimeError("离线中文增强音色依赖未安装：请先安装 piper-tts 中文扩展")
        if not model.exists() or not cfg.exists():
            raise RuntimeError("离线配音未安装：缺少中文模型文件")
        return _python_piper_audio_only(
            text=text,
            voice_id=vid,
            wav_path=wav_path,
            length_scale=length_scale,
            noise_scale=noise_scale,
            noise_w=noise_w,
        )
    if not exe.exists():
        raise RuntimeError("离线配音未安装：缺少 piper 可执行文件")
    if not model.exists() or not cfg.exists():
        raise RuntimeError("离线配音未安装：缺少中文模型文件")
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = wav_path.with_suffix(wav_path.suffix + ".tmp")
    if tmp.exists():
        tmp.unlink(missing_ok=True)

    cmd = [str(exe), "--model", str(model), "--config", str(cfg), "--output_file", str(tmp)]
    # Optional expressive controls (Piper CLI).
    try:
        if length_scale is not None:
            cmd += ["--length_scale", str(float(length_scale))]
        if noise_scale is not None:
            cmd += ["--noise_scale", str(float(noise_scale))]
        if noise_w is not None:
            cmd += ["--noise_w", str(float(noise_w))]
    except Exception:
        pass
    p = subprocess.run(
        cmd,
        input=(text or "").encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=90,
    )
    if p.returncode != 0:
        err = (p.stderr or b"").decode("utf-8", errors="ignore")
        out = (p.stdout or b"").decode("utf-8", errors="ignore")
        msg = (err.strip() or out.strip() or f"piper failed ({p.returncode})")
        raise RuntimeError(msg[:500])

    if (not tmp.exists()) or tmp.stat().st_size <= 0:
        raise RuntimeError("piper 未生成有效音频")
    tmp.replace(wav_path)
