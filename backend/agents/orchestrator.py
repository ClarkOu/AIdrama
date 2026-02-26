from __future__ import annotations
import logging
import uuid
from datetime import datetime
from backend.core.events import (
    event_bus,
    CHARACTER_IMAGE_REQUESTED, CHARACTER_IMAGE_DONE,
    SCRIPT_GENERATE_REQUESTED, SCRIPT_SEGMENTS_READY,
    SCRIPT_EDITED,
    SEGMENT_DRAFT_SUBMIT, SEGMENT_STATUS_UPDATED, SEGMENT_ALL_DONE,
    COMPOSE_REQUESTED, COMPOSE_DONE,
    OUTLINES_GENERATE_REQUESTED, OUTLINES_READY,
)
from backend.core.database import SessionLocal

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    编排 Agent。
    负责订阅所有 UI 事件，路由到对应 Agent，管理任务依赖。
    不直接调用任何外部 API。
    """

    def __init__(self):
        self._register()

    def _register(self):
        # 图片
        event_bus.subscribe(CHARACTER_IMAGE_REQUESTED, self._on_image_requested)
        event_bus.subscribe(CHARACTER_IMAGE_DONE,      self._on_image_done)
        # 脚本
        event_bus.subscribe(SCRIPT_GENERATE_REQUESTED, self._on_script_requested)
        event_bus.subscribe(SCRIPT_EDITED,             self._on_script_edited)
        event_bus.subscribe(SCRIPT_SEGMENTS_READY,     self._on_segments_ready)
        # 视频
        event_bus.subscribe(SEGMENT_DRAFT_SUBMIT,   self._on_draft_submit)
        event_bus.subscribe(SEGMENT_STATUS_UPDATED, self._on_segment_updated)
        event_bus.subscribe(SEGMENT_ALL_DONE,       self._on_all_done)
        # 合成
        event_bus.subscribe(COMPOSE_REQUESTED, self._on_compose_requested)
        event_bus.subscribe(COMPOSE_DONE,      self._on_compose_done)
        # 大纲批量生成
        event_bus.subscribe(OUTLINES_GENERATE_REQUESTED, self._on_outlines_requested)
        event_bus.subscribe(OUTLINES_READY,               self._on_outlines_ready)

    # ── 图片 ────────────────────────────────────────────────────
    async def _on_image_requested(self, payload: dict):
        from backend.agents.image_agent import ImageAgent
        agent = ImageAgent()
        await agent.handle(payload)

    async def _on_image_done(self, payload: dict):
        char_id = payload.get("char_id")
        logger.info(f"[Orchestrator] 角色图片完成: char_id={char_id}")
        # 将 AI 生成的图片保存到角色 ref_images
        if not char_id:
            return
        from backend.models.character import Character
        db = SessionLocal()
        try:
            char = db.query(Character).filter(Character.id == char_id).first()
            if char:
                new_image = {
                    "url": payload.get("url", ""),
                    "source": payload.get("source", "ai"),
                    "angle": "unknown",
                    "gen_prompt": payload.get("gen_prompt", ""),
                    "is_primary": payload.get("is_primary", False) or len(char.ref_images) == 0,
                }
                images = list(char.ref_images or [])
                # 若设为主图，先将其他图片 is_primary 置 False
                if new_image["is_primary"]:
                    for img in images:
                        img["is_primary"] = False
                images.append(new_image)
                char.ref_images = images
                char.updated_at = datetime.utcnow().isoformat()
                db.commit()
        finally:
            db.close()

    # ── 脚本 ────────────────────────────────────────────────────
    async def _on_script_requested(self, payload: dict):
        from backend.agents.script_agent import ScriptAgent
        agent = ScriptAgent()
        await agent.generate(payload)

    async def _on_script_edited(self, payload: dict):
        from backend.agents.script_agent import ScriptAgent
        agent = ScriptAgent()
        await agent.handle_edit(payload)

    async def _on_segments_ready(self, payload: dict):
        """SCRIPT_SEGMENTS_READY 事件:将 LLM 返回的分镜写入数据库"""
        from backend.models.episode import Episode
        from backend.models.segment import Segment, SegmentStatus

        ep_id     = payload["ep_id"]
        script_text = payload.get("script_text", "")
        segs_data   = payload.get("segments", [])
        partial     = payload.get("partial", False)
        acts_regenned = payload.get("acts_regenned", [])

        db = SessionLocal()
        try:
            # 更新剧本文本
            ep = db.query(Episode).filter(Episode.ep_id == ep_id).first()
            if ep:
                ep.script_text    = script_text
                ep.script_version = (ep.script_version or 0) + 1
                ep.updated_at     = datetime.utcnow().isoformat()

            # 局部重生时只删除受影响的幕；全量生成时删除所有
            existing = db.query(Segment).filter(Segment.ep_id == ep_id)
            if partial and acts_regenned:
                existing = existing.filter(Segment.act.in_(acts_regenned))
            existing.delete(synchronize_session=False)

            # 写入新分镜
            now = datetime.utcnow().isoformat()
            for i, s in enumerate(segs_data, start=1):
                seg = Segment(
                    id          = f"seg_{ep_id}_{i:03d}",
                    ep_id       = ep_id,
                    order       = i,
                    act         = s.get("act", 1),
                    scene_desc  = s.get("scene_desc", ""),
                    characters  = s.get("characters", []),
                    dialogue    = s.get("dialogue") or "",
                    prompt      = s.get("prompt", ""),
                    prompt_dirty= False,
                    duration    = max(4, min(12, int(s.get("duration") or 5))),
                    status      = SegmentStatus.PROMPT_READY,
                    created_at  = now,
                    updated_at  = now,
                )
                db.add(seg)

            db.commit()
            logger.info(f"[Orchestrator] 分镜写入完成: ep_id={ep_id}, count={len(segs_data)}")
        except Exception as e:
            db.rollback()
            logger.error(f"[Orchestrator] 分镜写入失败: {e}", exc_info=True)
        finally:
            db.close()

    # ── 视频 ────────────────────────────────────────────────────
    async def _on_draft_submit(self, payload: dict):
        from backend.agents.video_agent import VideoAgent
        agent = VideoAgent()
        await agent.submit_drafts(payload)

    async def _on_segment_updated(self, payload: dict):
        """将 VideoAgent 的状态变更写入数据库"""
        from backend.models.segment import Segment
        seg_id = payload.get("seg_id")
        status = payload.get("status")
        if not seg_id or not status:
            return
        db = SessionLocal()
        try:
            seg = db.query(Segment).filter(Segment.id == seg_id).first()
            if seg:
                seg.status = status
                for field in ("draft_task_id", "draft_video_url", "last_error"):
                    if field in payload:
                        setattr(seg, field, payload[field])
                seg.updated_at = datetime.utcnow().isoformat()
                db.commit()
                logger.info(f"[Orchestrator] Segment 状态写入: {seg_id} -> {status}")
        except Exception as e:
            db.rollback()
            logger.error(f"[Orchestrator] Segment 状态写入失败: {e}", exc_info=True)
        finally:
            db.close()

    async def _on_all_done(self, payload: dict):
        logger.info(f"[Orchestrator] 所有 Segment 完成，解锁合成: ep_id={payload.get('ep_id')}")

    # ── 大纲批量生成 ─────────────────────────────────────────────
    async def _on_outlines_requested(self, payload: dict):
        from backend.agents.script_agent import ScriptAgent
        agent = ScriptAgent()
        await agent.generate_outlines(payload)

    async def _on_outlines_ready(self, payload: dict):
        """OUTLINES_READY：大纲已生成，等待前端用户确认后再创建分集（不自动创建）"""
        logger.info(f"[Orchestrator] 大纲就绪: project_id={payload.get('project_id')}, count={len(payload.get('outlines', []))}")

    # ── 合成 ────────────────────────────────────────────────────
    async def _on_compose_requested(self, payload: dict):
        from backend.agents.compose_agent import ComposeAgent
        agent = ComposeAgent()
        await agent.compose(payload)

    async def _on_compose_done(self, payload: dict):
        logger.info(f"[Orchestrator] 合成完成: output={payload.get('output_path')}")


# 全局实例（应用启动时初始化）
orchestrator: Orchestrator | None = None


def init_orchestrator():
    global orchestrator
    orchestrator = Orchestrator()
    logger.info("[Orchestrator] 初始化完成，所有事件已注册")
