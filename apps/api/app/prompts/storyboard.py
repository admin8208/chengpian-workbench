from app.prompts.base import filmable_rules, json_only_rules, safety_rules, spoken_chinese_rules
from app.prompts.channels import avoid_phrases, channel_style, ending_tone, expression_rules, observation_focus, track_content_rules
from app.prompts.composer import build_messages
from app.prompts.schemas import beat_planner_schema, intent_classifier_schema, storyboard_writer_schema
from app.prompts.workflows import workflow_rules


def _continuity_rules(pack_key: str) -> list[str]:
    key = str(pack_key or "").strip().lower()
    channel_rule = "Let new places appear only when the narration itself advances to a new clue, stage, or evidence point."
    if key in ("emotion", "family_cn"):
        channel_rule = "Keep emotional scenes inside one shared space and relationship beat first; change gaze, gesture, distance, or silence before changing place."
    elif key == "history":
        channel_rule = "Keep one historical clue continuous across adjacent scenes, then use evidence cutaway or timeline shift only when needed."
    elif key == "career":
        channel_rule = "Keep the workplace context coherent across adjacent scenes, using desk, meeting, commute, phone, or chat as the same anchor line."
    return [
        "Continuity rules:",
        "- Adjacent scenes should usually share subject or setting, and the first 3 scenes must feel like one coherent visual world.",
        "- Build 2-4 scenes as one micro-scene before moving to a clearly new place.",
        "- Prefer continuity_mode = same_subject_new_action / same_place_new_angle / push_in / pull_out before cutaway or hard_shift.",
        "- Use hard_shift only for explicit contrast, flashback, result reveal, or timeline jump.",
        f"- {channel_rule}",
    ]


def build_intent_classifier_messages(*, pack, topic: str, hook_style: str, catalog: dict):
    system = build_messages(
        system_parts=[
            "You are a Chinese short-video showrunner. Identify the REAL internet context of the topic.",
            json_only_rules(),
            f"JSON schema: {intent_classifier_schema()}",
            "Rules: intent_family must be one of the provided candidates for the channel; format must be one of the provided candidates; tone should be short (e.g. sharp/funny/calm/suspense/warm).",
            "Do not classify by cliché hook language. Classify by real scene, conflict, relationship dynamic, evidence chain, or communication problem.",
        ],
        user_parts=[
            f"Channel: {pack.name} ({pack.key})",
            f"Channel style: {channel_style(pack.key)}",
            f"hook_style: {hook_style}",
            f"Observation focus: {observation_focus(pack.key)}",
            f"Topic (Chinese): {topic}",
            f"Candidate intents: {catalog.get('intents', [])}",
            f"Candidate formats: {catalog.get('formats', [])}",
            "Pick the best matching intent_family and format based on real-world short-video context.",
        ],
    )
    return system


def build_beat_planner_messages(*, pack, topic: str, intent_family: str, format_id: str, tone: str, roles: list[str], conflict: str, template_id: str, template_type: str, template_hint: str, n: int):
    extra = ""
    if str(pack.key or "").strip().lower() == "emotion":
        extra = "For emotion track, beats must feel like one real relationship scene first, then reveal hidden psychology, then land one restrained but piercing conclusion."
    return build_messages(
        system_parts=[
            "You are a Chinese Douyin script director. Plan a beat-by-beat structure that feels like real internet content.",
            json_only_rules(),
            f"JSON schema: {beat_planner_schema()}",
            "Rules: beats length must equal Scenes N; each beat is 1 short Chinese sentence describing story function. visual_elements must be concrete and filmable.",
            "Do not design beats around slogan hooks or formulaic emotional manipulation. The opening beat should feel like entering a real scene.",
            "Plan 2-4 adjacent beats as one coherent micro-scene before changing place or timeline.",
        ],
        user_parts=[
            f"Channel: {pack.name} ({pack.key})",
            f"Topic: {topic}",
            f"Observation focus: {observation_focus(pack.key)}",
            f"Intent: {intent_family}",
            f"Format: {format_id}",
            f"Tone: {tone}",
            f"Roles: {roles}",
            f"Conflict: {conflict}",
            f"Selected template: {template_id} ({template_type})",
            f"Template hint: {template_hint}",
            f"Scenes N: {n}",
            extra,
            "Plan beats and visual elements. Avoid naming real companies or real persons.",
            "Make beat-1 and beat-2 strictly follow the selected template hook style and conflict setup.",
        ],
    )


