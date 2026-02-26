from sqlalchemy import Column, String, Boolean, JSON, Text
from sqlalchemy.orm import relationship
from backend.core.database import Base


class Character(Base):
    """角色数据模型"""
    __tablename__ = "characters"

    id = Column(String, primary_key=True)          # 如 "char_001"
    project_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)           # 全系统唯一 Key
    aliases = Column(JSON, default=list)            # ["男主", "主角"]
    fixed_desc = Column(Text, nullable=False)       # "25岁黑发男，方形下颌..."
    ref_images = Column(JSON, default=list)         # 图片列表，结构见设计文档 3.1
    voice_config = Column(JSON, default=dict)       # {"type": "sample", "sample_path": "..."}
    created_at = Column(String)
    updated_at = Column(String)
