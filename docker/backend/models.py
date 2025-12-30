from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Float, Text, DateTime, LargeBinary, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

# Association table for Video-Actor many-to-many relationship
video_actors = Table(
    'video_actors',
    Base.metadata,
    Column('video_id', Integer, ForeignKey('videos.id', ondelete="CASCADE"), primary_key=True),
    Column('actor_id', Integer, ForeignKey('actors.id', ondelete="CASCADE"), primary_key=True)
)

class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    file_path = Column(String, unique=True, nullable=False, index=True)
    file_name = Column(String, nullable=False)
    file_size = Column(Integer)
    md5_hash = Column(String, index=True)
    file_hash = Column(String, index=True)  # Added based on utils/database.py
    title = Column(String, index=True)
    description = Column(Text)
    genre = Column(String)
    year = Column(Integer, index=True)
    rating = Column(Float)
    stars = Column(Integer, default=0, index=True)
    tags = Column(Text) # Comma separated tags
    nas_path = Column(String)
    is_nas_online = Column(Boolean, default=True)
    thumbnail_data = Column(LargeBinary)
    thumbnail_path = Column(String)
    duration = Column(Integer)
    resolution = Column(String)
    source_folder = Column(String) # Added based on utils/database.py
    javdb_code = Column(String) # Added based on utils/database.py
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    actors = relationship("Actor", secondary=video_actors, back_populates="videos")

class Folder(Base):
    __tablename__ = "folders"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    folder_path = Column(String, unique=True, nullable=False, index=True)
    folder_type = Column(String, default='local')
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tag_name = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Actor(Base):
    __tablename__ = "actors"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    avatar_path = Column(String)
    info_url = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    videos = relationship("Video", secondary=video_actors, back_populates="actors")
