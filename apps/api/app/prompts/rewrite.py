from app.prompts.base import filmable_rules, json_only_rules, safety_rules, spoken_chinese_rules
from app.prompts.channels import avoid_phrases, channel_style, ending_tone, expression_rules, observation_focus, track_content_rules
from app.prompts.composer import build_messages
from app.prompts.schemas import rewrite_storyboard_schema
from app.prompts.workflows import workflow_rules


def _continuity_rules(pack_key: str) -> list[str]:
    key = str(pack_key or "").strip().lower()
    channel_rule = "Keep the same topic world while allowing informative cutaway only when the narration explicitly changes place, time, or evidence."
    if key in ("emotion", "family_cn"):
        channel_rule = "Keep adjacent scenes in the same relationship moment whenever possible: same person, same room, same emotional tension, then change shot distance or action slightly."
    elif key == "history":
        channel_rule = "Keep adjacent scenes under the same historical clue, artifact, or place first; use cutaway only for evidence, timeline shift, or consequence."
    elif key == "career":
        channel_rule = "Keep adjacent scenes inside the same workplace context first: same office, meeting, desk, commute, or chat thread before jumping elsewhere."
    return [
        "Visual continuity rules:",
        "- Adjacent scenes should usually share the same subject or the same setting.",
        "- Build 2-4 consecutive scenes as one micro-scene before moving to a new place.",
        "- Prefer same_subject_new_action / same_place_new_angle / push_in / pull_out before hard_shift.",
        "- Use hard_shift only when narration clearly introduces contrast, flashback, result, or a new stage.",
        "- Avoid abrupt jumps like indoor person -> empty landscape, day -> night, realistic people -> abstract illustration without motivation.",
        f"- {channel_rule}",
        "- continuity_mode must be one of: hold, same_subject_new_action, same_place_new_angle, push_in, pull_out, cutaway, hard_shift.",
    ]


def build_rewrite_storyboard_messages(*, pack, workflow: str, source_text: str, level: str, character_profile: str, prof: dict, visual_style: str, negative: str, aspect: str = "landscape"):
    duration_part = (
        f"Total duration window: {int(float(prof.get('target_min_sec', 0.0) or 0.0))}-{int(float(prof.get('target_max_sec', 0.0) or 0.0))} seconds. Target about {int(float(prof.get('target_sec', 0.0) or 0.0))} seconds."
        if float(prof.get("target_min_sec", 0.0) or 0.0) > 0 and float(prof.get("target_max_sec", 0.0) or 0.0) > 0
        else f"Target total duration about {int(float(prof.get('target_sec', 0.0) or 0.0))} seconds."
    )
    return build_messages(
        system_parts=[
            f"You are a Chinese short-video scriptwriter and storyboard director for Douyin ({'vertical 9:16' if str(aspect or '').strip().lower() == 'portrait' else 'horizontal 16:9'}).",
            json_only_rules(),
            f"Channel style: {channel_style(pack.key)}",
            f"Observation focus: {observation_focus(pack.key)}",
            f"Workflow: {str(workflow or 'mix').strip().lower() or 'mix'}",
            "Track-specific content rules:",
            track_content_rules(pack.key),
            "Expression rules:",
            *expression_rules(pack.key),
            f"Ending tone: {ending_tone(pack.key)}",
            f"Avoid these phrases or tones: {avoid_phrases(pack.key)}",
            workflow_rules(workflow),
            spoken_chinese_rules(),
            filmable_rules(),
            safety_rules(),
            f"JSON schema:\n{rewrite_storyboard_schema()}",
            *_continuity_rules(getattr(pack, "key", "")),
            "Additional task: rewrite the user's source text into an original spoken script for Douyin.",
            "Keep key facts, improve clarity and pacing, avoid plagiarism, and keep it like real spoken Chinese.",
            f"Rewrite level: {level} (safe=more conservative, strong=more original).",
            "Style constraints:",
            "- Pick one clear sub-theme under the selected track; do not write broad all-in-one commentary.",
            "- For each scene, give concrete searchable visuals rather than abstract ideas.",
            "- visual_intent must include subject, action, setting, time, shot, camera_angle, lighting, composition, motion_intent, continuity_mode, transition_motivation.",
            "- transition_hint must match the visual cut logic: continue / contrast / cut.",
            "- lighting must be practical and believable, not only broad adjectives.",
            "- composition must describe shot framing and subject placement clearly.",
            "- motion_intent must describe a subtle video-frame movement such as slow push in / gentle pull out / subtle pan left / subtle pan right / hold still.",
            "- Do not rewrite into fixed short-video template language or title-style slogans.",
            "- Avoid expressions like 最……的是 / 你以为…… / 90%的人…… / 先给结果 / 记住这个道理.",
        ],
        user_parts=[
            "Rewrite the following source text into a short-video script and storyboard.",
            f"Character profile (optional): {character_profile}" if character_profile else "",
            f"Workflow: {str(workflow or 'mix').strip().lower() or 'mix'}",
            f"Scenes: {int(prof.get('scene_count', 8))}",
            f"Default duration per scene: {float(prof.get('scene_duration_sec', 6.0))}",
            duration_part,
            f"Visual style keywords: {visual_style}",
            f"Negative prompt keywords: {negative}",
            "Return the same strict storyboard schema as mix generation, including media_query, search_en and visual_intent.",
            "Make scene-2 continue scene-1 context whenever possible, and keep the first 3 scenes inside one coherent visual world.",
            "Source text:",
            "---",
            source_text,
            "---",
            "Return JSON only.",
        ],
    )
