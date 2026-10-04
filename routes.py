# -*- coding: utf-8 -*-
import hashlib
import json
import re
import secrets
import time
from datetime import datetime
from functools import wraps

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from ai_helper import ai_available, grade_answer
from demo import ensure_demo
from grader import band_name
from models import Answer, InterviewSession, Profile, User, db
from question_bank import DIMENSIONS, JOB_FAMILIES, build_session_questions, get_question
from reporting import insights_analysis, session_report

bp = Blueprint("main", __name__)

USERNAME_RE = re.compile(r"^[A-Za-z0-9_\u4e00-\u9fa5]{2,20}$")
VALID_FAMILIES = {f["key"] for f in JOB_FAMILIES}

# 登录失败节流：key -> 最近 10 分钟内的失败时间戳
LOGIN_FAILURES = {}


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("ascii"), 100_000
    ).hex()
    return f"{salt}${digest}"


def verify_password(password, stored):
    try:
        salt, digest = stored.split("$")
    except ValueError:
        return False
    return secrets.compare_digest(hash_password(password, salt).split("$")[1], digest)


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "uid" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"ok": False, "error": "请先登录"}), 401
            return redirect(url_for("main.login"))
        return fn(*args, **kwargs)

    return wrapper


def current_user():
    return db.session.get(User, session.get("uid"))


def family_name(key):
    for f in JOB_FAMILIES:
        if f["key"] == key:
            return f["name"]
    return "通用"


def _login_failure_key():
    return request.remote_addr + "|" + (request.form.get("username") or "").strip().lower()


def _login_throttled(key):
    now = time.time()
    entries = [t for t in LOGIN_FAILURES.get(key, []) if now - t < 600]
    LOGIN_FAILURES[key] = entries
    return len(entries) >= 8


def _login_record(key):
    now = time.time()
    LOGIN_FAILURES.setdefault(key, []).append(now)
    LOGIN_FAILURES[key] = [t for t in LOGIN_FAILURES[key] if now - t < 600]


# ---------- 页面 ----------


@bp.route("/")
def index():
    """公开落地页；已登录用户直接进入工作台。"""
    if "uid" in session:
        return redirect(url_for("main.dashboard"))
    return render_template("landing.html", jobs=JOB_FAMILIES)


@bp.route("/demo")
def demo_login():
    """一键进入演示账号：无数据则自动播种，有数据则直接登录。"""
    user = ensure_demo()
    session["uid"] = user.id
    return redirect(url_for("main.dashboard"))


@bp.route("/register", methods=["GET", "POST"])
def register():
    if "uid" in session:
        return redirect(url_for("main.dashboard"))
    error = ""
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if not USERNAME_RE.match(username):
            error = "用户名需 2-20 位，仅支持中英文、数字和下划线"
        elif len(password) < 6 or len(password) > 64:
            error = "密码长度需在 6-64 位之间"
        elif User.query.filter_by(username=username).first():
            error = "用户名已存在"
        else:
            user = User(username=username, password_hash=hash_password(password))
            db.session.add(user)
            db.session.flush()
            db.session.add(Profile(user_id=user.id))
            db.session.commit()
            session["uid"] = user.id
            return redirect(url_for("main.dashboard"))
    return render_template("register.html", error=error)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if "uid" in session:
        return redirect(url_for("main.dashboard"))
    error = ""
    if request.method == "POST":
        key = _login_failure_key()
        if _login_throttled(key):
            error = "尝试次数过多，请 10 分钟后再试"
        else:
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""
            user = User.query.filter_by(username=username).first()
            if user and verify_password(password, user.password_hash):
                session["uid"] = user.id
                return redirect(url_for("main.dashboard"))
            _login_record(key)
            error = "用户名或密码错误"
    return render_template("login.html", error=error)


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("main.login"))


@bp.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    return render_template("dashboard.html", jobs=JOB_FAMILIES, ai_on=ai_available())


