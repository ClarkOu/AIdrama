from sqlalchemy import Column, String, Integer, Text, Boolean, JSON
from backend.core.database import Base


class Episode(Base):
    """分集数据模型"""
    __tablename__ = "episodes"

    ep_id = Column(String, primary_key=True)        # 如 "ep_001"
    project_id = Column(String, nullable=False, index=True)
    ep_number = Column(Integer, nullable=False)
    outline = Column(Text)                          # 本集梗概
    script_text = Column(Text)                      # 完整剧本原文（供人阅读）
    script_version = Column(Integer, default=0)
    script_locked = Column(Boolean, default=False)  # True=禁止编辑
    created_at = Column(String)
    updated_at = Column(String)
