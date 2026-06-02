from pathlib import Path

from app.tasks_tts_pipeline import (
    AudioSubtitlePrepResult,
    ensure_silent_voice_mp3 as ensure_silent_voice_mp3_impl,
    prepare_audio_and_subtitles as prepare_audio_and_subtitles_impl,
)


class AudioSubtitlePrepResultCompat(AudioSubtitlePrepResult):
    pass


def ensure_silent_voice_mp3(audio_path: Path, *, duration_sec: float) -> None:
    ensure_silent_voice_mp3_impl(audio_path, duration_sec=duration_sec)


def prepare_audio_and_subtitles(
    *,
    job_id: int,
    target_job_id: int,
    pid: int,
    project,
    scenes,
    script_text: str,
    audio_path: Path,
    srt_path: Path,
    has_voice_upload: bool,
    has_subtitle_upload: bool,
    require_tts: bool,
    planned_duration: float,
    base_durs: list[float],
    voice_name: str,
    voice_rate: str,
    reuse_generated_tts: bool,
    temp_file_prefix: str,
    on_update,
    friendly_tts_failure_message,
    subtitle_has_visible_cues,
) -> AudioSubtitlePrepResultCompat:
    result = prepare_audio_and_subtitles_impl(
        job_id=job_id,
        target_job_id=target_job_id,
        pid=pid,
        project=project,
        scenes=scenes,
        script_text=script_text,
        audio_path=audio_path,
        srt_path=srt_path,
        has_voice_upload=has_voice_upload,
        has_subtitle_upload=has_subtitle_upload,
        require_tts=require_tts,
        planned_duration=planned_duration,
        base_durs=base_durs,
        voice_name=voice_name,
        voice_rate=voice_rate,
        reuse_generated_tts=reuse_generated_tts,
        temp_file_prefix=temp_file_prefix,
        on_update=on_update,
        friendly_tts_failure_message=friendly_tts_failure_message,
        subtitle_has_visible_cues=subtitle_has_visible_cues,
    )
    return AudioSubtitlePrepResultCompat(**result.__dict__)
