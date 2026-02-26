from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import uuid
import aiofiles
import os
from pathlib import Path
from datetime import datetime

from backend.core.database import get_db
from backend.core.config import settings
from backend.core.events import event_bus, CHARACTER_IMAGE_REQUESTED
from backend.models.character import Character

router = APIRouter(prefix="/characters", tags=["characters"])
CHARS_DIR = Path(settings.ASSETS_DIR) / "chars"
CHARS_DIR.mkdir(parents=True, exist_ok=True)


class CharacterCreate(BaseModel):
    project_id: str
    name: str
    fixed_desc: str
    aliases: list[str] = []
    voice_config: dict = {}


class CharacterUpdate(BaseModel):
    name: Optional[str] = None
    fixed_desc: Optional[str] = None
    aliases: Optional[list[str]] = None
    voice_config: Optional[dict] = None


class ImageGenRequest(BaseModel):
    mode: str          # "t2i" | "i2i"
    prompt: str = ""
    ref_image_path: str = ""


@router.post("/", status_code=201)
def create_character(body: CharacterCreate, db: Session = Depends(get_db)):
    char = Character(
        id=f"char_{uuid.uuid4().hex[:8]}",
        project_id=body.project_id,
        name=body.name,
        fixed_desc=body.fixed_desc,
        aliases=body.aliases,
        voice_config=body.voice_config,
        ref_images=[],
        created_at=datetime.utcnow().isoformat(),
        updated_at=datetime.utcnow().isoformat(),
    )
    db.add(char)
    db.commit()
    db.refresh(char)
    return char


@router.get("/project/{project_id}")
def list_characters(project_id: str, db: Session = Depends(get_db)):
    return db.query(Character).filter(Character.project_id == project_id).all()


@router.get("/{char_id}")
def get_character(char_id: str, db: Session = Depends(get_db)):
    char = db.query(Character).filter(Character.id == char_id).first()
    if not char:
        raise HTTPException(404, "角色不存在")
    return char


@router.patch("/{char_id}")
def update_character(char_id: str, body: CharacterUpdate, db: Session = Depends(get_db)):
    char = db.query(Character).filter(Character.id == char_id).first()
    if not char:
        raise HTTPException(404, "角色不存在")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(char, field, value)
    char.updated_at = datetime.utcnow().isoformat()
    db.commit()
    db.refresh(char)
    return char


@router.delete("/{char_id}", status_code=204)
def delete_character(char_id: str, db: Session = Depends(get_db)):
    char = db.query(Character).filter(Character.id == char_id).first()
    if not char:
        raise HTTPException(404, "角色不存在")
    db.delete(char)
    db.commit()


@router.post("/{char_id}/upload-image")
async def upload_image(char_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """方式 C：本地上传图片"""
    char = db.query(Character).filter(Character.id == char_id).first()
    if not char:
        raise HTTPException(404, "角色不存在")

    ext = os.path.splitext(file.filename)[1] or ".jpg"
    filename = f"{char_id}_upload_{uuid.uuid4().hex[:8]}{ext}"
    save_path = str(CHARS_DIR / filename)

    async with aiofiles.open(save_path, "wb") as f:
        await f.write(await file.read())

    http_url = f"{settings.BACKEND_URL}/assets/chars/{filename}"
    new_image = {
        "url": http_url,
        "source": "upload",
        "angle": "unknown",
        "gen_prompt": "",
        "is_primary": len(char.ref_images) == 0,  # 第一张自动设为主图
    }
    images = list(char.ref_images or [])
    images.append(new_image)
    char.ref_images = images
    char.updated_at = datetime.utcnow().isoformat()
    db.commit()
    return {"url": http_url, "message": "上传成功"}


@router.post("/{char_id}/generate-image")
async def generate_image(char_id: str, body: ImageGenRequest, db: Session = Depends(get_db)):
    """方式 A/B：触发 AI 生图（异步，结果通过 SSE 推送）"""
    char = db.query(Character).filter(Character.id == char_id).first()
    if not char:
        raise HTTPException(404, "角色不存在")

    await event_bus.publish(CHARACTER_IMAGE_REQUESTED, {
        "char_id": char_id,
        "char_name": char.name,
        "project_id": char.project_id,
        "mode": body.mode,
        "prompt": body.prompt or char.fixed_desc,
        "ref_image_path": body.ref_image_path,
    })
    return {"message": "生图任务已提交，请等待结果推送"}


@router.post("/{char_id}/images/{index}/set-primary", status_code=200)
def set_primary_image(char_id: str, index: int, db: Session = Depends(get_db)):
    """将指定索引的图片设为主图"""
    char = db.query(Character).filter(Character.id == char_id).first()
    if not char:
        raise HTTPException(404, "角色不存在")
    images = list(char.ref_images or [])
    if index < 0 or index >= len(images):
        raise HTTPException(400, f"图片索引 {index} 超出范围")
    for i, img in enumerate(images):
        img["is_primary"] = (i == index)
    char.ref_images = images
    char.updated_at = datetime.utcnow().isoformat()
    db.commit()
    db.refresh(char)
    return char


@router.delete("/{char_id}/images/{index}", status_code=200)
def delete_image(char_id: str, index: int, db: Session = Depends(get_db)):
    """删除指定索引的图片。若删除的是主图则将下一张置为主图"""
    char = db.query(Character).filter(Character.id == char_id).first()
    if not char:
        raise HTTPException(404, "角色不存在")
    images = list(char.ref_images or [])
    if index < 0 or index >= len(images):
        raise HTTPException(400, f"图片索引 {index} 超出范围")
    was_primary = images[index].get("is_primary", False)
    images.pop(index)
    # 若删除的是主图，且还有剩余图片，则将第 0 张置为主图
    if was_primary and images:
        images[0]["is_primary"] = True
    char.ref_images = images
    char.updated_at = datetime.utcnow().isoformat()
    db.commit()
    db.refresh(char)
    return char
