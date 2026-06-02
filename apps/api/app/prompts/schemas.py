def intent_classifier_schema() -> str:
    return '{"intent_family": string, "format": string, "tone": string, "roles": [string], "conflict": string, "risk_flags": [string]}'


def beat_planner_schema() -> str:
    return '{"beats": [string], "visual_elements": [string], "must_avoid": [string]}'


def storyboard_writer_schema() -> str:
    return (
        '{\n'
        '  "script": string,\n'
        '  "scenes": [\n'
        '    {\n'
        '      "idx": integer (1..N),\n'
        '      "narration": string (Chinese, spoken, short sentences),\n'
        '      "on_screen_text": string (Chinese, optional),\n'
        '      "media_query": string (Chinese, short keywords),\n'
        '      "search_en": string (ENGLISH stock keywords, 2-6 words),\n'
        '      "visual_intent": {"subject": string, "action": string, "setting": string, "time": string, "shot": string, "camera_angle": string, "lighting": string, "composition": string, "motion_intent": string, "continuity_mode": string, "transition_motivation": string, "anchor_id": string, "anchor_type": string, "key_objects": [string], "emotion_state": string, "must_show": [string], "must_not_show": [string], "text_policy": {"mode": string, "content": string, "placement": string, "readability": string, "style": string, "max_chars": integer}},\n'
        '      "visual_theme": string,\n'
        '      "scene_group": integer,\n'
        '      "transition_hint": string,\n'
        '      "image_prompt": string (optional),\n'
        '      "image_negative": string (optional),\n'
        '      "duration_sec": number\n'
        '    }\n'
        '  ]\n'
        '}'
    )


def rewrite_storyboard_schema() -> str:
    return storyboard_writer_schema()


def repair_storyboard_schema() -> str:
    return storyboard_writer_schema()
