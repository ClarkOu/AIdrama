from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import uuid
from datetime import datetime

from backend.core.database import get_db
from backend.core.events import event_bus, SCRIPT_GENERATE_REQUESTED, SCRIPT_EDITED
from backend.models.episode import Episode
from backend.models.project import Project
from backend.models.character import Character
from backend.models.segment import Segment

router = APIRouter(prefix="/episodes", tags=["episodes"])


class EpisodeCreate(BaseModel):
    project_id: str
    ep_number: int
    outline: str


class ScriptEditRequest(BaseModel):
    new_script_text: str


class EpisodeBatchCreate(BaseModel):
    outlines: list[dict]   # [{"ep": 1, "outline": "..."}, ...]


@router.post("/", status_code=201)
def create_episode(body: EpisodeCreate, db: Session = Depends(get_db)):
    ep = Episode(
        ep_id=f"ep_{uuid.uuid4().hex[:8]}",
        project_id=body.project_id,
        ep_number=body.ep_number,
        outline=body.outline,
        script_version=0,
        script_locked=False,
        created_at=datetime.utcnow().isoformat(),
        updated_at=datetime.utcnow().isoformat(),
    )
    db.add(ep)
    db.commit()
    db.refresh(ep)
    return ep


@router.post("/project/{project_id}/batch", status_code=201)
def batch_create_episodes(project_id: str, body: EpisodeBatchCreate, db: Session = Depends(get_db)):
    """根据大纲列表批量创建分集（用户确认大纲后调用）"""
    now = datetime.utcnow().isoformat()
    created = []
    for item in body.outlines:
        ep_number = int(item.get("ep", 1))
        ep_id     = f"ep_{uuid.uuid4().hex[:8]}"
        ep = Episode(
            ep_id       = ep_id,
            project_id  = project_id,
            ep_number   = ep_number,
            outline     = item.get("outline", ""),
            script_version = 0,
            script_locked  = False,
            created_at  = now,
            updated_at  = now,
        )
        db.add(ep)
        created.append(ep)
    db.commit()
    return [{"ep_id": e.ep_id, "ep_number": e.ep_number, "outline": e.outline} for e in created]


@router.get("/project/{project_id}")
def list_episodes(project_id: str, db: Session = Depends(get_db)):
    return db.query(Episode).filter(Episode.project_id == project_id).order_by(Episode.ep_number).all()


@router.get("/{ep_id}")
def get_episode(ep_id: str, db: Session = Depends(get_db)):
    ep = db.query(Episode).filter(Episode.ep_id == ep_id).first()
    if not ep:
        raise HTTPException(404, "分集不存在")
    return ep


@router.post("/{ep_id}/generate-script")
async def generate_script(ep_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """触发 Script Agent 生成剧本+分镜"""
    ep = db.query(Episode).filter(Episode.ep_id == ep_id).first()
    if not ep:
        raise HTTPException(404, "分集不存在")
    if ep.script_locked:
        raise HTTPException(400, "剧本已锁定，无法重新生成")

    proj = db.query(Project).filter(Project.id == ep.project_id).first()
    chars = db.query(Character).filter(Character.project_id == ep.project_id).all()

    # 查询本集之前所有集数的完整剧本（按集号升序）
    prev_eps = (
        db.query(Episode)
        .filter(
            Episode.project_id == ep.project_id,
            Episode.ep_number < ep.ep_number,
            Episode.script_text.isnot(None),
            Episode.script_text != "",
        )
        .order_by(Episode.ep_number)
        .all()
    )
    prev_episodes = [
        {"ep_number": p.ep_number, "outline": p.outline, "script_text": p.script_text}
        for p in prev_eps
    ]

    payload = {
        "ep_id": ep.ep_id,
        "ep_number": ep.ep_number,
        "project_id": ep.project_id,
        "outline": ep.outline,
        "title": proj.title if proj else "",
        "tone": proj.tone if proj else "",
        "visual_style": proj.world_config.get("visual_style", "") if proj else "",
        "characters": [{"name": c.name, "fixed_desc": c.fixed_desc} for c in chars],
        "prev_episodes": prev_episodes,
    }

    async def _publish():
        await event_bus.publish(SCRIPT_GENERATE_REQUESTED, payload)

    background_tasks.add_task(_publish)
    return {"message": "脚本生成任务已提交"}


@router.patch("/{ep_id}/script")
async def edit_script(ep_id: str, body: ScriptEditRequest, db: Session = Depends(get_db)):
    """编辑剧本文本，触发 diff 分析"""
    ep = db.query(Episode).filter(Episode.ep_id == ep_id).first()
    if not ep:
        raise HTTPException(404, "分集不存在")
    if ep.script_locked:
        raise HTTPException(400, "剧本已锁定")

    segments = db.query(Segment).filter(Segment.ep_id == ep_id).all()
    old_text = ep.script_text or ""

    await event_bus.publish(SCRIPT_EDITED, {
        "ep_id": ep_id,
        "old_script_text": old_text,
        "new_script_text": body.new_script_text,
        "segments": [
            {"act": s.act, "scene_desc": s.scene_desc, "dialogue": s.dialogue, "id": s.id}
            for s in segments
        ],
    })

    ep.script_text = body.new_script_text
    ep.script_version = (ep.script_version or 0) + 1
    ep.updated_at = datetime.utcnow().isoformat()
    db.commit()
    return {"message": "剧本更新成功，diff 分析已触发", "script_version": ep.script_version}
