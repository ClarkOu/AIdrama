from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import uuid
from datetime import datetime

from backend.core.database import get_db
from backend.core.events import event_bus, SEGMENT_DRAFT_SUBMIT, COMPOSE_REQUESTED
from backend.models.segment import Segment, SegmentStatus
from backend.models.episode import Episode
from backend.models.character import Character

router = APIRouter(prefix="/segments", tags=["segments"])


class SegmentUpdate(BaseModel):
    prompt: Optional[str] = None
    dialogue: Optional[str] = None
    scene_desc: Optional[str] = None
    characters: Optional[list[str]] = None
    order: Optional[int] = None


class ReorderRequest(BaseModel):
    ordered_ids: list[str]  # 按新顺序排列的 seg_id 列表


@router.get("/episode/{ep_id}")
def list_segments(ep_id: str, db: Session = Depends(get_db)):
    return db.query(Segment).filter(Segment.ep_id == ep_id).order_by(Segment.order).all()


@router.get("/{seg_id}")
def get_segment(seg_id: str, db: Session = Depends(get_db)):
    seg = db.query(Segment).filter(Segment.id == seg_id).first()
    if not seg:
        raise HTTPException(404, "分镜不存在")
    return seg


@router.patch("/{seg_id}")
def update_segment(seg_id: str, body: SegmentUpdate, db: Session = Depends(get_db)):
    """直接编辑分镜内容，0 次 API 调用"""
    seg = db.query(Segment).filter(Segment.id == seg_id).first()
    if not seg:
        raise HTTPException(404, "分镜不存在")

    updates = body.model_dump(exclude_none=True)

    # 如果修改了 prompt 且已有视频，标记 prompt_dirty
    if "prompt" in updates and seg.final_video_url:
        seg.prompt_dirty = True
        seg.prompt_version = (seg.prompt_version or 1) + 1

    for field, value in updates.items():
        setattr(seg, field, value)

    seg.updated_at = datetime.utcnow().isoformat()
    db.commit()
    db.refresh(seg)
    return seg


@router.post("/episode/{ep_id}/reorder")
def reorder_segments(ep_id: str, body: ReorderRequest, db: Session = Depends(get_db)):
    """拖拽排序：按新顺序更新所有 Segment.order"""
    for new_order, seg_id in enumerate(body.ordered_ids, start=1):
        db.query(Segment).filter(Segment.id == seg_id, Segment.ep_id == ep_id).update(
            {"order": new_order, "updated_at": datetime.utcnow().isoformat()}
        )
    db.commit()
    return {"message": "排序已更新"}


