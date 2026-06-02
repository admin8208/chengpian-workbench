CHANNEL_PROFILES: dict[str, dict] = {
    "emotion": {
        "name": "情感关系",
        "description": "关系冲突、边界感、失望积累等情绪话题。",
        "channel_style": "情感关系内容，优先写真实关系现场、潜台词、失望积累和心理反差，不输出操控术或极端报复建议。",
        "observation_focus": "关系里的潜台词、等待、误解、退让、冷下来之前的细小瞬间，以及表面情绪和真实感受之间的落差。",
        "expression_rules_cn": [
            "先写场景里的动作、停顿、回避和一句没说透的话，不要先下结论。",
            "把委屈、嘴硬、误解、失望写成能被看见的细节，不要只写情绪标签。",
            "人物不要扁平，不要把关系写成单向受害或单向操控。",
            "收尾更像看清一层关系，而不是给一句金句。",
        ],
        "avoid_phrases": ["最扎心的是", "看哭了", "女生一定要", "清醒一点", "这种人千万别碰"],
        "ending_tone": "像把一段关系里的真实感受看明白了一层，而不是直接给道理。",
        "content_rules": (
            "- Focus on one emotional mechanism only: unmet needs, boundary collapse, disappointment buildup, controlled care, misunderstanding, breakup aftertaste, or dating filter.\n"
            "- Start from one concrete relationship moment before any conclusion: unread message, dining table silence, doorway pause, half-finished sentence, looking away, turning back, deleting chat.\n"
            "- Prefer spoken Chinese with subtext and human contradiction; avoid empty preaching and universal life lessons.\n"
            "- Each scene should show a visible relationship moment: looking away, waiting, chatting, arguing, leaving, silence, checking phone, not replying.\n"
            "- At least one line should reveal the contrast between surface emotion and real feeling."
        ),
        "query_bias": ["sad woman alone", "couple argument home", "chat message phone", "night city loneliness"],
        "hook_pool": ["真正让人难受的，不是那句话本身", "关系开始变冷，往往不是从争吵开始的", "有些失望，都是一点点攒出来的"],
        "image_style": "emotional, intimate, soft lighting, warm tones",
        "image_setting": "modern Chinese apartment, cozy cafe, city street at night, bedroom",
        "image_mood": "melancholic, reflective, warm, bittersweet",
        "tts_profile": {
            "edge_voices": ["zh-CN-XiaoyiNeural", "zh-CN-XiaoxiaoNeural"],
            "base_tempo": 0.96,
            "base_pitch": 1.01,
            "base_rate": "+2%",
            "pause_s": 0.15,
        },
    },
    "career": {
        "name": "职场成长",
        "description": "职场冲突、沟通、加班、绩效等现实场景。",
        "channel_style": "现代职场趣闻与吐槽，强调真实场景、边界表达和复盘价值。",
        "observation_focus": "会议、消息、交接、甩锅、解释、补救这些动作是怎么一步步把局面推偏的。",
        "expression_rules_cn": [
            "从一个普通但关键的工作瞬间切入，不要先喊职场真相。",
            "重点写回复节奏、会场气氛、责任流动和误判形成，不要写成功学。",
            "让冲突从具体动作和信息错位里出来，不靠夸张形容词。",
            "结尾更像复盘，讲清楚转折点，而不是教训观众。",
        ],
        "avoid_phrases": ["最离谱的一幕是", "90%的人第一步就做错了", "一招教你", "领导都这样", "先给结果"],
        "ending_tone": "像复盘完一个局面后终于看清关键节点，而不是宣布标准答案。",
        "content_rules": (
            "- Focus on one workplace scenario only: leader communication, blame shift, overtime, performance review, transfer/job change, or useless meetings.\n"
            "- Keep it grounded in visible office actions: meeting room, typing, chat messages, commuting, presentations, overtime desk.\n"
            "- Use crisp spoken language, like someone recounting a real workplace incident."
        ),
        "query_bias": ["office overtime desk", "meeting room tension", "commute city office", "work chat laptop"],
        "hook_pool": ["事情真正变味，是从一个很普通的瞬间开始的", "后来复盘才发现，转折点出现得比想象中更早", "那次场面看着不大，后面的麻烦却全从这儿出来了"],
        "image_style": "professional, corporate, clean composition, modern",
        "image_setting": "modern Chinese office building, meeting room, coworking space, subway commute",
        "image_mood": "focused, determined, professional, tense",
        "tts_profile": {
            "edge_voices": ["zh-CN-YunyangNeural", "zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural", "zh-CN-XiaoyiNeural"],
            "base_tempo": 1.01,
            "base_pitch": 1.0,
            "base_rate": "+5%",
            "pause_s": 0.07,
        },
    },
    "family_cn": {
        "name": "中式家庭",
        "description": "家庭关系、代际沟通、情感压力与边界。",
        "channel_style": "中式家庭关系复盘，聚焦代际冲突与沟通逻辑，避免羞辱和对立煽动。",
        "observation_focus": "饭桌、电话、亲戚聚会、替你做决定、拿你和别人比较这些熟悉场景里的关系压力。",
        "expression_rules_cn": [
            "先写大家熟悉的家庭说话方式和当时的场景，不要先喊压迫。",
            "重点拆开那句话为什么会让人难受，而不是只做控诉。",
            "保留复杂性，不把长辈或晚辈写成纯粹的对立面。",
            "结尾更像理解沟通逻辑，留一点余地，不要只剩情绪发泄。",
        ],
        "avoid_phrases": ["最窒息的一句是", "原生家庭毁一生", "父母都这样", "这就是控制", "看完就懂了"],
        "ending_tone": "像把熟悉关系里的压力来源看清楚一点，而不是把问题说成绝对对立。",
        "content_rules": (
            "- Focus on one Chinese-family logic pattern only: control, comparison, face culture,催婚催育, or emotional blackmail.\n"
            "- Show specific household moments: dining table, living room talk, phone call, relatives gathering, school gate.\n"
            "- Avoid pure accusation; keep it as story replay + logic unpacking."
        ),
        "query_bias": ["chinese family dinner", "parents talking living room", "young woman home stress", "family phone call"],
        "hook_pool": ["很多家庭的问题，不是吵出来的，是日常说话一点点压出来的", "有些话当时听着像关心，后来才知道它为什么这么重", "家里真正让人难受的，往往不是大道理，而是那种很熟悉的语气"],
        "image_style": "warm, family-oriented, soft natural lighting, traditional Chinese elements",
        "image_setting": "Chinese family home, dining table, living room, kitchen, balcony",
        "image_mood": "nostalgic, warm, bittersweet, intimate",
        "tts_profile": {
            "edge_voices": ["zh-CN-XiaoyiNeural", "zh-CN-YunxiNeural", "zh-CN-XiaoxiaoNeural", "zh-CN-YunyangNeural"],
            "base_tempo": 1.0,
            "base_pitch": 1.0,
            "base_rate": "+4%",
            "pause_s": 0.085,
        },
    },
    "history": {
        "name": "历史悬疑",
        "description": "历史人物、线索、反转和悬念表达。",
        "channel_style": "历史奇闻解说，节奏快，证据感强，允许反转但避免阴谋论绝对化。",
        "observation_focus": "史料、器物、地图、地名、判断落差和时间顺序里真正能支撑结论的线索。",
        "expression_rules_cn": [
            "从材料、对象、地点或判断差异切入，不要从惊天真相切入。",
            "让线索一点点推进，悬念来自证据落差，不来自神秘腔。",
            "保持证据感，少做夸张口播式煽动。",
            "结尾像重新理解一段材料，而不是揭露一个阴谋。",
        ],
        "avoid_phrases": ["最反常的细节是", "你以为", "惊天秘密", "真相只有一个", "很多人都没听过"],
        "ending_tone": "像顺完线索后对这段历史有了更稳的理解，而不是抛一个更大的噱头。",
        "content_rules": (
            "- Focus on one concrete historical hook: misunderstood person, lost artifact, power game, or institutional cold fact.\n"
            "- Every scene must include a tangible historical object/place/action, not abstract commentary.\n"
            "- Prefer evidence-like wording:史料、线索、文书、器物、城门、地图、战报。"
        ),
        "query_bias": ["ancient chinese street", "old map scroll", "palace corridor", "historical document"],
        "hook_pool": ["这件事真正奇怪的地方，不在大家最先注意到的那一层", "后来再看资料，最值得盯住的反而是那个不起眼的细节", "表面上像是这样，但线索真正拐弯的地方其实更早"],
        "image_style": "historical, dramatic lighting, cinematic, documentary style",
        "image_setting": "ancient Chinese architecture, historical site, old study room, museum artifact",
        "image_mood": "mysterious, suspenseful, dramatic, atmospheric",
        "tts_profile": {
            "edge_voices": ["zh-CN-YunxiNeural", "zh-CN-YunyangNeural", "zh-CN-XiaoxiaoNeural", "zh-CN-XiaoyiNeural"],
            "base_tempo": 1.03,
            "base_pitch": 0.99,
            "base_rate": "+6%",
            "pause_s": 0.075,
        },
    },
}


def channel_profile(pack_key: str) -> dict:
    key = str(pack_key or "career").strip().lower()
    return CHANNEL_PROFILES.get(key, CHANNEL_PROFILES["career"])
