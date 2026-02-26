from __future__ import annotations
import asyncio
from collections import defaultdict
from typing import Callable, Any
import logging

logger = logging.getLogger(__name__)


class EventBus:
    """
    轻量内存事件总线。
    支持 publish / subscribe / unsubscribe。
    所有 handler 均为 async 函数。
    """

    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: Callable):
        self._subscribers[event_type].append(handler)
        logger.debug(f"[EventBus] subscribed: {event_type} -> {handler.__name__}")

    def unsubscribe(self, event_type: str, handler: Callable):
        self._subscribers[event_type].remove(handler)

    async def publish(self, event_type: str, payload: Any = None):
        logger.info(f"[EventBus] publish: {event_type} | payload_keys={list(payload.keys()) if isinstance(payload, dict) else type(payload).__name__}")
        handlers = self._subscribers.get(event_type, [])
        tasks = [asyncio.create_task(h(payload)) for h in handlers]
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r, h in zip(results, handlers):
                if isinstance(r, BaseException):
                    logger.error(f"[EventBus] handler {h.__name__} 抛出异常: {r}", exc_info=r)


# 全局单例
event_bus = EventBus()

# ── 事件类型常量 ─────────────────────────────────────────────
# 角色/图片
CHARACTER_IMAGE_REQUESTED  = "character.image.requested"
CHARACTER_IMAGE_DONE       = "character.image.done"

# 脚本
SCRIPT_GENERATE_REQUESTED  = "script.generate.requested"
SCRIPT_SEGMENTS_READY      = "script.segments.ready"
SCRIPT_EDITED              = "script.edited"
SCRIPT_STREAM_CHUNK        = "script.stream.chunk"   # LLM 流式输出 chunk

# 视频分镜
SEGMENT_DRAFT_SUBMIT       = "segment.draft.submit"
SEGMENT_STATUS_UPDATED     = "segment.status.updated"
SEGMENT_ALL_DONE           = "segment.all.done"

# 合成
COMPOSE_REQUESTED          = "compose.requested"
COMPOSE_DONE               = "compose.done"

# 项目大纲自动生成
OUTLINES_GENERATE_REQUESTED = "outlines.generate.requested"
OUTLINES_READY              = "outlines.ready"
OUTLINE_STREAM_CHUNK        = "outline.stream.chunk"   # 大纲 LLM 流式 chunk