def build_storyboard_writer_messages(*, pack, workflow: str, topic: str, intent_family: str, format_id: str, tone: str, roles: list[str], conflict: str, template_id: str, template_type: str, template_hint: str, template_hook_style: str, character_profile: str, n: int, base_dur: float, prof: dict, beats: list[str], visual_elements: list[str], must_avoid: list[str]):
    pack_key = str(pack.key or "").strip().lower()
    aspect = str((prof or {}).get("aspect") or "landscape").strip().lower() or "landscape"
    frame_ratio = "vertical 9:16" if aspect == "portrait" else "horizontal 16:9"
    emotion_extra = ""
    if pack_key == "emotion":
        emotion_extra = (
            "For emotion track:\n"
            "- Write it like someone recounting one specific relationship scene, not like an essay.\n"
            "- Open with a specific moment, not a moral.\n"
            "- Every 2-3 scenes should expose one deeper motive or subtext behind the visible behavior.\n"
            "- Avoid broad advice like 你要学会 / 我们应该 / 一定要 unless it is the final conclusion.\n"
            "- Include one line that could work alone as a cover subtitle or punchline.\n"
            "- Prefer emotional realism: 嘴硬、沉默、冷处理、过度付出、没被接住、控制式关心、误会积累.\n"
            "- Use first or second person (我/你) to increase empathy and immersion.\n"
            "- Each scene narration should not exceed 20 Chinese characters.\n"
            "- First 3 seconds must have a strong emotional hook (具体场景 + 情感冲突).\n"
            "- Use concrete scene descriptions: 深夜的厨房、未读的消息、转身的背影、沉默的餐桌.\n"
            "- Avoid starting sentences with 其实、但是、所以; use more natural transitions.\n"
            "- End with a piercing conclusion or unexpected twist that resonates.\n"
            "- Use colloquial expressions, avoid written/formal language.\n"
            "- Each scene should have one specific emotional detail, not general statements."
        )
    duration_part = (
        f"Total duration window: {int(float(prof.get('target_min_sec', 0.0) or 0.0))}-{int(float(prof.get('target_max_sec', 0.0) or 0.0))} sec; target {int(float(prof.get('target_sec', 0.0) or 0.0))} sec."
        if float(prof.get("target_min_sec", 0.0) or 0.0) > 0 and float(prof.get("target_max_sec", 0.0) or 0.0) > 0
        else f"Total duration target: {int(float(prof.get('target_sec', 0.0) or 0.0))} sec."
    )
    return build_messages(
        system_parts=[
            f"You are a Chinese short-video screenwriter and storyboard director for Douyin ({frame_ratio}).",
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
            f"JSON schema:\n{storyboard_writer_schema()}",
            *_continuity_rules(pack.key),
            "Rules:",
            "- Scene 1 is a 0-3s opening, but it must open from a real moment, object, line, or atmosphere instead of a slogan.",
            "- Follow the selected structure, but do not let structure become a visible formula.",
            "- search_en must be concrete nouns+actions+setting (no punctuation).",
            "- Keep visual continuity through coherent scene context and transitions.",
            "- Group scenes with similar visual_theme into same scene_group (1-3 groups max).",
            "- Use transition_hint: continue / contrast / cut.",
            "- visual_intent must include subject, action, setting, time, shot, camera_angle, lighting, composition, motion_intent, continuity_mode, transition_motivation.",
            "- lighting must describe believable practical light mood or source, not vague style words only.",
            "- composition must describe framing, subject placement, or negative space in a directly drawable way.",
            "- motion_intent must describe how this shot should feel if converted into a subtle moving video frame: slow push in / gentle pull out / subtle pan left / subtle pan right / hold still.",
            "- Avoid abrupt adjacent jumps of subject+setting unless narration explicitly transitions.",
            "- Do not write like a short-video title, life-coach slogan, or motivational script machine.",
            "- Avoid formulaic expressions like 最……的是 / 你以为…… / 90%的人…… / 先给结果 / 这条建议先收好.",
        ],
        user_parts=[
            f"Channel: {pack.name} ({pack.key})",
            f"Topic: {topic}",
            f"Intent: {intent_family}",
            f"Format: {format_id}",
            f"Tone: {tone}",
            f"Roles: {roles}",
            f"Conflict: {conflict}",
            f"Template: {template_id} ({template_type})",
            f"Template hint: {template_hint}",
            f"Template hook style: {template_hook_style}",
            f"Character profile: {character_profile}" if character_profile else "",
            f"Scenes N: {n}",
            f"Default duration: {base_dur} sec (vary slightly)",
            duration_part,
            f"Beats (must follow): {beats}",
            f"Suggested visual elements: {visual_elements}",
            f"Must avoid: {must_avoid}",
            "For each scene, prefer one concrete short-video shot with visible people/objects/actions instead of abstract commentary.",
            "Use media_query/search_en that a stock site can actually return.",
            "Scene 1 should enter the situation quickly in <=18 Chinese chars, but avoid sounding like a slogan or clickbait title.",
            "Scene 2 should deepen the situation and keep the same contextual anchor whenever possible.",
            emotion_extra,
            "Write the script + scenes now. Return JSON only.",
        ],
    )


