
import re


def _find_any(text: str, patterns: list[str]) -> str | None:
    for p in patterns:
        if re.search(p, text, flags=re.IGNORECASE):
            return p
    return None


def check_text(script: str, *, channel_key: str = "") -> list[dict]:
    """Return a list of warnings.

    Output item schema:
      {code, level, message, evidence?}
    """

    t = (script or "").strip()
    if not t:
        return [
            {
                "code": "empty_script",
                "level": "warn",
                "message": "脚本为空，无法做合规检查。",
            }
        ]

    warnings: list[dict] = []

    # Hard blocks / high risk claims
    hit = _find_any(t, [r"包治百病", r"保证(有效|赚钱|变瘦|成功)", r"稳赚", r"一夜暴富"]) 
    if hit:
        warnings.append(
            {
                "code": "guarantee_claim",
                "level": "block",
                "message": "检测到‘保证/稳赚/包治’等高风险承诺式表述，建议改写为更谨慎的表达。",
                "evidence": hit,
            }
        )

    # Medical/health advice risk
    hit = _find_any(t, [r"治疗", r"处方", r"药", r"癌", r"抑郁", r"焦虑症", r"诊断", r"医嘱", r"副作用"]) 
    if hit and channel_key != "family_cn":
        warnings.append(
            {
                "code": "medical_content",
                "level": "warn",
                "message": "包含医疗/诊断/用药相关内容，建议加免责声明并避免给出明确治疗建议。",
                "evidence": hit,
            }
        )

    # Finance/investment advice risk
    hit = _find_any(t, [r"理财", r"投资", r"股票", r"基金", r"币", r"收益率", r"翻倍", r"内幕"]) 
    if hit:
        warnings.append(
            {
                "code": "finance_content",
                "level": "warn",
                "message": "包含投资/收益相关内容，建议避免承诺收益与引导交易。",
                "evidence": hit,
            }
        )

    # Extremes / absolutes (often triggers moderation)
    hit = _find_any(t, [r"100%", r"百分之百", r"绝对", r"必然", r"一定能"]) 
    if hit:
        warnings.append(
            {
                "code": "absolute_language",
                "level": "info",
                "message": "检测到绝对化表述，建议用更可验证/更谨慎的说法。",
                "evidence": hit,
            }
        )

    # Contact / external diversion
    hit = _find_any(t, [r"微信", r"加(v|V)", r"公众号", r"私信", r"电报", r"QQ群", r"群号", r"二维码"]) 
    if hit:
        warnings.append(
            {
                "code": "contact_diversion",
                "level": "warn",
                "message": "检测到导流/联系方式相关词汇，可能触发平台限制。",
                "evidence": hit,
            }
        )

    # Phone number like patterns
    if re.search(r"\b1\d{10}\b", t):
        warnings.append(
            {
                "code": "phone_number",
                "level": "warn",
                "message": "检测到可能的手机号，建议移除或打码。",
            }
        )

    ok = not any(w.get("level") == "block" for w in warnings)
    if ok and not warnings:
        warnings.append(
            {
                "code": "ok",
                "level": "info",
                "message": "未发现明显高风险项（规则检查）。",
            }
        )
    return warnings
