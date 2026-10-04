# -*- coding: utf-8 -*-
"""双引擎点评：大模型优先，失败/未配置时回退离线规则。

AI 点评会把题目的评分细则、关键词与候选人画像一起交给模型，
并要求结构化输出（含证据与分档），解析失败或调用异常时无缝回退。
"""
import json
import re

from ai_client import AIClient
from grader import DIMENSIONS, band_name, grade_offline

_ai = AIClient()


def ai_available():
    return _ai.available()


def _extract_json(text):
    """防御性解析：处理 ```json 代码块与前后杂讯。"""
    if not text:
        return None
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S | re.I)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except Exception:
        return None


def _validate_grade(data):
    if not isinstance(data, dict):
        return None
    try:
        score = float(data.get("score"))
    except (TypeError, ValueError):
        return None

    dims = data.get("dimensions")
    if not isinstance(dims, dict):
        return None
    clean_dims = {k: float(v) for k, v in dims.items() if k in DIMENSIONS and isinstance(v, (int, float))}
    if len(clean_dims) < len(DIMENSIONS):
        return None

    def str_list(value):
        if isinstance(value, list):
            return [str(x).strip() for x in value if str(x).strip()][:4]
        return []

    evidence = data.get("evidence")
    if isinstance(evidence, str):
        evidence = [evidence]
    evidence = [str(x).strip() for x in (evidence or []) if str(x).strip()][:2]

    score = max(0, min(100, round(score)))
    return {
        "score": score,
        "band": str(data.get("band") or band_name(score)),
        "dimensions": {k: max(0, min(100, round(v))) for k, v in clean_dims.items()},
        "strengths": str_list(data.get("strengths")) or ["完成作答，内容有一定信息量。"],
        "improvements": str_list(data.get("improvements")) or ["可再补充一个具体例子和量化结果。"],
        "evidence": evidence,
        "sample": str(data.get("sample") or ""),
        "score_breakdown": data.get("score_breakdown") if isinstance(data.get("score_breakdown"), dict) else {},
        "graded_by": "ai",
    }


def _profile_text(profile):
    if not profile:
        return "（候选人未填写画像）"
    parts = []
    if profile.target_job:
        parts.append("目标岗位：" + profile.target_job)
    if profile.level:
        parts.append("求职阶段：" + profile.level)
    if profile.skills:
        parts.append("技能标签：" + profile.skills)
    if profile.experience:
        parts.append("经历简介：" + profile.experience)
    return "\n".join(parts) if parts else "（候选人未填写画像）"


def _rubric_text(q):
    rubric = q.get("rubric") or {}
    if not rubric:
        return "（本题未配置分档细则）"
    return "\n".join(f"{k}+ 分：{v}" for k, v in rubric.items())


def grade_answer(q, content, profile=None):
    if not _ai.available():
        return grade_offline(q, content, profile)

    job = (profile.target_job if profile else "") or "未知岗位"
    prompt = (
        "你是一名资深面试官，正在对候选人的模拟面试作答进行逐题点评。请严格依据题目评分细则与候选人画像打分，"
        "不要泛泛夸奖，点评要具体、可执行，并尽量引用候选人原话作为证据。\n\n"
        f"【候选人画像】\n{_profile_text(profile)}\n\n"
        f"【题目】{q['title']}\n"
        f"【题型】{q.get('type', 'general')}，难度 {q.get('difficulty', 1)}/3\n"
        f"【评分要点】{q.get('points', '')}\n"
        f"【关键词/考点】{'、'.join(q.get('keywords', []))}\n"
        f"【分档细则】\n{_rubric_text(q)}\n\n"
        f"【候选人回答】\n{content}\n\n"
        "只输出一个 JSON 对象，不要任何解释，字段如下：\n"
        "{\n"
        '  "score": 0到100的整数,\n'
        '  "band": "卓越/优秀/良好/合格/待提升",\n'
        '  "dimensions": {"专业能力":0到100,"逻辑表达":0到100,"沟通协作":0到100,"应变能力":0到100,"岗位匹配":0到100},\n'
        '  "strengths": ["优点1","优点2","优点3"],\n'
        '  "improvements": ["改进1","改进2","改进3"],\n'
        '  "evidence": ["引用候选人原话片段1","片段2"],\n'
        '  "sample": "针对本题的一段更优回答示例",\n'
        '  "score_breakdown": {"要点覆盖":0到100,"结构清晰":0到100,"量化细节":0到100,"表达条理":0到100}\n'
        "}"
    )

    system = (
        "你是严谨、专业的模拟面试官。你只输出合法 JSON，不做解释；"
        "评分要与分档细则一致，优点和改进都要有据可依。"
    )
    try:
        raw = _ai.chat(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=0.35,
            max_tokens=1200,
            json_mode=True,
            timeout=90,
        )
        data = _validate_grade(_extract_json(raw))
        if data:
            return data
    except Exception:
        pass  # 任何异常都回退离线规则
    return grade_offline(q, content, profile)