from __future__ import annotations
import logging
import asyncio
import json
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from backend.core.database import init_db
from backend.core.config import settings
from backend.core.events import (
    event_bus,
    SEGMENT_STATUS_UPDATED, CHARACTER_IMAGE_DONE, COMPOSE_DONE,
    SCRIPT_SEGMENTS_READY, SCRIPT_STREAM_CHUNK,
    OUTLINES_READY, OUTLINE_STREAM_CHUNK,
)
from backend.agents.orchestrator import init_orchestrator
from backend.api import characters, projects, episodes, segments

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── SSE 推送队列 ───────────────────────────────────────────────
# ep_id  → [Queue, ...]   分集级（分镜状态、脚本就绪、合成完成）
# proj_id → [Queue, ...]  项目级（图片生成完成等）
_ep_queues:   dict[str, list[asyncio.Queue]] = {}
_proj_queues: dict[str, list[asyncio.Queue]] = {}


def _ep_subscribe(ep_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    _ep_queues.setdefault(ep_id, []).append(q)
    return q


def _ep_unsubscribe(ep_id: str, q: asyncio.Queue):
    lst = _ep_queues.get(ep_id, [])
    if q in lst:
        lst.remove(q)


def _proj_subscribe(proj_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    _proj_queues.setdefault(proj_id, []).append(q)
    return q


def _proj_unsubscribe(proj_id: str, q: asyncio.Queue):
    lst = _proj_queues.get(proj_id, [])
    if q in lst:
        lst.remove(q)


async def _broadcast_ep(ep_id: str, data: dict):
    for q in _ep_queues.get(ep_id, []):
        await q.put(data)


async def _broadcast_proj(proj_id: str, data: dict):
    for q in _proj_queues.get(proj_id, []):
        await q.put(data)


# ── 事件 → SSE 广播 ────────────────────────────────────────────
async def _on_segment_updated(payload: dict):
    ep_id = payload.get("ep_id") or ""
    await _broadcast_ep(ep_id, {"type": "segment_status", **payload})


async def _on_script_ready(payload: dict):
    ep_id = payload.get("ep_id") or ""
    await _broadcast_ep(ep_id, {
        "type": "script_ready",
        "ep_id": ep_id,
        "segment_count": len(payload.get("segments", [])),
    })


async def _on_image_done(payload: dict):
    proj_id = payload.get("project_id") or ""
    if proj_id:
        await _broadcast_proj(proj_id, {"type": "image_done", **payload})
    else:
        # project_id 丢失时广播给所有项目订阅者
        for qs in _proj_queues.values():
            for q in qs:
                await q.put({"type": "image_done", **payload})


async def _on_compose_done(payload: dict):
    ep_id = payload.get("ep_id") or ""
    # 将本地路径转换为可访问的 HTTP URL
    output_path = payload.get("output_path", "")
    if output_path:
        # "./assets/output/xxx.mp4" → "/assets/output/xxx.mp4"
        relative = output_path.lstrip(".")
        output_url = f"{settings.BACKEND_URL}{relative}"
    else:
        output_url = ""
    await _broadcast_ep(ep_id, {"type": "compose_done", "ep_id": ep_id, "output_url": output_url})


async def _on_stream_chunk(payload: dict):
    ep_id = payload.get("ep_id") or ""
    await _broadcast_ep(ep_id, {"type": "script_chunk", "delta": payload.get("delta", "")})


async def _on_outlines_ready(payload: dict):
    proj_id = payload.get("project_id") or ""
    if proj_id:
        await _broadcast_proj(proj_id, {
            "type":    "outlines_ready",
            "count":   len(payload.get("outlines", [])),
            "outlines": payload.get("outlines", []),
        })


async def _on_outline_chunk(payload: dict):
    proj_id = payload.get("project_id") or ""
    if proj_id:
        await _broadcast_proj(proj_id, {
            "type":  "outline_chunk",
            "delta": payload.get("delta", ""),
        })


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("数据库已初始化")
    init_orchestrator()
    logger.info("Orchestrator 已启动")

    # 注册 SSE 广播订阅
    event_bus.subscribe(SEGMENT_STATUS_UPDATED, _on_segment_updated)
    event_bus.subscribe(SCRIPT_SEGMENTS_READY,  _on_script_ready)
    event_bus.subscribe(SCRIPT_STREAM_CHUNK,    _on_stream_chunk)
    event_bus.subscribe(CHARACTER_IMAGE_DONE,   _on_image_done)
    event_bus.subscribe(COMPOSE_DONE,           _on_compose_done)
    event_bus.subscribe(OUTLINES_READY,         _on_outlines_ready)
    event_bus.subscribe(OUTLINE_STREAM_CHUNK,   _on_outline_chunk)

    yield
    logger.info("应用关闭")


app = FastAPI(
    title="AIdrama API",
    description="AI 短剧自动生成工具后端",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js 开发服务器
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态资源（角色图、场景图、输出视频）
app.mount("/assets", StaticFiles(directory=settings.ASSETS_DIR), name="assets")

# ── 路由注册 ─────────────────────────────────────────────────────
app.include_router(characters.router, prefix="/api")
app.include_router(projects.router,   prefix="/api")
app.include_router(episodes.router,   prefix="/api")
app.include_router(segments.router,   prefix="/api")


# ── SSE 实时推送端点 ──────────────────────────────────────────────
@app.get("/api/sse/{ep_id}")
async def sse_episode(ep_id: str, request: Request):
    """分集级 SSE：分镜状态变更 / 脚本就绪 / 合成完成"""
    queue = _ep_subscribe(ep_id)

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            _ep_unsubscribe(ep_id, queue)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/sse/project/{proj_id}")
async def sse_project(proj_id: str, request: Request):
    """项目级 SSE：角色图片生成完成等"""
    queue = _proj_subscribe(proj_id)

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            _proj_unsubscribe(proj_id, queue)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.1.0"}
