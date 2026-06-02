
# A small, extensible intent catalog for "networkized" short-video writing.
# The LLM selects intent_family + format based on topic/context.


def catalog_for_pack(pack_key: str) -> dict:
    k = (pack_key or "").strip().lower()
    if k == "history":
        return {
            "pack": "history",
            "intents": [
                {
                    "id": "history_suspense_reveal",
                    "desc": "悬念开场 -> 史料锚点 -> 反转揭示 -> 留悬念追更",
                },
                {
                    "id": "history_misunderstood_person",
                    "desc": "被误解的人物/事件，先大众印象再反证",
                },
                {
                    "id": "history_lost_artifact",
                    "desc": "失落文物/密信/地图等线索叙事",
                },
                {
                    "id": "history_power_game",
                    "desc": "权力博弈（朝堂/宫廷/派系）但避免阴谋论绝对化",
                },
            ],
            "formats": [
                {"id": "narration_suspense", "desc": "悬疑解说口播"},
                {"id": "cold_knowledge", "desc": "冷知识反转口播"},
            ],
        }
    if k == "emotion":
        return {
            "pack": "emotion",
            "intents": [
                {"id": "emotion_unspoken_need", "desc": "嘴上不说、心里失望：潜台词与未被看见的需要"},
                {"id": "emotion_boundary", "desc": "关系边界失守：过度付出、试探和退让"},
                {"id": "emotion_disappointment", "desc": "失望积累：不是一次争吵，而是很多次没被接住"},
                {"id": "emotion_controlled_care", "desc": "以关心之名的控制：看似在乎，实则压迫"},
                {"id": "emotion_breakup_rebuild", "desc": "分开后的后劲：复盘、清醒和自我重建"},
                {"id": "emotion_misunderstanding", "desc": "表面是生气，实际是委屈：误解与错位沟通"},
                {"id": "emotion_online_dating", "desc": "相亲/社交平台：筛选标准、边界感和风险识别"},
            ],
            "formats": [
                {"id": "story_confession", "desc": "第一人称倾诉（场景-潜台词-扎心结论）"},
                {"id": "warm_story", "desc": "关系故事（细节-误解-看见真实心理）"},
                {"id": "rant_drama", "desc": "轻冲突短剧（嘴硬/沉默/冷处理/反问）"},
                {"id": "case_analysis", "desc": "案例拆解（问题-误区-可执行建议）"},
            ],
        }

    if k == "family_cn":
        return {
            "pack": "family_cn",
            "intents": [
                {"id": "family_cn_control", "desc": "父母控制型关爱：替你决定的人生"},
                {"id": "family_cn_comparison", "desc": "比较式教育：拿别人孩子当标尺"},
                {"id": "family_cn_face_culture", "desc": "面子优先：关系维护压过真实需求"},
                {"id": "family_cn_marriage_pressure", "desc": "催婚催育：家庭期待与个人边界"},
                {"id": "family_cn_emotion_blackmail", "desc": "情感勒索：以孝顺之名消耗个体"},
            ],
            "formats": [
                {"id": "family_story", "desc": "家庭故事复盘（事件-冲突-和解）"},
                {"id": "logic_breakdown", "desc": "逻辑拆解（常见话术-真实问题-替代说法）"},
                {"id": "boundary_handbook", "desc": "边界手册（可直接使用的表达模板）"},
            ],
        }

    # career (default)
    return {
        "pack": "career",
        "intents": [
            {"id": "leader_communication", "desc": "上下级沟通错位：目标、预期、反馈"},
            {"id": "blame_shift", "desc": "背锅/甩锅：事实留痕与边界表达"},
            {"id": "overtime_culture", "desc": "加班与临时任务：优先级协商"},
            {"id": "performance_review", "desc": "绩效复盘：结果导向表达与修正"},
            {"id": "job_change_transition", "desc": "转岗/跳槽：风险评估与沟通策略"},
            {"id": "meeting_nonsense", "desc": "无效会议：推进决策与落地机制"},
        ],
        "formats": [
            {"id": "scene_rant", "desc": "场景吐槽（真实细节+反转）"},
            {"id": "checklist_tips", "desc": "清单建议（可执行步骤）"},
            {"id": "case_replay", "desc": "案例复盘（问题-决策-结果）"},
        ],
    }


