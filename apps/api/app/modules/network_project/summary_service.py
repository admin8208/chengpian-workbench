from __future__ import annotations


class NetworkProjectSummaryStrategy:
    def blocker_missing_asset_label(self) -> str:
        return "缺素材"

    def missing_asset_message(self, count: int) -> str:
        return network_missing_asset_message(count)

    def missing_asset_suggestion(self) -> str:
        return network_missing_asset_suggestion()

    def missing_asset_fix_action(self) -> str:
        return "autofill_media"

    def mode_strength_labels(self) -> tuple[str, str]:
        return ("网络素材模式", "镜头素材已覆盖完整")

    def media_settings_fix_action(self, last_message: str) -> str | None:
        if any(x in last_message for x in ("Pexels", "Pixabay", "素材来源", "API Key", "素材")):
            return "go_settings_media"
        return None

    def duplicate_asset_feedback(self) -> tuple[str, str, str]:
        return (
            "部分镜头复用了相同素材，拼接感可能偏强",
            "建议补充更多差异化素材，减少重复镜头",
            "render_batch_story",
        )

    def continuity_feedback(self, *, anchor_coverage: float, jump_rate: float) -> tuple[str, str] | None:
        if anchor_coverage < 0.6:
            return (
                f"视觉主线不稳定（锚点覆盖率 {int(anchor_coverage * 100)}%）",
                "建议围绕同一人物/场景元素重配关键镜头，提升画面连续度",
            )
        if jump_rate > 0.2:
            return (
                f"相邻镜头跳变偏多（跳变率 {int(jump_rate * 100)}%）",
                "镜头切换偏跳，建议先处理问题镜头再重渲染",
            )
        return None

    def reasonability_feedback(self) -> tuple[str, str]:
        return (
            "内容语义与可视化匹配度偏低，建议先优化旁白与检索词后再渲染",
            "focus_scene_issues",
        )

    def default_summary_suggestion(self) -> str:
        return "当前项目状态不错，可直接继续出候选版本或重新渲染视频"


def network_missing_asset_message(count: int) -> str:
    return f"还有 {int(count)} 个镜头未绑定素材"


def network_missing_asset_suggestion() -> str:
        return "当前项目使用网络素材模式，建议先补齐缺失素材，再继续配音和渲染"


network_summary_strategy = NetworkProjectSummaryStrategy()