@bp.route("/interview/<int:sid>")
@login_required
def interview_page(sid):
    return render_template("interview.html", sid=sid)


@bp.route("/report/<int:sid>")
@login_required
def report_page(sid):
    return render_template("report.html", sid=sid)


@bp.route("/history")
@login_required
def history_page():
    return render_template("history.html")


@bp.route("/insights")
@login_required
def insights_page():
    return render_template("insights.html", dims=DIMENSIONS)


# ---------- API ----------


@bp.route("/api/jobs")
def api_jobs():
    return jsonify({"ok": True, "jobs": JOB_FAMILIES, "ai": ai_available()})


@bp.route("/api/profile", methods=["GET"])
@login_required
def api_profile_get():
    user = current_user()
    p = user.profile
    return jsonify(
        {
            "ok": True,
            "profile": {
                "name": p.name,
                "target_job": p.target_job,
                "job_family": p.job_family,
                "level": p.level,
                "experience": p.experience,
                "skills": p.skills,
            },
        }
    )


@bp.route("/api/profile", methods=["POST"])
@login_required
def api_profile_save():
    user = current_user()
    data = request.get_json(silent=True) or {}
    p = user.profile
    p.name = (data.get("name") or p.name or "").strip()[:64]
    p.target_job = (data.get("target_job") or p.target_job or "").strip()[:128]
    family = (data.get("job_family") or p.job_family or "general").strip()
    p.job_family = family if family in VALID_FAMILIES else "general"
    level = (data.get("level") or p.level or "校招").strip()
    p.level = level if level in ("实习", "校招", "社招") else "校招"
    p.experience = (data.get("experience") or p.experience or "").strip()[:2000]
    p.skills = (data.get("skills") or p.skills or "").strip()[:500]
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/api/session/start", methods=["POST"])
@login_required
def api_session_start():
    user = current_user()
    data = request.get_json(silent=True) or {}
    family = (data.get("job_family") or user.profile.job_family or "general").strip()
    if family not in VALID_FAMILIES:
        family = "general"
    level = user.profile.level or "校招"

    try:
        count = int(data.get("count", 5))
    except (TypeError, ValueError):
        count = 5
    count = max(3, min(8, count))

    # 用历史场次做轮换偏移，避免每次练到同一组题
    offset = user.sessions.count()
    qids = build_session_questions(family, count=count, level=level, offset=offset)

    sess = InterviewSession(
        user_id=user.id,
        job_family=family,
        target_job=user.profile.target_job or "",
        level=level,
        question_ids=json.dumps(qids),
        current_index=0,
    )
    db.session.add(sess)
    db.session.commit()
    return jsonify({"ok": True, "session_id": sess.id, "total": len(qids)})


def _session_or_403(sid):
    user = current_user()
    sess = db.session.get(InterviewSession, sid)
    if not sess or sess.user_id != user.id:
        return None
    return sess

@bp.route("/api/session/<int:sid>")
@login_required
def api_session_get(sid):
    sess = _session_or_403(sid)
    if not sess:
        return jsonify({"ok": False, "error": "会话不存在"}), 404
    qids = sess.question_id_list()
    idx = sess.current_index
    question = get_question(qids[idx]) if idx < len(qids) else None
    answered = sess.answers.count()
    return jsonify(
        {
            "ok": True,
            "session": {
                "id": sess.id,
                "family": sess.job_family,
                "family_name": family_name(sess.job_family),
                "target_job": sess.target_job,
                "level": sess.level,
                "status": sess.status,
                "current_index": idx,
                "total": len(qids),
                "answered": answered,
            },
            "question": question
            and {
                "id": question["id"],
                "type": question["type"],
                "title": question["title"],
                "difficulty": question.get("difficulty", 1),
            },
        }
    )


