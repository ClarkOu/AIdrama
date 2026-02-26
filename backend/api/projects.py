from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import uuid
from datetime import datetime

from backend.core.database import get_db
from backend.core.events import event_bus, OUTLINES_GENERATE_REQUESTED
from backend.models.project import Project

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    title: str
    genre: str = ""
    tone: str = ""
    story_premise: str = ""     # 故事主线
    total_episodes: int = 6
    world_config: dict = {}
    episode_outlines: list[dict] = []


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    genre: Optional[str] = None
    tone: Optional[str] = None
    total_episodes: Optional[int] = None
    world_config: Optional[dict] = None
    episode_outlines: Optional[list[dict]] = None


@router.post("/", status_code=201)
async def create_project(body: ProjectCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    proj = Project(
        id=f"proj_{uuid.uuid4().hex[:8]}",
        title=body.title,
        genre=body.genre,
        tone=body.tone,
        story_premise=body.story_premise,
        total_episodes=body.total_episodes,
        world_config=body.world_config,
        episode_outlines=body.episode_outlines,
        created_at=datetime.utcnow().isoformat(),
        updated_at=datetime.utcnow().isoformat(),
    )
    db.add(proj)
    db.commit()
    db.refresh(proj)

    # 如果填了故事主线，在后台异步触发大纲生成（不阻塞 HTTP 响应）
    if body.story_premise.strip():
        payload = {
            "project_id": proj.id,
            "title": proj.title,
            "genre": proj.genre,
            "tone": proj.tone,
            "story_premise": proj.story_premise,
            "total_episodes": proj.total_episodes,
        }
        background_tasks.add_task(event_bus.publish, OUTLINES_GENERATE_REQUESTED, payload)

    return proj


@router.get("/")
def list_projects(db: Session = Depends(get_db)):
    return db.query(Project).order_by(Project.created_at.desc()).all()


@router.get("/{project_id}")
def get_project(project_id: str, db: Session = Depends(get_db)):
    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        raise HTTPException(404, "项目不存在")
    return proj


@router.patch("/{project_id}")
def update_project(project_id: str, body: ProjectUpdate, db: Session = Depends(get_db)):
    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        raise HTTPException(404, "项目不存在")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(proj, field, value)
    proj.updated_at = datetime.utcnow().isoformat()
    db.commit()
    db.refresh(proj)
    return proj


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, db: Session = Depends(get_db)):
    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        raise HTTPException(404, "项目不存在")
    db.delete(proj)
    db.commit()
