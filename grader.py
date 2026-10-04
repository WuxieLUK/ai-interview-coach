# -*- coding: utf-8 -*-
"""离线规则评分器：无 API Key 时的兜底引擎。

评分不只看关键词是否命中，而是综合：
- 专业覆盖度（关键词 + 具体专业名词/工具）
- 结构完整度（STAR / 分点 / 因果链条）
- 量化与细节（数字、指标、单位）
- 表达清晰度（句子数量、口头禅、模糊词）
并把结果落到五个能力维度与一段可解释的依据上。
"""
import math
import re

DIMENSIONS = ["专业能力", "逻辑表达", "沟通协作", "应变能力", "岗位匹配"]

BANDS = [(90, "卓越"), (80, "优秀"), (70, "良好"), (60, "合格"), (0, "待提升")]

STAR_MARKERS = {
    "S": ["背景", "情况", "当时", "一开始", "在实习", "项目是", "场景"],
    "T": ["任务", "目标", "要做", "负责", "需求是", "挑战"],
    "A": ["行动", "做了", "采取", "我负责", "于是", "通过", "设计", "实现", "推动", "优化"],
    "R": ["结果", "成果", "最终", "提升", "下降", "获得", "完成", "达到", "上线"],
}

SIGNPOSTS = ["首先", "其次", "然后", "最后", "第一", "第二", "第三", "综上", "具体来说", "一方面", "另一方面"]
ACTION_VERBS = ["负责", "主导", "推动", "设计", "实现", "开发", "优化", "协调", "沟通", "落地", "复盘", "调研", "分析", "拆解", "制定", "跟进", "验证", "上线", "迭代"]
COLLAB_MARKERS = ["团队", "协作", "沟通", "共识", "分工", "反馈", "冲突", "倾听", "同事", "成员", "配合", "对齐", "协调", "合作"]
SITUATION_MARKERS = ["止损", "回滚", "定位", "监控", "日志", "优先级", "预案", "复盘", "升级", "根因", "影响面", "临时方案", "长期方案", "分级", "回应", "口径"]
SPECIFIC_TERMS = ["python", "java", "go", "c++", "mysql", "redis", "kafka", "docker", "kubernetes", "sql", "flask", "spring", "react", "vue", "http", "api", "rpc", "mq", "索引", "缓存", "消息队列", "微服务", "限流", "降级", "分布式", "数据库", "前端", "后端", "算法", "模型", "ab测试", "漏斗", "留存", "roi", "gmv", "dau", "mau", "埋点", "北极星", "产品", "需求", "用户", "运营", "数据分析", "指标"]
FILLERS = ["然后然后", "就是就是", "呃", "嗯", "那个那个", "怎么说", "非常非常"]
VAGUE_WORDS = ["很多", "一些", "大概", "可能", "应该", "还行", "不错", "挺多", "比较"]


def _clamp(v, lo=0, hi=100):
    return max(lo, min(hi, round(v)))


def _sentences(content):
    parts = re.split(r"[。！？!?；;\n]+", content)
    return [p.strip() for p in parts if p.strip()]


def _keyword_signal(q, content):
    """加权关键词覆盖：命中越多、权重越高，专业分越高。"""
    text = content.lower()
    hits, missed = [], []
    total_w, hit_w = 0.0, 0.0
    for item in q.get("keywords", []):
        if isinstance(item, str):
            term, weight = item, 1
        else:
            term, weight = item.get("term", ""), float(item.get("weight", 1))
        if not term:
            continue
        total_w += weight
        if term.lower() in text:
            hits.append(term)
            hit_w += weight
        else:
            missed.append(term)
    coverage = (hit_w / total_w) if total_w else 0.0
    score = _clamp(40 + coverage * 60)
    return score, hits, missed, coverage


def _length_signal(content):
    n = len(content)
    if n < 25:
        return 25, "too_short"
    if n < 60:
        return 60, "short"
    if n < 140:
        return 82, "ok"
    if n < 320:
        return 92, "good"
    return 95, "long"


