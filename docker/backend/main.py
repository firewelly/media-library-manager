from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db, engine
import models, schemas
from fastapi.middleware.cors import CORSMiddleware

# Create tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Media Library API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Videos ---
@app.get("/videos/", response_model=List[schemas.Video])
def read_videos(
    skip: int = 0, 
    limit: int = 50, 
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(models.Video)
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (models.Video.title.ilike(search_pattern)) | 
            (models.Video.file_name.ilike(search_pattern)) |
            (models.Video.tags.ilike(search_pattern))
        )
    videos = query.offset(skip).limit(limit).all()
    return videos

@app.get("/videos/{video_id}", response_model=schemas.Video)
def read_video(video_id: int, db: Session = Depends(get_db)):
    video = db.query(models.Video).filter(models.Video.id == video_id).first()
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return video

@app.post("/videos/", response_model=schemas.Video)
def create_video(video: schemas.VideoCreate, db: Session = Depends(get_db)):
    db_video = models.Video(**video.dict())
    db.add(db_video)
    db.commit()
    db.refresh(db_video)
    return db_video

@app.put("/videos/{video_id}", response_model=schemas.Video)
def update_video(video_id: int, video: schemas.VideoCreate, db: Session = Depends(get_db)):
    db_video = db.query(models.Video).filter(models.Video.id == video_id).first()
    if db_video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    
    for key, value in video.dict(exclude_unset=True).items():
        setattr(db_video, key, value)
    
    db.commit()
    db.refresh(db_video)
    return db_video

@app.delete("/videos/{video_id}")
def delete_video(video_id: int, db: Session = Depends(get_db)):
    db_video = db.query(models.Video).filter(models.Video.id == video_id).first()
    if db_video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    db.delete(db_video)
    db.commit()
    return {"ok": True}

# --- Folders ---
@app.get("/folders/", response_model=List[schemas.Folder])
def read_folders(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    folders = db.query(models.Folder).offset(skip).limit(limit).all()
    return folders

@app.post("/folders/", response_model=schemas.Folder)
def create_folder(folder: schemas.FolderCreate, db: Session = Depends(get_db)):
    db_folder = models.Folder(**folder.dict())
    db.add(db_folder)
    db.commit()
    db.refresh(db_folder)
    return db_folder

# --- Stats ---
@app.get("/stats/")
def get_stats(db: Session = Depends(get_db)):
    total_videos = db.query(models.Video).count()
    total_size_result = db.query(func.sum(models.Video.file_size)).scalar()
    total_size = total_size_result if total_size_result else 0
    
    # By Stars
    stars_stats = db.query(models.Video.stars, func.count(models.Video.id)).group_by(models.Video.stars).all()
    
    # By Year
    year_stats = db.query(models.Video.year, func.count(models.Video.id)).group_by(models.Video.year).all()
    
    return {
        "total_videos": total_videos,
        "total_size": total_size,
        "by_stars": {str(s): c for s, c in stars_stats},
        "by_year": {str(y): c for y, c in year_stats}
    }

@app.get("/")
def read_root():
    return {"message": "Welcome to Media Library API"}