def template_bank_for_pack(pack_key: str) -> list[dict]:
    """High-performing short-video expression templates by channel pack.

    These templates are platform-expression structures (how to speak), not topic tags.
    """

    k = (pack_key or "").strip().lower()
    if k == "history":
        return [
            {
                "id": "hist_clue_reveal",
                "type": "suspense_reveal",
                "desc": "异常细节开场 -> 线索递进 -> 关键反转 -> 留悬念",
                "hook_style": "detail_anomaly",
            },
            {
                "id": "hist_public_misread",
                "type": "myth_busting",
                "desc": "大众印象 -> 证据拆解 -> 认知反转 -> 再抛问题",
                "hook_style": "common_belief_flip",
            },
            {
                "id": "hist_power_chain",
                "type": "cause_effect_chain",
                "desc": "事件起点 -> 人物博弈 -> 连锁后果 -> 当代映射",
                "hook_style": "critical_turning_point",
            },
        ]
    if k == "emotion":
        return [
            {
                "id": "emo_unspoken_conflict",
                "type": "scene_subtext_reveal",
                "desc": "具体场景开场 -> 表面冲突 -> 潜台词揭示 -> 扎心结论",
                "hook_style": "scene_conflict",
            },
            {
                "id": "emo_silent_distance",
                "type": "cold_warm_turn",
                "desc": "沉默细节 -> 距离拉开 -> 真实动机 -> 反问收束",
                "hook_style": "quiet_tension",
            },
            {
                "id": "emo_case_breakdown",
                "type": "case_analysis",
                "desc": "一句结论 -> 案例切片 -> 误区点名 -> 可执行边界表达",
                "hook_style": "verdict_first",
            },
        ]
    if k == "family_cn":
        return [
            {
                "id": "fam_phrase_disassemble",
                "type": "phrase_deconstruction",
                "desc": "高频话术开场 -> 真实意图拆解 -> 伤害后果 -> 替代说法",
                "hook_style": "familiar_phrase",
            },
            {
                "id": "fam_table_conflict",
                "type": "home_scene_conflict",
                "desc": "家庭餐桌场景 -> 情绪升级 -> 边界表达 -> 关系修复",
                "hook_style": "domestic_tension",
            },
            {
                "id": "fam_boundary_handbook",
                "type": "boundary_steps",
                "desc": "问题点名 -> 三步边界 -> 低对抗表达 -> 收束结论",
                "hook_style": "practical_steps",
            },
        ]
    return [
        {
            "id": "car_meeting_breakpoint",
            "type": "workplace_conflict",
            "desc": "会议瞬间开场 -> 冲突升级 -> 证据反转 -> 可执行结论",
            "hook_style": "meeting_breakpoint",
        },
        {
            "id": "car_case_replay",
            "type": "case_replay",
            "desc": "结果先行 -> 复盘关键节点 -> 决策得失 -> 行动建议",
            "hook_style": "result_first",
        },
        {
            "id": "car_phrase_upgrade",
            "type": "language_upgrade",
            "desc": "低效说法 -> 升级表达 -> 场景演示 -> 结尾收束",
            "hook_style": "before_after_phrase",
        },
    ]


def select_template_for_intent(pack_key: str, *, intent_family: str = "", format_id: str = "") -> dict:
    bank = template_bank_for_pack(pack_key)
    if not bank:
        return {"id": "generic_template", "type": "generic", "desc": "具体场景开场 -> 冲突推进 -> 结尾收束", "hook_style": "scene_conflict"}

    intent = (intent_family or "").strip().lower()
    fmt = (format_id or "").strip().lower()
    def _pick(template_id: str) -> dict:
        for t in bank:
            if str(t.get("id", "")) == template_id:
                return t
        return bank[0]

    pk = (pack_key or "").strip().lower()
    if pk == "career":
        if any(x in intent for x in ("meeting", "blame", "leader")):
            return _pick("car_meeting_breakpoint")
        if any(x in fmt for x in ("case", "replay")):
            return _pick("car_case_replay")
        return _pick("car_phrase_upgrade")

    if pk == "emotion":
        if any(x in intent for x in ("boundary", "disappointment", "misunderstanding")):
            return _pick("emo_unspoken_conflict")
        if any(x in fmt for x in ("analysis", "case")):
            return _pick("emo_case_breakdown")
        return _pick("emo_unspoken_conflict")

    if pk == "family_cn":
        if any(x in intent for x in ("comparison", "control", "emotion_blackmail")):
            return _pick("fam_phrase_disassemble")
        return _pick("fam_boundary_handbook")

    if pk == "history":
        if any(x in intent for x in ("lost_artifact", "suspense")):
            return _pick("hist_clue_reveal")
        if any(x in intent for x in ("misunderstood", "misread")):
            return _pick("hist_public_misread")
        return _pick("hist_power_chain")

    return bank[0]


def template_prompt_hint(template_obj: dict) -> str:
    if not isinstance(template_obj, dict):
        return "具体场景开场 -> 冲突推进 -> 结尾收束"
    tid = str(template_obj.get("id", "") or "").strip()
    ttype = str(template_obj.get("type", "") or "").strip()
    desc = str(template_obj.get("desc", "") or "").strip()
    hs = str(template_obj.get("hook_style", "") or "").strip()
    return f"template={tid} type={ttype} hook={hs}; structure={desc}"