def _star_signal(content):
    hit = 0
    for markers in STAR_MARKERS.values():
        if any(m in content for m in markers):
            hit += 1
    return _clamp(hit / 4 * 100), hit


def _signpost_signal(content):
    count = sum(1 for s in SIGNPOSTS if s in content)
    return _clamp(35 + count * 22), count


def _action_signal(content):
    count = sum(1 for v in ACTION_VERBS if v in content)
    return _clamp(30 + count * 15), count


def _collab_signal(content):
    count = sum(1 for m in COLLAB_MARKERS if m in content)
    return _clamp(25 + count * 18), count


def _situation_signal(content):
    count = sum(1 for m in SITUATION_MARKERS if m in content)
    return _clamp(25 + count * 18), count


def _quant_signal(content):
    numbers = re.findall(r"\d+(?:\.\d+)?", content)
    units = re.findall(r"\d+(?:\.\d+)?\s*(?:%|％|倍|秒|毫秒|分钟|小时|天|月|年|万|亿|个|次|项|人|条|元|qps|tps|pv|uv|p99|dau|mau|gmv|roi)", content.lower())
    score = _clamp(15 + len(numbers) * 12 + len(units) * 15)
    return score, len(numbers), len(units)


def _specificity_signal(content):
    text = content.lower()
    count = sum(1 for t in SPECIFIC_TERMS if t in text)
    return _clamp(25 + count * 11), count


def _fluency_signal(content):
    filler = sum(content.count(f) for f in FILLERS)
    vague = sum(content.count(v) for v in VAGUE_WORDS)
    penalty = min(32, filler * 7 + vague * 2)
    return max(0, 100 - penalty), filler, vague


def _clarity_signal(content):
    sentences = _sentences(content)
    n = len(sentences)
    if n >= 4:
        base = 92
    elif n == 3:
        base = 80
    elif n == 2:
        base = 62
    else:
        base = 42
    avg_len = len(content) / max(1, n)
    if avg_len > 110:
        base -= 10
    return _clamp(base), n

def band_name(score):
    for threshold, name in BANDS:
        if score >= threshold:
            return name
    return "待提升"


def _evidence(content, hits, numbers, terms, limit=2):
    """从原回答里截取能支撑分数的短片段。"""
    sentences = _sentences(content)
    chosen = []
    for s in sentences:
        if len(chosen) >= limit:
            break
        if any(h in s for h in hits) or any(str(n) in s for n in re.findall(r"\d+", s)) or any(t in s.lower() for t in terms):
            chosen.append(s)
    return [c[:80] for c in chosen]


