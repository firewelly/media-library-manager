from typing import List, Optional, Any
from pydantic import BaseModel
from datetime import datetime

# --- Actor Schemas ---
class ActorBase(BaseModel):
    name: str
    avatar_path: Optional[str] = None
    info_url: Optional[str] = None

class ActorCreate(ActorBase):
    pass

class Actor(ActorBase):
    id: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True

# --- Video Schemas ---
class VideoBase(BaseModel):
    file_path: str
    file_name: str
    file_size: Optional[int] = None
    md5_hash: Optional[str] = None
    file_hash: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    genre: Optional[str] = None
    year: Optional[int] = None
    rating: Optional[float] = None
    stars: Optional[int] = 0
    tags: Optional[str] = None
    nas_path: Optional[str] = None
    is_nas_online: Optional[bool] = True
    thumbnail_path: Optional[str] = None
    duration: Optional[int] = None
    resolution: Optional[str] = None
    source_folder: Optional[str] = None
    javdb_code: Optional[str] = None

class VideoCreate(VideoBase):
    pass

class Video(VideoBase):
    id: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    actors: List[Actor] = []
    
    # We might not want to return full thumbnail blob in list views
    # thumbnail_data: Optional[bytes] = None 

    class Config:
        orm_mode = True

# --- Folder Schemas ---
class FolderBase(BaseModel):
    folder_path: str
    folder_type: Optional[str] = 'local'
    is_active: Optional[bool] = True

class FolderCreate(FolderBase):
    pass

class Folder(FolderBase):
    id: int
    created_at: Optional[datetime]

    class Config:
        orm_mode = True

# --- Tag Schemas ---
class TagBase(BaseModel):
    tag_name: str

class TagCreate(TagBase):
    pass

class Tag(TagBase):
    id: int
    created_at: Optional[datetime]

    class Config:
        orm_mode = True