def build_network_storyboard_messages(*, pack, workflow: str, topic: str, character_profile: str, n: int, base_dur: float, prof: dict, aspect: str = "landscape"):
    duration_part = (
        f"Total duration window: {int(float(prof.get('target_min_sec', 0.0) or 0.0))}-{int(float(prof.get('target_max_sec', 0.0) or 0.0))} sec; target {int(float(prof.get('target_sec', 0.0) or 0.0))} sec."
        if float(prof.get("target_min_sec", 0.0) or 0.0) > 0 and float(prof.get("target_max_sec", 0.0) or 0.0) > 0
        else f"Total duration target: {int(float(prof.get('target_sec', 0.0) or 0.0))} sec."
    )
    return build_messages(
        system_parts=[
            "You are a Chinese short-video storyboard director for stock-footage remix.",
            json_only_rules(),
            f"Channel style: {channel_style(pack.key)}",
            f"Observation focus: {observation_focus(pack.key)}",
            workflow_rules(workflow),
            spoken_chinese_rules(),
            filmable_rules(),
            safety_rules(),
            f"JSON schema:\n{storyboard_writer_schema()}",
            *_continuity_rules(pack.key),
            "Rules:",
            "- Generate the full script and scenes in one pass.",
            "- Prioritize stock-searchability over image generation details.",
            "- media_query must be concrete short Chinese keywords.",
            "- search_en must be the primary retrieval field, 2-6 English words, visible subject + action + setting.",
            "- image_prompt can be empty or brief when not needed.",
            "- Keep the first 2-3 scenes inside one coherent visual world.",
        ],
        user_parts=[
            f"Channel: {pack.name} ({pack.key})",
            f"Topic: {topic}",
            f"Character profile: {character_profile}" if character_profile else "",
            f"Scenes N: {n}",
            f"Default duration: {base_dur} sec (vary slightly)",
            duration_part,
            "Return directly usable stock-footage storyboard JSON now.",
        ],
    )


def build_ai_storyboard_messages(*, pack, workflow: str, topic: str, character_profile: str, n: int, base_dur: float, prof: dict, aspect: str = "landscape"):
    duration_part = (
        f"Total duration window: {int(float(prof.get('target_min_sec', 0.0) or 0.0))}-{int(float(prof.get('target_max_sec', 0.0) or 0.0))} sec; target {int(float(prof.get('target_sec', 0.0) or 0.0))} sec."
        if float(prof.get("target_min_sec", 0.0) or 0.0) > 0 and float(prof.get("target_max_sec", 0.0) or 0.0) > 0
        else f"Total duration target: {int(float(prof.get('target_sec', 0.0) or 0.0))} sec."
    )
    return build_messages(
        system_parts=[
            "You are a Chinese short-video storyboard director for AI image generation.",
            json_only_rules(),
            f"Target frame: {'vertical 9:16' if str(aspect or '').strip().lower() == 'portrait' else 'horizontal 16:9'}.",
            f"Channel style: {channel_style(pack.key)}",
            f"Observation focus: {observation_focus(pack.key)}",
            workflow_rules(workflow),
            spoken_chinese_rules(),
            filmable_rules(),
            safety_rules(),
            f"JSON schema:\n{storyboard_writer_schema()}",
            *_continuity_rules(pack.key),
            "Rules:",
            "- Generate the full script and scenes in one pass.",
            "- Prioritize image_prompt and visual_intent quality over stock-search fields.",
            "- Every scene must contain clear subject, action, setting, time, and shot.",
            "- Every scene must also contain lighting, composition, and motion_intent inside visual_intent.",
            "- Treat each image as a visual translation of the current scene narration, not a thematic approximation.",
            "- visual_intent must include key_objects, emotion_state, must_show, and must_not_show whenever they are implied by narration.",
            "- visual_intent.text_policy must decide whether this scene forbids text, allows incidental scene text, or needs later overlay text.",
            "- lighting should stay coherent across adjacent scenes in one micro-scene unless the narration intentionally creates contrast.",
            "- composition should say shot size + subject placement + whether clean subtitle-safe negative space is needed.",
            "- motion_intent should use one of: slow push in, gentle pull out, subtle pan left, subtle pan right, hold still.",
            "- The main visible action and key object in narration must be explicitly drawable in image_prompt.",
            "- Do not replace a concrete scene event with generic mood portrait, generic b-roll, or topic-level imagery.",
            "- Keep subject and setting continuity strong across adjacent scenes unless narration explicitly shifts.",
            "- image_prompt should be detailed, visual, and directly useful for image generation.",
            "- search_en can be short and secondary.",
        ],
        user_parts=[
            f"Channel: {pack.name} ({pack.key})",
            f"Topic: {topic}",
            f"Character profile: {character_profile}" if character_profile else "",
            f"Scenes N: {n}",
            f"Default duration: {base_dur} sec (vary slightly)",
            duration_part,
            "Return directly usable AI-image storyboard JSON now.",
        ],
    )
