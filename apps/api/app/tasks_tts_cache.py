from pathlib import Path


def build_generated_tts_cache_paths(
    *,
    pid: int,
    project_script: str,
    voice_name: str,
    voice_rate: str,
    channel_key: str,
    workflow: str,
    stable_digest,
    project_audio_dir,
    project_subtitles_dir,
) -> tuple[str, Path, Path]:
    tts_cache_key = stable_digest([
        "tts_text_norm_v2",
        "subtitle_display_no_punct_v2",
        "edge_plain_text_v2",
        int(pid),
        project_script or "",
        voice_name,
        voice_rate,
        channel_key or "",
        workflow,
    ])
    audio_path = project_audio_dir(int(pid)) / f"voice_cache_{tts_cache_key}.mp3"
    srt_path = project_subtitles_dir(int(pid)) / f"subtitle_cache_{tts_cache_key}.srt"
    return tts_cache_key, audio_path, srt_path
