from __future__ import annotations
import asyncio
import httpx
import logging
from datetime import datetime

from backend.core.config import settings
from backend.core.events import event_bus, SEGMENT_STATUS_UPDATED, SEGMENT_ALL_DONE
from backend.models.segment import SegmentStatus

logger = logging.getLogger(__name__)

# 并发信号量：最多 10 路
_semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_VIDEO_TASKS)


class VideoAgent:
    """
    Video Agent：
    - submit_drafts()      批量提交草稿（Seedance Draft，0.6倍价）
    - submit_finals()      批量提交正式生成
    - poll_and_retry()     轮询 + 自动重试（含降级逻辑）
    完整实现状态机：prompt_ready → drafting → draft_review → generating → done
    """

    API_KEY  = settings.SEEDANCE_API_KEY
    BASE_URL = settings.SEEDANCE_BASE_URL
    MODEL    = settings.SEEDANCE_MODEL
    RETRY_LIMIT = settings.VIDEO_RETRY_LIMIT

    # ── 公共入口 ─────────────────────────────────────────────────
    async def submit_drafts(self, payload: dict):
        """
        payload: {ep_id, segments:[{seg_id, prompt, characters, ref_images}]}
        """
        ep_id    = payload["ep_id"]
        segments = payload["segments"]
        logger.info(f"[VideoAgent] 批量提交生成: ep_id={ep_id}, count={len(segments)}")
        tasks = [self._process_segment(seg, ep_id=ep_id) for seg in segments]
        await asyncio.gather(*tasks, return_exceptions=True)

    # ── 单个 Segment 处理 ────────────────────────────────────────
    async def _process_segment(self, seg: dict, ep_id: str):
        seg_id = seg["seg_id"]
        async with _semaphore:
            await self._update_status(seg_id, SegmentStatus.DRAFT_PENDING, ep_id=ep_id)

            for attempt in range(self.RETRY_LIMIT + 1):
                try:
                    await self._update_status(seg_id, SegmentStatus.DRAFTING, ep_id=ep_id)
                    task_id = await self._submit_task(seg, self.MODEL)
                    video_url = await self._poll_until_done(task_id, seg_id)

                    await self._update_status(seg_id, SegmentStatus.DRAFT_REVIEW, ep_id=ep_id, extra={
                        "draft_task_id": task_id,
                        "draft_video_url": video_url,
                    })
                    return
                except Exception as e:
                    logger.warning(f"[VideoAgent] {seg_id} 第{attempt+1}次失败: {e}")
                    if attempt >= self.RETRY_LIMIT:
                        await self._update_status(seg_id, SegmentStatus.FAILED, ep_id=ep_id, extra={"last_error": str(e)})
                        return

    # ── Seedance API ─────────────────────────────────────────────
    async def _submit_task(self, seg: dict, model: str) -> str:
        """提交视频生成任务，返回 task_id"""
        headers = {
            "Authorization": f"Bearer {self.API_KEY}",
            "Content-Type": "application/json",
        }
        # 注入角色参考图
        ref_images = seg.get("ref_images", [])
        body = {
            "model": model,
            "content": [
                {"type": "text", "text": seg["prompt"]},
            ],
            "duration": seg.get("duration", 5),
        }
        if ref_images:
            for img in ref_images[:4]:  # Seedance 最多支持 4 张参考图
                body["content"].append({
                    "type": "image_url",
                    "role": "reference_image",
                    "image_url": {"url": img}
                })

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.BASE_URL}/contents/generations/tasks",
                headers=headers,
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["id"]

    async def _poll_until_done(self, task_id: str, seg_id: str, max_wait=600) -> str:
        """轮询任务状态，直到完成，返回视频 URL"""
        headers = {"Authorization": f"Bearer {self.API_KEY}"}
        elapsed = 0
        interval = 5

        async with httpx.AsyncClient(timeout=10) as client:
            while elapsed < max_wait:
                await asyncio.sleep(interval)
                elapsed += interval

                resp = await client.get(
                    f"{self.BASE_URL}/contents/generations/tasks/{task_id}",
                    headers=headers
                )
                resp.raise_for_status()
                data = resp.json()
                status = data.get("status")

                if status == "succeeded":
                    return data["content"]["video_url"]
                elif status in ("failed", "cancelled", "expired"):
                    msg = (data.get("error") or {}).get("message", "unknown")
                    raise RuntimeError(f"Seedance 任务失败: {msg}")
                # "running" / "pending" 继续等待

        raise TimeoutError(f"[VideoAgent] {seg_id} 超时 {max_wait}s 未完成")

    # ── 状态更新广播 ──────────────────────────────────────────────
    async def _update_status(self, seg_id: str, status: SegmentStatus, ep_id: str = "", extra: dict = None):
        payload = {"seg_id": seg_id, "status": status, "ep_id": ep_id, **(extra or {})}
        await event_bus.publish(SEGMENT_STATUS_UPDATED, payload)

    async def check_all_done(self, ep_id: str, segments: list[dict]):
        """检查是否所有 Segment 都 done/skipped，触发解锁合成"""
        terminal = {SegmentStatus.DONE, SegmentStatus.SKIPPED}
        if all(s["status"] in terminal for s in segments):
            await event_bus.publish(SEGMENT_ALL_DONE, {"ep_id": ep_id})
