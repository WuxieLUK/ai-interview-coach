# -*- coding: utf-8 -*-
# 接口冒烟测试：注册登录 → 画像 → 面试全流程 → 报告/历史/洞察
import json
import os
import tempfile

os.environ["SECRET_KEY"] = "test"

import app as app_module

app_module.app.config.update(
    SQLALCHEMY_DATABASE_URI="sqlite:///" + os.path.join(tempfile.gettempdir(), "coach_test.db"),
    TESTING=True,
)

from models import db
from question_bank import QUESTIONS


def main():
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
    client = app_module.app.test_client()

    # 题库内容完整性
    assert len(QUESTIONS["tech"]) >= 6
    assert len(QUESTIONS["general"]) >= 10
    for family, items in QUESTIONS.items():
        for q in items:
            assert q.get("title") and q.get("keywords") and q.get("dims")
            assert q.get("rubric") and q.get("sample")

    # 注册登录
    r = client.post("/register", data={"username": "tester", "password": "123456"}, follow_redirects=True)
    assert r.status_code == 200

    # 保存画像
    r = client.post("/api/profile", json={"name": "小李", "target_job": "后端开发工程师", "job_family": "tech", "level": "校招", "experience": "熟悉 Python/Flask"})
    assert r.get_json()["ok"], "保存画像失败"

    # 开始面试
    r = client.post("/api/session/start", json={"job_family": "tech"})
    data = r.get_json()
    assert data["ok"], "开始面试失败"
    sid = data["session_id"]
    assert data["total"] == 5

    # 逐题作答
    answers = [
        "我熟悉 Python 和 Flask，做过校园二手交易平台后端，负责用户认证和商品接口，用索引优化了查询，线上日请求量提升明显。",
        "这个项目让我最有挑战的是并发下单问题。我负责设计缓存和消息队列方案，通过限流降级保证稳定性，最后接口 P99 从 2 秒降到 300 毫秒，获得了团队认可。",
        "RESTful API 以资源为中心，用 GET POST 等动词表达操作，用状态码表达语义；GraphQL 让客户端自己选字段，解决过度获取问题。",
        "我最近在学习分布式系统，看了很多资料也做了笔记，还写了一个小的 demo 练习，感觉收获很大。",
        "遇到这种情况我会先止损回滚，然后看监控日志定位问题，找到原因后修复并写复盘文档，避免下次再犯。",
    ]
    for i, a in enumerate(answers):
        r = client.post(f"/api/session/{sid}/answer", json={"content": a})
        d = r.get_json()
        assert d["ok"], f"第{i+1}题作答失败: {d}"
        result = d["result"]
        assert 0 <= result["score"] <= 100
        assert result["graded_by"] in ("ai", "rule")
        assert result.get("band")
        assert len(result["dimensions"]) == 5
        assert result["strengths"] and result["improvements"]
        assert d["finished"] is (i == 4)

    # 报告：含整体画像与训练计划
    r = client.get(f"/api/session/{sid}/result")
    d = r.get_json()
    assert d["ok"] and d["session"]["status"] == "finished"
    assert d["session"]["total_score"] > 0
    assert len(d["session"]["dimensions"]) == 5
    assert len(d["answers"]) == 5
    assert d["report"]["band"]
    assert len(d["report"]["strongest"]) == 2 and len(d["report"]["weakest"]) == 2
    assert len(d["report"]["dimension_analysis"]) == 5
    assert d["report"]["priority_actions"]
    assert d["tips"]

    # 历史与洞察
    h = client.get("/api/history").get_json()
    assert h["ok"] and len(h["sessions"]) == 1
    ins = client.get("/api/insights").get_json()
    assert ins["ok"] and ins["sessions"] == 1 and len(ins["dims"]) == 5
    assert ins["strongest"] and ins["weakest"]
    assert ins["recommendations"]

    # 未登录保护
    client2 = app_module.app.test_client()
    assert client2.get("/api/history").status_code == 401

    print("[OK] smoke tests passed: content bank, 5 graded answers, rich report/insights, auth guard")


if __name__ == "__main__":
    main()