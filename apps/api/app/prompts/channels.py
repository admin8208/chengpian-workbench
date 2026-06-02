from app.channel_profiles import channel_profile


def channel_style(pack_key: str) -> str:
    return str(channel_profile(pack_key).get("channel_style") or "")


def track_content_rules(pack_key: str) -> str:
    return str(channel_profile(pack_key).get("content_rules") or "")


def observation_focus(pack_key: str) -> str:
    return str(channel_profile(pack_key).get("observation_focus") or "")


def expression_rules(pack_key: str) -> list[str]:
    vals = channel_profile(pack_key).get("expression_rules_cn") or []
    return [str(x) for x in vals if str(x).strip()]


def avoid_phrases(pack_key: str) -> list[str]:
    vals = channel_profile(pack_key).get("avoid_phrases") or []
    return [str(x) for x in vals if str(x).strip()]


def ending_tone(pack_key: str) -> str:
    return str(channel_profile(pack_key).get("ending_tone") or "")


def track_query_bias(pack_key: str) -> list[str]:
    vals = channel_profile(pack_key).get("query_bias") or []
    return [str(x) for x in vals if str(x).strip()]
