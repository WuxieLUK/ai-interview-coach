# -*- coding: utf-8 -*-
"""演示数据播种器：一键生成面试官可展示的演示账号与多场真实评分记录。

说明：
- 使用离线规则评分器（不经网络）保证秒级生成、结果确定；
- 覆盖技术 / 产品 / 数据三个方向，且技术方向三场“弱→中→强”递进，
  用于在洞察页演示成长趋势；
- 保证数据库为空时也能立刻看到“满”的历史、报告与雷达图。
"""
import hashlib
import json
import secrets
from datetime import datetime, timedelta

from grader import DIMENSIONS, grade_offline
from models import Answer, InterviewSession, Profile, User, db
from question_bank import build_session_questions, get_question

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo123"

DEMO_PROFILE = {
    "name": "陈同学",
    "target_job": "后端开发工程师",
    "job_family": "tech",
    "level": "校招",
    "skills": "Python · Go · Flask · MySQL · Redis",
    "experience": "校园二手交易平台后端：负责订单/支付模块，引入缓存与索引优化，接口 P99 从 2s 降至 300ms。",
}


def _hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), 100_000).hex()
    return f"{salt}${digest}"


def _weak_answer(q):
    if q.get("type") == "technical":
        return "这个知识点我了解得不多，只知道大概概念，平时按流程来做应该就可以了。"
    if q.get("type") == "situational":
        return "遇到这种情况我会冷静一点，先看看问题，再想办法处理。"
    return "我做过一些相关的事情，过程还算顺利，最后也完成了。"


def _medium_answer(q):
    lead = "、".join(q.get("keywords", [])[:3])
    if q.get("type") == "technical":
        return f"我理解这道题主要涉及 {lead} 这些点。先把概念讲清楚，再在项目里注意落地，最后用数据验证效果。"
    if q.get("type") == "situational":
        return f"我会先定位问题，再和团队沟通 {lead} 相关的方案，确定优先级后执行，最后复盘。"
    return f"我在一个项目里负责相关工作，涉及 {lead} 这些方面，和团队协作完成了任务，最后取得了一定成果。"


def _strong_answer(q):
    """基于高分示例再加结构与量化收尾，模拟高水平作答。"""
    base = q.get("sample", "")
    if q.get("type") == "technical":
        return "首先，" + base + " 综上，我会结合场景、数据与一致性做取舍，并在落地后用指标验证。"
    if q.get("type") == "situational":
        return "我的处理分四步：先止损、再定位、然后给预案、最后复盘。" + base
    return "第一，" + base + " 最后，我会用具体数据复盘结果，沉淀成可复用的方法。"


def _finalize_local(sess, answers):
    scores = [a.score for a in answers]
    sess.total_score = round(sum(scores) / len(scores), 1)

    dim_totals = {d: [] for d in DIMENSIONS}
    for a in answers:
        for d, v in a.dimension_dict().items():
            if d in dim_totals:
                dim_totals[d].append(v)
    dim_avg = {d: round(sum(v) / len(v)) if v else 60 for d, v in dim_totals.items()}
    sess.dimensions = json.dumps(dim_avg)

    rank = sorted(DIMENSIONS, key=lambda d: dim_avg.get(d, 0), reverse=True)
    strong = rank[:2]
    weak = list(reversed(rank[-2:]))
    sess.summary = (
        f"本场共 {len(answers)} 题，平均 {sess.total_score} 分。"
        f"“{'、'.join(strong)}”表现最好，“{'、'.join(weak)}”最需要加强。"
    )
    sess.status = "finished"
    sess.finished_at = datetime.utcnow()


def _run_session(user, profile, family, qids, answer_fn, created_at):
    sess = InterviewSession(
        user_id=user.id,
        job_family=family,
        target_job=profile.target_job or "",
        level=profile.level or "校招",
        question_ids=json.dumps(qids),
        current_index=len(qids),
        created_at=created_at,
    )
    db.session.add(sess)
    db.session.flush()

    answers = []
    for qid in qids:
        q = get_question(qid)
        if not q:
            continue
        content = answer_fn(q)
        result = grade_offline(q, content, profile)
        a = Answer(
            session_id=sess.id,
            question_id=q["id"],
            question_title=q["title"],
            question_type=q["type"],
            dimensions=json.dumps(result["dimensions"]),
            content=content,
            score=result["score"],
            feedback=json.dumps(
                {
                    "strengths": result.get("strengths", []),
                    "improvements": result.get("improvements", []),
                    "sample": result.get("sample", ""),
                    "band": result.get("band", ""),
                    "evidence": result.get("evidence", []),
                    "score_breakdown": result.get("score_breakdown", {}),
                }
            ),
            graded_by="rule",
            created_at=created_at + timedelta(minutes=len(answers) + 1),
        )
        db.session.add(a)
        answers.append(a)

    _finalize_local(sess, answers)
    return sess


def ensure_demo():
    """幂等创建演示账号并补齐历史数据。返回 User。"""
    user = User.query.filter_by(username=DEMO_USERNAME).first()
    if not user:
        user = User(username=DEMO_USERNAME, password_hash=_hash_password(DEMO_PASSWORD))
        db.session.add(user)
        db.session.flush()
        profile = Profile(user_id=user.id, **DEMO_PROFILE)
        db.session.add(profile)
    profile = user.profile

    # 已播好就只登录，不重复造数
    if user.sessions.count() >= 5:
        db.session.commit()
        return user

    now = datetime.utcnow()

    # 技术方向：弱 → 中 → 强，演示成长曲线
    tech_weak = build_session_questions("tech", count=5, level="校招", offset=0)
    tech_mid = build_session_questions("tech", count=5, level="校招", offset=1)
    tech_strong = build_session_questions("tech", count=5, level="校招", offset=2)
    _run_session(user, profile, "tech", tech_weak, _weak_answer, now - timedelta(days=6))
    _run_session(user, profile, "tech", tech_mid, _medium_answer, now - timedelta(days=3))
    _run_session(user, profile, "tech", tech_strong, _strong_answer, now)

    # 产品方向：一场完整优质作答
    product_qids = build_session_questions("product", count=5, level="校招", offset=1)
    _run_session(user, profile, "product", product_qids, _strong_answer, now - timedelta(days=2))

    # 数据方向：一场中等水平作答
    data_qids = build_session_questions("data", count=5, level="校招", offset=2)
    _run_session(user, profile, "data", data_qids, _medium_answer, now - timedelta(days=4))

    db.session.commit()
    return user