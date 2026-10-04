# -*- coding: utf-8 -*-
"""报告与洞察分析：把零散的答题数据聚合为可解释的能力画像。

输出“总分 / 分档 / 强弱项 / 维度点评 / 优先行动”，供报告页与洞察页直接使用。
"""
import math

from grader import DIMENSIONS, band_name
from question_bank import get_question

DIM_NOTES = {
    "专业能力": "知识点覆盖与深度：能否讲清原理、给出量化结果。",
    "逻辑表达": "结构与条理：是否分点、因果是否清楚、时间感是否好。",
    "沟通协作": "角色与沟通：是否讲清自己如何协作、对齐与解决分歧。",
    "应变能力": "压力与情景：是否按止损-定位-预案-复盘推进。",
    "岗位匹配": "与目标岗位的贴合度：是否主动关联经历与岗位要求。",
}

DIM_ACTIONS = {
    "专业能力": "围绕目标岗位梳理 3 个高频考点，每个都准备成“概念 + 例子 + 数据”的回答模板。",
    "逻辑表达": "下次作答强制用“第一/第二/第三”或 STAR 结构，每题控制在 3-4 个分点、2 分钟内。",
    "沟通协作": "行为题里明确讲出你的角色、你如何沟通对齐，并补一个冲突化解的细节。",
    "应变能力": "情景题按“止损 → 定位 → 预案 → 复盘”四步作答，并说明优先级判断。",
    "岗位匹配": "把每段经历都收束到“这对该岗位意味着什么”，主动呼应 JD 的关键要求。",
}


def _sorted_dims(dims):
    return sorted(DIMENSIONS, key=lambda d: dims.get(d, 0), reverse=True)


def _consistency(scores):
    if not scores:
        return "暂无数据"
    if len(scores) < 2:
        return "单题无法评估"
    mean = sum(scores) / len(scores)
    variance = sum((s - mean) ** 2 for s in scores) / len(scores)
    std = math.sqrt(variance)
    if std <= 8:
        return "发挥稳定"
    if std <= 16:
        return "略有波动"
    return "波动较大"


def _avg_difficulty(answers):
    total, count = 0, 0
    for a in answers:
        q = get_question(a.question_id)
        if q:
            total += int(q.get("difficulty", 1))
            count += 1
    return round(total / count, 1) if count else 0


def _dimension_analysis(dims):
    analysis = []
    for dim in DIMENSIONS:
        value = int(dims.get(dim, 0))
        if value >= 85:
            label = "优势"
        elif value >= 70:
            label = "良好"
        elif value >= 60:
            label = "达标"
        else:
            label = "待提升"
        analysis.append({"dimension": dim, "score": value, "label": label, "note": DIM_NOTES.get(dim, "")})
    return analysis


def _priority_actions(dims, answers=None, limit=3):
    weakest = list(reversed(_sorted_dims(dims)))[:2]
    actions = []
    for dim in weakest:
        action = DIM_ACTIONS.get(dim)
        if action and action not in actions:
            actions.append(action)
    if answers:
        seen = set()
        for a in answers:
            fb = a.feedback_dict()
            for tip in fb.get("improvements", []):
                if tip not in seen:
                    seen.add(tip)
                    actions.append(tip)
            if len(actions) >= limit + 1:
                break
    return actions[:limit]


def session_report(sess):
    answers = list(sess.answers.order_by("id").all())
    dims = sess.dimension_dict() or {}
    scores = [a.score for a in answers]
    total = round(sess.total_score or (sum(scores) / len(scores) if scores else 0), 1)

    rank = _sorted_dims(dims)
    strongest = rank[:2]
    weakest = list(reversed(rank[-2:]))

    consistency = _consistency(scores)
    avg_difficulty = _avg_difficulty(answers)

    summary = (
        f"本场共 {len(answers)} 题，平均 {total} 分，整体水平“{band_name(total)}”。"
        f"“{'、'.join(strongest)}”是你的强项，“{'、'.join(weakest)}”最值得加强。"
        f"各题得分{consistency}，平均难度 {avg_difficulty}/3。"
    )

    return {
        "total_score": total,
        "band": band_name(total),
        "dimensions": dims,
        "strongest": strongest,
        "weakest": weakest,
        "dimension_analysis": _dimension_analysis(dims),
        "priority_actions": _priority_actions(dims, answers),
        "consistency": consistency,
        "avg_difficulty": avg_difficulty,
        "summary": summary,
        "score_trend": scores,
    }


def insights_analysis(user):
    finished = list(user.sessions.filter_by(status="finished").order_by("created_at").all())
    if not finished:
        return {
            "sessions": 0, "avg_total": 0, "dims": {},
            "strongest": [], "weakest": [], "trend_delta": 0,
            "recent_avg": 0, "first_score": 0, "last_score": 0,
            "series": [], "recommendations": [],
        }

    total_scores = [s.total_score for s in finished]
    avg_total = round(sum(total_scores) / len(total_scores), 1)

    dims = {d: [] for d in DIMENSIONS}
    for s in finished:
        for d, v in s.dimension_dict().items():
            if d in dims:
                dims[d].append(v)
    avg_dims = {d: round(sum(v) / len(v)) if v else 0 for d, v in dims.items()}

    rank = _sorted_dims(avg_dims)
    strongest = rank[:2]
    weakest = list(reversed(rank[-2:]))

    first_score = total_scores[0]
    last_score = total_scores[-1]
    trend_delta = round(last_score - first_score, 1)
    recent = total_scores[-3:]
    recent_avg = round(sum(recent) / len(recent), 1)

    series = [
        {
            "id": s.id,
            "created_at": s.created_at.isoformat(),
            "total_score": s.total_score,
            "dimensions": s.dimension_dict(),
        }
        for s in finished
    ]

    return {
        "sessions": len(finished),
        "avg_total": avg_total,
        "dims": avg_dims,
        "strongest": strongest,
        "weakest": weakest,
        "trend_delta": trend_delta,
        "recent_avg": recent_avg,
        "first_score": first_score,
        "last_score": last_score,
        "series": series,
        "recommendations": _priority_actions(avg_dims),
    }