def grade_offline(q, content, profile=None):
    content = (content or "").strip()
    qtype = q.get("type", "general")
    is_behavioral = qtype == "behavioral"
    is_situational = qtype == "situational"
    is_technical = qtype == "technical"

    kw_score, hits, missed, coverage = _keyword_signal(q, content)
    len_score, len_flag = _length_signal(content)
    star_score, star_hit = _star_signal(content)
    sign_score, sign_count = _signpost_signal(content)
    action_score, action_count = _action_signal(content)
    collab_score, collab_count = _collab_signal(content)
    situation_score, situation_count = _situation_signal(content)
    quant_score, num_count, unit_count = _quant_signal(content)
    spec_score, spec_count = _specificity_signal(content)
    flu_score, filler_count, vague_count = _fluency_signal(content)
    clarity_score, sentence_count = _clarity_signal(content)

    if is_behavioral:
        structure = round(star_score * 0.6 + sign_score * 0.25 + action_score * 0.15)
    elif is_situational:
        structure = round(situation_score * 0.55 + sign_score * 0.25 + action_score * 0.20)
    else:
        structure = round(sign_score * 0.5 + clarity_score * 0.3 + action_score * 0.2)

    if is_technical:
        professional = 0.55 * kw_score + 0.30 * spec_score + 0.15 * max(quant_score, 55)
        logic = 0.45 * structure + 0.30 * clarity_score + 0.25 * flu_score
        communication = 0.35 * clarity_score + 0.35 * flu_score + 0.30 * spec_score
        adaptability = 0.45 * structure + 0.30 * flu_score + 0.25 * max(quant_score, 50)
    else:
        professional = 0.55 * kw_score + 0.25 * clarity_score + 0.20 * max(quant_score, spec_score * 0.6)
        logic = 0.45 * structure + 0.30 * clarity_score + 0.25 * flu_score
        communication = 0.45 * max(collab_score, action_score) + 0.30 * clarity_score + 0.25 * flu_score
        adaptability = 0.45 * structure + 0.30 * flu_score + 0.25 * quant_score
        if is_situational:
            adaptability = 0.55 * situation_score + 0.20 * quant_score + 0.25 * flu_score

    raw_dims = {
        "专业能力": professional,
        "逻辑表达": logic,
        "沟通协作": communication,
        "应变能力": adaptability,
        "岗位匹配": 0.55 * kw_score + 0.25 * spec_score + 0.20 * quant_score,
    }

    def _stretch(v):
        if v <= 55:
            return _clamp(v)
        return _clamp(55 + (v - 55) * 1.4)

    dimensions = {k: _stretch(v) for k, v in raw_dims.items()}
    score = _clamp(sum(dimensions.values()) / len(dimensions))

    # ------- 优点（证据化） -------
    strengths = []
    if coverage >= 0.55 and hits:
        strengths.append("要点覆盖到位：命中“" + "、".join(hits[:4]) + "”等关键点。")
    if quant_score >= 65:
        strengths.append("有数据支撑：提到 " + str(num_count) + " 个数字" + ("，含指标单位" if unit_count else "") + "，结论更有说服力。")
    if is_behavioral and star_hit >= 3:
        strengths.append("STAR 结构清晰：情境-任务-行动-结果基本完整。")
    if not is_behavioral and structure >= 75:
        strengths.append("回答有框架、分点清楚，能按逻辑推进。")
    if spec_count >= 2:
        strengths.append("使用具体专业名词/工具，表达显得专业。")
    if clarity_score >= 85 and sentence_count >= 3:
        strengths.append("表达有层次，句子长短得当、可读性好。")
    if collab_score >= 60 and (is_behavioral or is_situational):
        strengths.append("体现了沟通协作意识，角色与配合讲得比较清楚。")
    if not strengths:
        strengths.append("完成了作答，保留了继续展开的基础。")

    # ------- 改进（按优先级） -------
    improvements = []
    if coverage < 0.55 and missed:
        improvements.append("关键点有缺失，建议补充：" + "、".join(missed[:4]) + "。")
    if len_flag in ("too_short", "short"):
        improvements.append("回答偏短，用“背景-行动-结果”展开，并补一个具体例子和数字。")
    if is_behavioral and star_hit < 3:
        improvements.append("行为题建议按 STAR 结构组织：情境-任务-行动-结果。")
    if quant_score < 55:
        improvements.append("缺少量化结果：用数字说明效果，如提升了多少、耗时缩短多少。")
    if flu_score and (filler_count or vague_count >= 3):
        improvements.append("减少“然后/就是/大概”这类口头禅或模糊词，表达更干脆。")
    if sentence_count < 3:
        improvements.append("建议分点作答（第一/第二/第三），让逻辑更清楚。")
    if is_situational and situation_count < 2:
        improvements.append("情景题可按“止损→定位→预案→复盘”四步作答，体现优先级判断。")
    if not improvements:
        improvements.append("可再给一个可量化结果或复盘一句，让回答更有闭环。")

    evidence = _evidence(content, hits, re.findall(r"\d+", content), SPECIFIC_TERMS)

    return {
        "score": score,
        "band": band_name(score),
        "dimensions": dimensions,
        "strengths": strengths[:4],
        "improvements": improvements[:4],
        "evidence": evidence,
        "sample": q.get("sample") or q.get("points", ""),
        "score_breakdown": {
            "关键词覆盖": kw_score,
            "结构完整度": structure,
            "内容充实度": len_score,
            "量化与细节": quant_score,
            "表达清晰度": clarity_score,
        },
        "graded_by": "rule",
    }