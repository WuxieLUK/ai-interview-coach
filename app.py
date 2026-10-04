# -*- coding: utf-8 -*-
import os

from flask import Flask

from models import db
from routes import bp


def _load_dotenv(path):
    """轻量 .env 加载：不引入额外依赖，兼容 KEY=VALUE / export 与双引号。"""
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip().replace("export ", "").strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def create_app():
    app = Flask(__name__)
    base_dir = os.path.dirname(os.path.abspath(__file__))

    _load_dotenv(os.path.join(base_dir, ".env"))

    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(base_dir, "interview_coach.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or os.urandom(24).hex()
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.json.ensure_ascii = False

    db.init_app(app)
    app.register_blueprint(bp)

    with app.app_context():
        db.create_all()
    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)