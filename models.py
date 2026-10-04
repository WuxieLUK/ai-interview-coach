import json
from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    profile = db.relationship("Profile", backref="user", uselist=False)
    sessions = db.relationship("InterviewSession", backref="user", lazy="dynamic")


class Profile(db.Model):
    __tablename__ = "profiles"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    name = db.Column(db.String(64), default="")
    target_job = db.Column(db.String(128), default="")
    job_family = db.Column(db.String(32), default="general")
    level = db.Column(db.String(32), default="校招")  # 校招 / 实习 / 社招
    experience = db.Column(db.Text, default="")
    skills = db.Column(db.Text, default="")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class InterviewSession(db.Model):
    __tablename__ = "interview_sessions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    job_family = db.Column(db.String(32), default="general")
    target_job = db.Column(db.String(128), default="")
    level = db.Column(db.String(32), default="校招")
    question_ids = db.Column(db.Text, default="[]")  # JSON
    current_index = db.Column(db.Integer, default=0)
    status = db.Column(db.String(16), default="active")  # active / finished
    total_score = db.Column(db.Float, default=0.0)
    dimensions = db.Column(db.Text, default="{}")  # JSON {维度: 均分}
    summary = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    finished_at = db.Column(db.DateTime, nullable=True)
    answers = db.relationship("Answer", backref="session", lazy="dynamic", cascade="all, delete-orphan")

    def question_id_list(self):
        return json.loads(self.question_ids or "[]")

    def dimension_dict(self):
        return json.loads(self.dimensions or "{}")


class Answer(db.Model):
    __tablename__ = "answers"
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("interview_sessions.id"), nullable=False)
    question_id = db.Column(db.String(32), default="")
    question_title = db.Column(db.Text, default="")
    question_type = db.Column(db.String(16), default="general")
    dimensions = db.Column(db.Text, default="{}")  # JSON 该题涉及的维度
    content = db.Column(db.Text, default="")
    score = db.Column(db.Float, default=0.0)
    feedback = db.Column(db.Text, default="{}")  # JSON {strengths, improvements, sample}
    graded_by = db.Column(db.String(8), default="rule")  # ai / rule
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def dimension_dict(self):
        return json.loads(self.dimensions or "{}")

    def feedback_dict(self):
        return json.loads(self.feedback or "{}")
