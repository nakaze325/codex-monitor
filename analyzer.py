import re

HIGH_PHRASES = (
    "reset usage limits", "usage limits restored", "rate limits reset",
    "limits restored", "back to 100%", "reset completed",
)
MEDIUM_PHRASES = ("will reset", "reset incoming", "fixed an issue", "investigating limits")


def analyze(text: str) -> dict:
    normalized = re.sub(r"\s+", " ", text.lower().replace("’", "'"))
    if not re.search(r"\bcodex\b", normalized):
        return {"score": 0, "signal_type": "normal_update", "analysis": "正文未明确提及 Codex，无法确认额度信号的对象。"}
    scores = []
    reasons = []
    for sentence in re.findall(r"[^.!?。！？;\n]+[.!?。！？;]?", text.lower().replace("’", "'")):
        sentence = re.sub(r"\s+", " ", sentence).strip()
        if sentence.endswith(("?", "？")):
            continue
        if re.search(r"\b(?:not|never|no|hasn't|haven't|isn't|aren't|won't|didn't|don't|doesn't|can't|cannot)\b", sentence):
            continue
        if re.search(r"\b(?:how to|how do|how can|can we|can you|did you|did we|have you|have we|has codex)\b", sentence):
            continue
        high = [phrase for phrase in HIGH_PHRASES if re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", sentence)]
        medium = [phrase for phrase in MEDIUM_PHRASES if re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", sentence)]
        if medium == ["fixed an issue"] and not re.search(r"\b(?:limits?|quota|reset)\b", sentence):
            medium = []
        future = re.search(r"\b(?:will|soon|tomorrow|incoming|planning|plan|may|might|could|would|if|hope|hopefully)\b", sentence)
        if high:
            scores.append(65 if future else 85)
            reasons.append("命中 " + ", ".join(high) + ("，含未来或不确定表达" if future else ""))
        elif medium:
            scores.append(65)
            reasons.append("命中 " + ", ".join(medium))
    score = max(scores, default=0)
    signal_type = "confirmed_reset" if score >= 80 else "possible_reset" if score >= 60 else "normal_update"
    analysis = "；".join(reasons) if reasons else "未命中有效重置信号，或命中否定/询问表达。"
    return {"score": score, "signal_type": signal_type, "analysis": analysis + " 本结果来自关键词规则，分数不是统计概率。"}
