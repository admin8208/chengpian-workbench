def json_only_rules() -> str:
    return "Return STRICT JSON only. No markdown. No code fences."


def spoken_chinese_rules() -> str:
    return (
        "Use natural spoken Chinese. Avoid broad moralizing, essay tone, and generic AI phrasing.\n"
        "Prefer short, concrete, internet-native sentences.\n"
        "Do not use template phrases like 很多人不知道 / 其实你会发现 / 值得注意的是 / 需要注意的是 / 说白了 / 第N个关键点.\n"
        "Do not open with host-style greetings or topic-introductions like 大家好 / 哈喽大家好 / 今天我们来聊聊 / 今天想和大家聊聊 / 这一期 / 本期视频.\n"
        "Do not use creator-platform filler like 点赞收藏 / 先关注 / 评论区 / 屏幕前的你 / 看到最后.\n"
        "You may sound colloquial, but do not sound like a presenter warming up the audience before the real content starts.\n"
        "Do not write like a summary article or PPT. Write like a real person talking to camera.\n"
        "Prefer spoken transitions, concrete details, interruptions, reactions, and colloquial landing lines."
    )


def filmable_rules() -> str:
    return (
        "Every scene must be filmable and searchable.\n"
        "Prefer visible subject + action + place rather than abstract commentary."
    )


def safety_rules() -> str:
    return "Keep content safe. Avoid real person/company defamation, insults, slurs, watermark, and text-overlay instructions."
