def workflow_rules(workflow: str) -> str:
    wf = str(workflow or "mix").strip().lower() or "mix"
    if wf == "mix":
        return (
            "For workflow=mix (stock footage remix):\n"
            "- media_query is a short Chinese visual note for editors only; keep it concrete and under 12 Chinese characters.\n"
            "- search_en is the only stock-search field and must be 2-6 English words with visible subject + action + place.\n"
            "- Avoid abstract concepts ('growth', 'truth', 'feelings'), avoid full sentences, avoid punctuation/emoji in search_en.\n"
            "- image_prompt can be short or empty; it is not the primary field."
        )
    return f"Workflow={wf}. Keep fields concrete and aligned with the requested workflow."