@bp.route("/api/session/<int:sid>/answer", methods=["POST"])
@login_required
def api_session_answer(sid):
    sess = _session_or_403(sid)
    if not sess:
        return jsonify({"ok": False, "error": "会话不存在"}), 404
    if sess.status != "active":
        return jsonify({"ok": False, "error": "该面试已结束"}), 400
    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"ok": False, "error": "回答不能为空"}), 400
    if len(content) > 8000:
        return jsonify({"ok": False, "error": "回答过长，请控制在 8000 字以内"}), 400

    qids = sess.question_id_list()
    idx = sess.current_index
    if idx >= len(qids):
        return jsonify({"ok": False, "error": "没有待回答的题目"}), 400
    q = get_question(qids[idx])
    if not q:
        return jsonify({"ok": False, "error": "题目不存在"}), 500

    result = grade_answer(q, content, current_user().profile)
    answer = Answer(
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
        graded_by=result["graded_by"],
    )
    db.session.add(answer)
    sess.current_index = idx + 1

    finished = sess.current_index >= len(qids)
    next_question = None
    if finished:
        _finalize(sess)
    else:
        nq = get_question(qids[sess.current_index])
        next_question = nq and {
            "id": nq["id"],
            "type": nq["type"],
            "title": nq["title"],
            "difficulty": nq.get("difficulty", 1),
        }
    db.session.commit()
    return jsonify(
        {
            "ok": True,
            "result": result,
            "finished": finished,
            "answered": sess.answers.count(),
            "total": len(qids),
            "next_question": next_question,
            "session_id": sess.id,
        }
    )


def _finalize(sess):
    answers = sess.answers.all()
    if not answers:
        return
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
        f"本场共 {len(answers)} 题，平均 {sess.total_score} 分，整体水平“{band_name(sess.total_score)}”。"
        f"“{'、'.join(strong)}”表现最好，“{'、'.join(weak)}”最需要加强。"
    )
    sess.status = "finished"
    sess.finished_at = datetime.utcnow()


@bp.route("/api/session/<int:sid>/result")
@login_required
def api_session_result(sid):
    sess = _session_or_403(sid)
    if not sess:
        return jsonify({"ok": False, "error": "会话不存在"}), 404

    answers = []
    for a in sess.answers.order_by(Answer.id).all():
        fb = a.feedback_dict()
        answers.append(
            {
                "question_id": a.question_id,
                "question_title": a.question_title,
                "question_type": a.question_type,
                "content": a.content,
                "score": a.score,
                "graded_by": a.graded_by,
                "dimensions": a.dimension_dict(),
                "strengths": fb.get("strengths", []),
                "improvements": fb.get("improvements", []),
                "sample": fb.get("sample", ""),
                "band": fb.get("band", ""),
                "evidence": fb.get("evidence", []),
            }
        )

    report = session_report(sess) if sess.status == "finished" else None
    return jsonify(
        {
            "ok": True,
            "session": {
                "id": sess.id,
                "family_name": family_name(sess.job_family),
                "target_job": sess.target_job,
                "level": sess.level,
                "status": sess.status,
                "total_score": sess.total_score,
                "dimensions": sess.dimension_dict(),
                "summary": (report or {}).get("summary") or sess.summary,
                "created_at": sess.created_at.isoformat(),
            },
            "answers": answers,
            "report": report,
            "tips": (report or {}).get("priority_actions", []),
        }
    )


@bp.route("/api/history")
@login_required
def api_history():
    user = current_user()
    items = []
    for s in user.sessions.order_by(InterviewSession.created_at.desc()).limit(50).all():
        items.append(
            {
                "id": s.id,
                "family_name": family_name(s.job_family),
                "target_job": s.target_job,
                "level": s.level,
                "status": s.status,
                "total_score": s.total_score,
                "created_at": s.created_at.isoformat(),
            }
        )
    return jsonify({"ok": True, "sessions": items})


@bp.route("/api/insights")
@login_required
def api_insights():
    user = current_user()
    analysis = insights_analysis(user)
    return jsonify({"ok": True, **analysis})