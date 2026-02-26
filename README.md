# AIdrama — AI 短剧自动生成工具

> 只需用大白话说出你的故事想法，AI 自动生成剧本、分镜、角色图、视频片段，最终合成完整短剧 MP4。

---

## 快速启动

### 前置准备

| 工具 | 版本 | 安装 |
|------|------|------|
| Python | 3.11+ | [python.org](https://python.org) |
| Node.js | 18+ | [nodejs.org](https://nodejs.org) |
| FFmpeg | 任意 | `brew install ffmpeg` (macOS) |

### 1. 配置 API Key

```bash
cp backend/.env.example backend/.env
# 编辑 backend/.env，填写：
#   ANTHROPIC_API_KEY   或 OPENAI_API_KEY
#   SEEDREAM_API_KEY    （角色图生成，火山方舟）
#   SEEDANCE_API_KEY    （视频生成，火山方舟）
```

### 2. 启动

```bash
chmod +x start.sh
./start.sh
```

- 前端：http://localhost:3000
- 后端 API 文档：http://localhost:8000/docs

---

## 核心流程

```
1. 新建项目 → 填写剧名、风格、基调
2. 进入「角色图库」→ 添加角色（姓名 + 形象描述）→ 生成/上传角色图
3. 添加分集，填写梗概
4. 点「生成脚本+分镜」→ AI 一次输出完整剧本 + 所有分镜 Prompt
5. （可选）在剧本编辑器或分镜卡片里修改内容
6. 点「批量生成草稿」→ 草稿视频实时推送，逐个审核通过/退回
7. 通过的分镜自动进入正式生成
8. 全部完成后点「合成整集」→ 下载 MP4
```

---

## 目录结构

```
AIdrama/
├── backend/
│   ├── models/          # SQLAlchemy 数据模型
│   ├── agents/          # 5 个 Agent（Orchestrator / Image / Script / Video / Compose）
│   ├── api/             # FastAPI 路由
│   ├── core/            # 配置、数据库、事件总线
│   └── main.py          # 应用入口 + SSE
├── frontend/
│   ├── pages/           # Next.js 页面
│   ├── components/      # UI 组件
│   └── lib/api.ts       # API 客户端
├── assets/              # 角色图、场景图、输出视频
└── start.sh             # 一键启动
```

---

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.11 + FastAPI + SQLAlchemy + SQLite |
| 任务队列 | Celery + Redis（可选，MVP 可先跳过）|
| 视频合成 | FFmpeg（本地） |
| 前端 | Next.js 14 + Tailwind CSS |
| LLM | Claude 3.5 Sonnet / GPT-4o |
| 图片生成 | Seedream 3.0（火山方舟）|
| 视频生成 | Seedance 1.5 Pro（火山方舟）|
