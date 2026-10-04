# 🎯 AI 面试陪练（Mock Interview Coach）

> 模拟面试 → 逐题结构化点评 → 五维能力画像 → 训练计划 → 越练越强。
>
> 一个基于 Flask + SQLite 的本地模拟面试 Web 应用：**大模型优先 + 离线规则兜底**双引擎设计，
> **未配置任何 API Key 也能完整运行**。

## ✨ 功能

| 模块 | 说明 |
|---|---|
| **目标岗位画像** | 填写目标岗位、求职阶段（实习/校招/社招）、技能与经历，作为出题与点评的上下文 |
| **自适应组卷** | 5 大方向 44 题，每场按“破冰 → 岗位基础 → 行为故事 → 岗位进阶 → 综合情景”的难度节奏组卷，并按历史场次轮换题目 |
| **结构化题库** | 每题内置评分要点、四档评分细则、高分参考答案与面试官追问 |
| **证据化点评** | 逐题输出得分、分档、五维能力、优点、改进建议、引用原话的证据与更优示例 |
| **双引擎评分** | 配置大模型（默认 DeepSeek，兼容任意 OpenAI 接口）输出深度点评；未配置自动回退**离线规则评分器**（关键词覆盖 / STAR 结构 / 量化细节 / 表达条理 / 情景四步法） |
| **面试报告** | 总分 + 整体分档 + 五维能力条形图 + 维度解读 + 训练计划 + 逐题回顾，支持打印 / 导出 PDF |
| **能力洞察** | 跨场次五维雷达图、强项短板、最近趋势与成长建议（ECharts 本地化，无 CDN 依赖） |
| **用户系统** | 注册 / 登录（PBKDF2 加盐哈希、登录失败节流）、会话管理、历史记录、资源按用户隔离 |

## 🧠 五维能力模型

- **专业能力** — 岗位知识点覆盖度与深度，能否讲清原理并给出量化结果
- **逻辑表达** — 分点作答、STAR 结构、因果链条与时间感
- **沟通协作** — 行为故事中的角色、沟通方式与冲突处理
- **应变能力** — 情景题“止损-定位-预案-复盘”的推进能力
- **岗位匹配** — 回答与目标岗位 / JD 的贴合度

## 🛠 技术栈

- **后端**：Python · Flask · Flask-SQLAlchemy · SQLite
- **前端**：原生 HTML/CSS/JS（无框架）· ECharts 5（本地化）
- **AI 接入**：OpenAI 兼容 Chat API（默认 DeepSeek），可选任意兼容服务
- **安全**：PBKDF2 加盐密码哈希、登录失败节流、登录会话、资源按用户隔离

## 🚀 快速开始

环境要求：Python 3.9+

```bash
cd ai-interview-coach
python -m venv .venv
# Windows
.\.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt   # 国内网络可加 -i https://pypi.tuna.tsinghua.edu.cn/simple
python app.py
```

浏览器打开 **http://127.0.0.1:5000/** 即可使用。
数据库 `interview_coach.db` 首次启动自动创建。

### 一键演示

面试官展示时，直接打开 **http://127.0.0.1:5000/demo**：
自动创建演示账号（`demo` / `demo123`）并补齐 5 场不同岗位、强弱递进的历史数据，无需注册、无需 API Key。
完整走查脚本见 [`DEMO.md`](DEMO.md)。

## ⚙️ 配置大模型（可选，不配也能跑）

复制 `.env.example` 为 `.env`，程序启动时会自动读取：

| 变量 | 说明 |
|---|---|
| `AI_API_KEY` | 必填（启用 AI 点评）；兼容 `DEEPSEEK_API_KEY` / `OPENAI_API_KEY` 别名 |
| `AI_BASE_URL` | 可选，默认 `https://api.deepseek.com`，可指向任意 OpenAI 兼容端点 |
| `AI_MODEL` | 可选，默认 `deepseek-chat` |
| `AI_TIMEOUT` | 可选，单次请求超时秒数，默认 60 |
| `AI_MAX_RETRIES` | 可选，失败重试次数，默认 2 |
| `SECRET_KEY` | 可选，Flask 会话密钥，默认自动生成 |

未配置时自动以**离线规则模式**运行，全部功能可用。

## 📁 项目结构

```
├── app.py               # Flask 入口（含 .env 自动加载）
├── routes.py            # 路由与 API（认证/画像/面试/报告/历史/洞察）
├── models.py            # ORM 模型（用户/画像/会话/回答）
├── question_bank.py     # 内置题库：5 方向 44 题，含细则/示例/追问
├── grader.py            # 离线规则评分器（关键词/STAR/量化/条理/情景四步法）
├── reporting.py         # 报告与洞察分析（分档/强弱项/维度解读/训练计划）
├── ai_client.py         # OpenAI 兼容大模型客户端（重试/超时/JSON 模式）
├── ai_helper.py         # 双引擎：大模型优先 + 离线兜底
├── templates/           # 8 个页面模板
├── static/              # style.css / app.js / echarts.min.js（本地）
├── test_api.py          # 接口冒烟测试
└── requirements.txt
```

## 🧪 测试

```bash
python test_api.py
```

覆盖：题库完整性 → 注册登录 → 保存画像 → 开始面试 → 逐题作答评分 → 报告/历史/洞察 → 未登录保护。

## 📄 说明

- 本项目为个人学习 / 作品展示项目，题库为演示数据，可自行扩充 `question_bank.py`。
- 商用部署请设置强随机 `SECRET_KEY`、关闭调试模式，并置于 HTTPS 后使用。
- 与任何公司 / 招聘平台无关联。