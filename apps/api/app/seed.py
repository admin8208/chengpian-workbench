
import json

from sqlmodel import select

from app.db import session_scope
from app.image_service import normalize_image_providers
from app.llm_service import normalize_llm_providers
from app.models import ChannelPack, ImageProvider, LlmProvider


DEFAULT_PACKS: list[ChannelPack] = [
    ChannelPack(
        key="history",
        name="历史奇闻",
        description="悬念强、反转多，适合系列追更与涨粉。",
        config_json=json.dumps(
            {
                "scene_count": 10,
                "scene_duration_sec": 5,
                "style": "cinematic documentary b-roll, high detail, natural lighting",
                "negative": "watermark, text, logo, subtitles burned in",
                "hook_style": "suspense",
                "voice": "zh-CN-YunxiNeural",
                "voice_rate": "+0%",
                "voice_volume": 1.0,
                "subtitle_style": "boxed",
            },
            ensure_ascii=True,
        ),
    ),
    ChannelPack(
        key="emotion",
        name="情感关系",
        description="聚焦真实关系现场、潜台词和失望积累，强调边界感、心理反差与扎心但克制的结论。",
        config_json=json.dumps(
            {
                "scene_count": 7,
                "scene_duration_sec": 5.0,
                "target_min_sec": 30,
                "target_max_sec": 40,
                "target_sec": 35,
                "style": "intimate relationship moments, silent dinner, unread messages, hallway pause, late-night walk, home interior emotional distance, close-up expressions, realistic daily life b-roll",
                "negative": "watermark, text, logo, subtitles burned in",
                "hook_style": "emotion_hook",
                "voice": "zh-CN-XiaoyiNeural",
                "voice_rate": "+0%",
                "voice_volume": 1.0,
                "subtitle_style": "emotion",
                "emotion_keywords": {
                    "失望": ["disappointed face", "sad expression", "lonely moment", "empty room", "looking away"],
                    "委屈": ["tears", "crying", "hurt expression", "alone at night", "sad eyes"],
                    "边界": ["distance", "separate spaces", "back turned", "silence", "alone"],
                    "理解": ["warm light", "gentle touch", "understanding eyes", "comfort", "embrace"],
                    "沉默": ["silence", "quiet moment", "no words", "tension", "awkward"],
                    "争吵": ["argument", "conflict", "angry face", "shouting", "tension"],
                    "分手": ["breakup", "leaving", "goodbye", "sad departure", "alone"],
                    "孤独": ["lonely", "alone", "solitude", "single person", "empty space"],
                    "温暖": ["warm", "cozy", "comfortable", "together", "happy couple"],
                    "误会": ["misunderstanding", "confusion", "hurt feelings", "regret", "apology"],
                },
            },
            ensure_ascii=True,
        ),
    ),
    ChannelPack(
        key="career",
        name="现代职场",
        description="职场趣闻与吐槽，强调真实场景、沟通边界和复盘价值。",
        config_json=json.dumps(
            {
                "scene_count": 8,
                "scene_duration_sec": 5.5,
                "style": "clean modern office b-roll, minimal, sharp",
                "negative": "watermark, text, logo, subtitles burned in",
                "hook_style": "pain_point",
                "voice": "zh-CN-YunyangNeural",
                "voice_rate": "+0%",
                "voice_volume": 1.0,
                "subtitle_style": "boxed",
            },
            ensure_ascii=True,
        ),
    ),
    ChannelPack(
        key="family_cn",
        name="中式家庭",
        description="聚焦中式家庭中的代际冲突、控制式关爱与沟通逻辑。",
        config_json=json.dumps(
            {
                "scene_count": 8,
                "scene_duration_sec": 5.5,
                "style": "chinese family daily life, home interior b-roll, realistic candid moments",
                "negative": "watermark, text, logo, subtitles burned in",
                "hook_style": "family_conflict",
                "voice": "zh-CN-XiaoyiNeural",
                "voice_rate": "+0%",
                "voice_volume": 1.0,
                "subtitle_style": "boxed",
            },
            ensure_ascii=True,
        ),
    ),
]


def seed_channel_packs() -> None:
    with session_scope() as session:
        for pack in DEFAULT_PACKS:
            existing = session.exec(select(ChannelPack).where(ChannelPack.key == pack.key)).first()
            if existing:
                continue
            session.add(pack)


def seed_llm_providers() -> None:
    defaults: list[LlmProvider] = [
        LlmProvider(
            name="DeepSeek (OpenAI兼容)",
            type="openai_compat",
            base_url="https://api.deepseek.com",
            default_model="deepseek-chat",
            enabled=True,
            is_default=False,
        ),
        LlmProvider(
            name="Kimi (Moonshot, OpenAI兼容)",
            type="openai_compat",
            base_url="https://api.moonshot.cn",
            default_model="moonshot-v1-8k",
            enabled=True,
            is_default=False,
        ),
        LlmProvider(
            name="OpenAI",
            type="openai_compat",
            base_url="https://api.openai.com",
            default_model="gpt-4o-mini",
            enabled=True,
            is_default=False,
        ),
        LlmProvider(
            name="Ollama (本地)",
            type="ollama",
            base_url="http://127.0.0.1:11434",
            default_model="qwen2.5:7b",
            enabled=True,
            is_default=False,
        ),
    ]

    with session_scope() as session:
        if session.exec(select(LlmProvider)).first():
            normalize_llm_providers(session)
            return
        session.add(defaults[0])
        normalize_llm_providers(session)


def seed_image_providers() -> None:
    defaults: list[ImageProvider] = [
        ImageProvider(
            name="OpenAI 图像",
            type="openai_compat",
            base_url="https://api.openai.com",
            default_model="gpt-image-2",
            enabled=True,
            is_default=True,
        )
    ]

    with session_scope() as session:
        normalize_image_providers(session)
        if not session.exec(select(ImageProvider)).first():
            session.add(defaults[0])
        normalize_image_providers(session)
