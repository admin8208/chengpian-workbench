from __future__ import annotations


class AiProjectSummaryStrategy:
    def blocker_missing_asset_label(self) -> str:
        return "缺镜头图"

    def missing_asset_message(self, count: int) -> str:
        return ai_missing_asset_message(count)

    def missing_asset_suggestion(self) -> str:
        return ai_missing_asset_suggestion()

    def missing_asset_fix_action(self) -> str:
        return "generate_images"

    def mode_strength_labels(self) -> tuple[str, str]:
        return ("智能生图链路模式", "镜头图已覆盖完整")

    def media_settings_fix_action(self, last_message: str) -> str | None:
        if any(x in last_message for x in ("生图", "图片", "出图", "镜头图")) and any(x in last_message for x in ("API Key", "base_url", "model", "默认")):
            return "go_settings_image"
        return None

    def duplicate_asset_feedback(self) -> tuple[str, str, str]:
        return (
            "部分镜头复用了相同镜头图，画面变化可能不足",
            "建议重生成重复镜头或微调提示词，减少连续重复画面",
            "focus_scene_issues",
        )

    def continuity_feedback(self, *, anchor_coverage: float, jump_rate: float) -> tuple[str, str] | None:
        if anchor_coverage < 0.6:
            return (
                f"视觉主线不稳定（锚点覆盖率 {int(anchor_coverage * 100)}%）",
                "建议围绕同一人物/场景元素重生成关键镜头，提升画面连续度",
            )
        if jump_rate > 0.2:
            return (
                f"相邻镜头跳变偏多（跳变率 {int(jump_rate * 100)}%）",
                "镜头切换偏跳，建议优先处理问题镜头后再重渲染",
            )
        return None

    def reasonability_feedback(self) -> tuple[str, str]:
        return (
            "内容语义与镜头生成匹配度偏低，建议先优化旁白与提示词后再渲染",
            "focus_scene_issues",
        )

    def default_summary_suggestion(self) -> str:
        return "当前智能生图链路状态稳定，可继续生成候选版本或重新渲染视频"


def ai_missing_asset_message(count: int) -> str:
    return f"还有 {int(count)} 个镜头未生成镜头图"


def ai_missing_asset_suggestion() -> str:
    return "当前项目使用智能生图链路模式，建议先补齐镜头图，再继续配音和渲染"


ai_summary_strategy = AiProjectSummaryStrategy()