@router.post("/episode/{ep_id}/submit-drafts")
async def submit_drafts(ep_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """批量提交草稿生成（触发 Video Agent）"""
    ep = db.query(Episode).filter(Episode.ep_id == ep_id).first()
    if not ep:
        raise HTTPException(404, "分集不存在")

    segments = db.query(Segment).filter(
        Segment.ep_id == ep_id,
        Segment.status == SegmentStatus.PROMPT_READY
    ).all()

    if not segments:
        raise HTTPException(400, "没有待提交的分镜（状态需为 prompt_ready）")

    # 注入角色参考图
    chars_map = {
        c.name: c for c in db.query(Character).filter(Character.project_id == ep.project_id).all()
    }

    seg_payloads = []
    for seg in segments:
        ref_images = []
        for char_name in (seg.characters or []):
            char = chars_map.get(char_name)
            if char and char.ref_images:
                # 主图排在最前，收集该角色全部图片
                sorted_imgs = sorted(char.ref_images, key=lambda x: (0 if x.get("is_primary") else 1))
                for img in sorted_imgs:
                    if len(ref_images) >= 4:
                        break
                    ref_images.append(img["url"])
        seg_payloads.append({
            "seg_id": seg.id,
            "prompt": seg.prompt,
            "characters": seg.characters,
            "ref_images": ref_images,
            "duration": seg.duration or 5,
        })

    payload = {
        "ep_id": ep_id,
        "segments": seg_payloads,
    }
    async def _publish(): await event_bus.publish(SEGMENT_DRAFT_SUBMIT, payload)
    background_tasks.add_task(_publish)
    return {"message": f"已提交 {len(seg_payloads)} 个分镜生成任务"}


@router.post("/{seg_id}/submit-draft")
async def submit_single_draft(seg_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """单个分镜提交草稿生成"""
    seg = db.query(Segment).filter(Segment.id == seg_id).first()
    if not seg:
        raise HTTPException(404, "分镜不存在")
    if seg.status != SegmentStatus.PROMPT_READY:
        raise HTTPException(400, f"当前状态 {seg.status} 不可提交草稿，需为 prompt_ready")

    ep = db.query(Episode).filter(Episode.ep_id == seg.ep_id).first()
    chars_map = {
        c.name: c for c in db.query(Character).filter(Character.project_id == ep.project_id).all()
    } if ep else {}

    ref_images = []
    for char_name in (seg.characters or []):
        char = chars_map.get(char_name)
        if char and char.ref_images:
            # 主图排在最前，收集该角色全部图片
            sorted_imgs = sorted(char.ref_images, key=lambda x: (0 if x.get("is_primary") else 1))
            for img in sorted_imgs:
                if len(ref_images) >= 4:
                    break
                ref_images.append(img["url"])

    payload = {
        "ep_id": seg.ep_id,
        "segments": [{"seg_id": seg.id, "prompt": seg.prompt, "characters": seg.characters, "ref_images": ref_images, "duration": seg.duration or 5}],
    }
    async def _publish(): await event_bus.publish(SEGMENT_DRAFT_SUBMIT, payload)
    background_tasks.add_task(_publish)
    return {"message": "已提交单个分镜生成任务"}


@router.post("/{seg_id}/approve-draft")
def approve_draft(seg_id: str, db: Session = Depends(get_db)):
    """审核通过 → 直接 done，可合成"""
    seg = db.query(Segment).filter(Segment.id == seg_id).first()
    if not seg:
        raise HTTPException(404, "分镜不存在")
    if seg.status != SegmentStatus.DRAFT_REVIEW:
        raise HTTPException(400, f"当前状态 {seg.status} 不可通过审核")
    seg.status = SegmentStatus.DONE
    seg.updated_at = datetime.utcnow().isoformat()
    db.commit()
    return {"message": "已通过，可合成"}


@router.post("/{seg_id}/reject-draft")
def reject_draft(seg_id: str, db: Session = Depends(get_db)):
    """不通过草稿 → 回到 prompt_ready，可修改 prompt"""
    seg = db.query(Segment).filter(Segment.id == seg_id).first()
    if not seg:
        raise HTTPException(404, "分镜不存在")
    seg.status = SegmentStatus.PROMPT_READY
    seg.draft_task_id = None
    seg.draft_video_url = None
    seg.updated_at = datetime.utcnow().isoformat()
    db.commit()
    return {"message": "草稿已退回，请修改 prompt 后重新提交"}


@router.post("/{seg_id}/skip")
def skip_segment(seg_id: str, db: Session = Depends(get_db)):
    """跳过该分镜，用占位画面填充"""
    seg = db.query(Segment).filter(Segment.id == seg_id).first()
    if not seg:
        raise HTTPException(404, "分镜不存在")
    seg.status = SegmentStatus.SKIPPED
    seg.updated_at = datetime.utcnow().isoformat()
    db.commit()
    return {"message": "已跳过"}


@router.post("/episode/{ep_id}/compose")
async def compose_episode(ep_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """合成整集 MP4（需要所有分镜 done 或 skipped）"""
    ep = db.query(Episode).filter(Episode.ep_id == ep_id).first()
    if not ep:
        raise HTTPException(404, "分集不存在")

    segments = db.query(Segment).filter(Segment.ep_id == ep_id).order_by(Segment.order).all()
    terminal = {SegmentStatus.DONE, SegmentStatus.SKIPPED}
    not_ready = [s.id for s in segments if s.status not in terminal]

    if not_ready:
        raise HTTPException(400, f"以下分镜尚未完成: {not_ready}")

    from backend.models.project import Project
    proj = db.query(Project).filter(Project.id == ep.project_id).first()

    seg_list = [
        {"seg_id": s.id, "order": s.order, "final_video_url": s.draft_video_url}
        for s in segments
    ]
    compose_payload = {
        "ep_id": ep_id,
        "project_title": proj.title if proj else "episode",
        "ep_number": ep.ep_number,
        "segments": seg_list,
    }
    async def _publish(): await event_bus.publish(COMPOSE_REQUESTED, compose_payload)
    background_tasks.add_task(_publish)
    return {"message": "合成任务已提交"}
