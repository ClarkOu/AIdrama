from sqlalchemy import Column, String, Integer, JSON, Text, Boolean
from backend.core.database import Base


class Project(Base):
    """项目数据模型"""
    __tablename__ = "projects"

    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    genre = Column(String)
    tone = Column(String)
    story_premise = Column(Text, default="")    # 故事主线（用于自动生成集数梗概）
    total_episodes = Column(Integer, default=6)
    world_config = Column(JSON, default=dict)
    episode_outlines = Column(JSON, default=list)
    created_at = Column(String)
    updated_at = Column(String)
