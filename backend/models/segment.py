from sqlalchemy import Column, String, Integer, Text, Boolean, JSON, Float
from backend.core.database import Base
import enum


class SegmentStatus(str, enum.Enum):
    PROMPT_READY   = "prompt_ready"    # 默认，等待提交生成
    DRAFT_PENDING  = "draft_pending"   # 已提交，等待队列
    DRAFTING       = "drafting"        # Seedance 生成中
    DRAFT_REVIEW   = "draft_review"    # 视频完成，等待用户审核
    DONE           = "done"            # 用户通过，可合成
    FAILED         = "failed"          # 多次重试后仍失败
    SKIPPED        = "skipped"         # 用户手动跳过


class Segment(Base):
    """分镜数据模型（含完整状态机）"""
    __tablename__ = "segments"

    id = Column(String, primary_key=True)           # 如 "seg_001_01"
    ep_id = Column(String, nullable=False, index=True)
    order = Column(Integer, nullable=False)         # 排序序号（可拖拽调整）
    act = Column(Integer, nullable=False)           # 第几幕（1-5）

    scene_desc = Column(Text)                       # 场景描述（中文，供人读）
    characters = Column(JSON, default=list)         # ["林战", "陈总"]
    dialogue = Column(Text)                         # 对白原文
    prompt = Column(Text)                           # 视频生成提示词
    prompt_dirty = Column(Boolean, default=False)   # prompt 被修改但视频未重生

    prompt_version = Column(Integer, default=1)

    # 状态机
    status = Column(String, default=SegmentStatus.PROMPT_READY)

    # 视频
    duration = Column(Integer, default=5)          # 视频时长（秒），由 LLM 决定
    draft_task_id = Column(String)
    draft_video_url = Column(String)

    retry_count = Column(Integer, default=0)
    last_error = Column(Text)

    created_at = Column(String)
    updated_at = Column(String)
