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

### 1. 克隆 & 安装依赖

```bash
git clone https://github.com/ClarkOu/AIvideo.git
cd AIvideo

# 后端
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 前端
cd ../frontend
npm install
```

### 2. 配置 API Key

```bash
cp .env.example .env
# 编辑 .env，填写以下必要配置：
```

| 配置项 | 必填 | 说明 |
|--------|------|------|
| `LLM_API_KEY` | ✅ | LLM 文字生成（硅基流动 / OpenAI 兼容） |
| `LLM_BASE_URL` | ✅ | LLM 接口地址，如 `https://api.siliconflow.cn/v1` |
| `LLM_MODEL` | ✅ | 模型名，如 `deepseek-ai/DeepSeek-V3.2` |
| `SEEDANCE_API_KEY` | ✅ | 视频生成（火山引擎 Seedance） |
| `SEEDREAM_API_KEY` | 可选 | 角色图 AI 生成（不填则只能本地上传） |
| `BACKEND_URL` | 默认 | 后端访问地址，默认 `http://localhost:8000` |

### 3. 启动

```bash
# 方式一：一键启动
chmod +x start.sh && ./start.sh

# 方式二：分别启动
# 终端 1 - 后端
cd backend && source .venv/bin/activate
uvicorn backend.main:app --reload --port 8000

# 终端 2 - 前端
cd frontend && npm run dev
```

- 前端：http://localhost:3000
- 后端 API 文档：http://localhost:8000/docs

---

## 核心流程

```
1. 新建项目 → 填写剧名、风格、基调
2. 进入「角色库」→ 添加角色 → 上传 / AI 生成角色参考图（支持多图管理）
3. 添加分集，填写梗概（支持 AI 批量生成大纲）
4. 点「生成脚本+分镜」→ AI 流式输出剧本 + 自动拆分分镜 Prompt
5. （可选）在剧本编辑器或分镜卡片里修改内容
6. 点「批量生成草稿」→ Seedance 视频实时推送，逐个审核通过/退回
7. 全部审核通过后点「合成整集」→ FFmpeg 拼接 → 下载 MP4
```

---

## 主要功能

### 角色库
- 支持本地上传 / 文生图(Seedream) / 图生图 三种方式添加角色图
- 多图管理：设主图、删除单张，缩略条预览
- 图片以 HTTP URL 存储，Seedance 可直接访问
- 视频生成时自动注入角色参考图（`role: "reference_image"`，最多 4 张）

### 脚本 & 分镜
- LLM 一次生成完整剧本 + 结构化分镜数据
- SSE 流式打字机效果，实时看到 AI 写作过程
- 每个分镜独立 Prompt，支持手动编辑后重新生成
- LLM 智能决定每段视频时长（4-12 秒）

### 视频生成
- Seedance 1.5 Pro 异步任务 + 轮询状态
- 分镜状态机：`prompt_ready → draft_pending → drafting → draft_review → done`
- 支持单个/批量提交，SSE 实时推送进度
- 审核不通过可退回修改 Prompt 重新生成

### 整集合成
- 所有分镜 done 后一键合成
- 自动下载远程视频 → FFmpeg concat → 输出 MP4
- 合成完成后前端显示下载按钮

---

## 目录结构

```
AIdrama/
├── .env.example         # 配置文件示例
├── .gitignore
├── start.sh             # 一键启动脚本
├── 设计文档.md
├── backend/
│   ├── main.py          # FastAPI 入口 + SSE 端点
│   ├── core/
│   │   ├── config.py    # 配置项（Pydantic Settings）
│   │   ├── database.py  # SQLAlchemy + SQLite
│   │   └── events.py    # 进程内事件总线
│   ├── models/          # 数据模型（Project / Episode / Segment / Character）
│   ├── api/             # REST 路由（projects / episodes / segments / characters）
│   ├── agents/          # 5 个 Agent
│   │   ├── orchestrator.py  # 编排中心，事件路由
│   │   ├── script_agent.py  # LLM 脚本生成
│   │   ├── image_agent.py   # Seedream 图片生成
│   │   ├── video_agent.py   # Seedance 视频生成
│   │   └── compose_agent.py # FFmpeg 合成
│   └── requirements.txt
├── frontend/
│   ├── pages/           # Next.js 页面
│   │   ├── index.tsx            # 项目列表
│   │   ├── project/[id].tsx     # 项目详情
│   │   ├── episode/[id].tsx     # 分集工作台
│   │   └── characters/[pid].tsx # 角色库
│   ├── components/      # UI 组件
│   │   ├── CharacterCard.tsx    # 角色卡（多图画廊）
│   │   ├── SegmentCard.tsx      # 分镜卡
│   │   ├── ScriptEditor.tsx     # 剧本编辑器
│   │   ├── ImageGenPanel.tsx    # 图片生成面板
│   │   └── EpisodeTimeline.tsx  # 进度时间线
│   ├── lib/api.ts       # Axios API 客户端
│   ├── next.config.js   # 代理 /api + /assets → 后端
│   └── package.json
└── assets/              # 运行时生成（已 gitignore）
    ├── chars/           # 角色图片
    └── output/          # 合成视频
```

---

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.11 + FastAPI + SQLAlchemy + SQLite |
| 前端 | Next.js 14 + Tailwind CSS |
| LLM | DeepSeek V3.2 / OpenAI 兼容接口（硅基流动） |
| 图片生成 | Seedream 3.0（火山引擎，可选） |
| 视频生成 | Seedance 1.5 Pro（火山引擎） |
| 视频合成 | FFmpeg（本地） |
| 实时通信 | Server-Sent Events (SSE) |

---

## License

MIT
