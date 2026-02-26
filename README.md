[**中文文档**](./README_zh.md) | English

# AIdrama — AI Short Drama Auto-Generation Tool

> Just describe your story idea in plain words — AI automatically generates scripts, storyboards, character images, video clips, and composites them into a complete short drama MP4.

---

## Quick Start

### Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.11+ | [python.org](https://python.org) |
| Node.js | 18+ | [nodejs.org](https://nodejs.org) |
| FFmpeg | any | `brew install ffmpeg` (macOS) |

### 1. Clone & Install Dependencies

```bash
git clone https://github.com/ClarkOu/AIvideo.git
cd AIvideo

# Backend
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

### 2. Configure API Keys

```bash
cp .env.example .env
# Edit .env and fill in the required keys:
```

| Key | Required | Description |
|-----|----------|-------------|
| `LLM_API_KEY` | ✅ | LLM text generation (SiliconFlow / OpenAI-compatible) |
| `LLM_BASE_URL` | ✅ | LLM endpoint, e.g. `https://api.siliconflow.cn/v1` |
| `LLM_MODEL` | ✅ | Model name, e.g. `deepseek-ai/DeepSeek-V3.2` |
| `SEEDANCE_API_KEY` | ✅ | Video generation (Volcengine Seedance) |
| `SEEDREAM_API_KEY` | Optional | Character image AI generation (upload-only if not set) |
| `BACKEND_URL` | Default | Backend URL, defaults to `http://localhost:8000` |

### 3. Run

```bash
# Option 1: One-click start
chmod +x start.sh && ./start.sh

# Option 2: Start separately
# Terminal 1 - Backend
cd backend && source .venv/bin/activate
uvicorn backend.main:app --reload --port 8000

# Terminal 2 - Frontend
cd frontend && npm run dev
```

- Frontend: http://localhost:3000
- Backend API docs: http://localhost:8000/docs

---

## Core Workflow

```
1. Create project → Set title, style, tone
2. Open "Character Library" → Add characters → Upload / AI-generate reference images (multi-image)
3. Add episodes with outlines (supports AI batch outline generation)
4. Click "Generate Script + Storyboard" → AI streams script + auto-splits into segment prompts
5. (Optional) Edit in script editor or segment cards
6. Click "Batch Generate Drafts" → Seedance videos push in real-time, review each one
7. All approved → Click "Compose Episode" → FFmpeg concat → Download MP4
```

---

## Key Features

### Character Library
- Three ways to add images: local upload / text-to-image (Seedream) / image-to-image
- Multi-image management: set primary, delete individual, thumbnail strip preview
- Images stored as HTTP URLs, directly accessible by Seedance
- Auto-injects character reference images during video generation (`role: "reference_image"`, up to 4)

### Script & Storyboard
- LLM generates complete script + structured storyboard data in one pass
- SSE streaming typewriter effect — watch AI write in real-time
- Each segment has independent prompt, supports manual edit + regeneration
- LLM intelligently decides video duration per segment (4–12 seconds)

### Video Generation
- Seedance 1.5 Pro async tasks + status polling
- Segment state machine: `prompt_ready → draft_pending → drafting → draft_review → done`
- Single / batch submission, SSE real-time progress push
- Rejected drafts return to prompt editing for regeneration

### Episode Composition
- One-click compose after all segments are done
- Auto-downloads remote videos → FFmpeg concat → outputs MP4
- Download button appears in frontend after completion

---

## Project Structure

```
AIdrama/
├── .env.example         # Config file template
├── .gitignore
├── start.sh             # One-click start script
├── backend/
│   ├── main.py          # FastAPI entry + SSE endpoints
│   ├── core/
│   │   ├── config.py    # Settings (Pydantic Settings)
│   │   ├── database.py  # SQLAlchemy + SQLite
│   │   └── events.py    # In-process event bus
│   ├── models/          # Data models (Project / Episode / Segment / Character)
│   ├── api/             # REST routes (projects / episodes / segments / characters)
│   ├── agents/          # 5 Agents
│   │   ├── orchestrator.py  # Orchestration hub, event routing
│   │   ├── script_agent.py  # LLM script generation
│   │   ├── image_agent.py   # Seedream image generation
│   │   ├── video_agent.py   # Seedance video generation
│   │   └── compose_agent.py # FFmpeg composition
│   └── requirements.txt
├── frontend/
│   ├── pages/           # Next.js pages
│   │   ├── index.tsx            # Project list
│   │   ├── project/[id].tsx     # Project detail
│   │   ├── episode/[id].tsx     # Episode workspace
│   │   └── characters/[pid].tsx # Character library
│   ├── components/      # UI components
│   │   ├── CharacterCard.tsx    # Character card (multi-image gallery)
│   │   ├── SegmentCard.tsx      # Segment card
│   │   ├── ScriptEditor.tsx     # Script editor
│   │   ├── ImageGenPanel.tsx    # Image generation panel
│   │   └── EpisodeTimeline.tsx  # Progress timeline
│   ├── lib/api.ts       # Axios API client
│   ├── next.config.js   # Proxy /api + /assets → backend
│   └── package.json
└── assets/              # Runtime generated (gitignored)
    ├── chars/           # Character images
    └── output/          # Composed videos
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11 + FastAPI + SQLAlchemy + SQLite |
| Frontend | Next.js 14 + Tailwind CSS |
| LLM | DeepSeek V3.2 / OpenAI-compatible (SiliconFlow) |
| Image Gen | Seedream 3.0 (Volcengine, optional) |
| Video Gen | Seedance 1.5 Pro (Volcengine) |
| Video Compose | FFmpeg (local) |
| Real-time | Server-Sent Events (SSE) |

---

## License

MIT
