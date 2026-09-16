from typing import Annotated
from uuid import UUID
from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from app.api.v1.dependencies import DatabaseSession, get_current_active_user
from app.models.user import User
from app.models.video import Video
from app.schemas.video import VideoResponse
from app.services.video_processing import analyze_video
from app.services.video_storage import VideoStorage
router=APIRouter(prefix="/videos", tags=["videos"])
CurrentUser=Annotated[User,Depends(get_current_active_user)]
def owned(database: DatabaseSession, user: User, video_id: UUID)->Video:
    video=database.scalar(select(Video).where(Video.id==video_id,Video.owner_id==user.id))
    if video is None: raise HTTPException(status_code=404,detail="Video not found")
    return video
@router.post("",response_model=VideoResponse,status_code=status.HTTP_201_CREATED)
def upload_video(file: Annotated[UploadFile,File(...)], database: DatabaseSession,user:CurrentUser)->Video:
    storage=VideoStorage()
    try: key,size=storage.save(file)
    except ValueError as error: raise HTTPException(status_code=400,detail=str(error)) from None
    video=Video(owner_id=user.id,original_filename=Path(file.filename or "video").name,storage_key=key,content_type=file.content_type or "application/octet-stream",file_size=size); database.add(video)
    try: database.commit(); database.refresh(video)
    except Exception: database.rollback(); storage.delete(key); raise
    return analyze_video(database,video)
@router.get("",response_model=list[VideoResponse])
def list_videos(database:DatabaseSession,user:CurrentUser)->list[Video]: return list(database.scalars(select(Video).where(Video.owner_id==user.id).order_by(Video.created_at.desc())))
@router.get("/{video_id}",response_model=VideoResponse)
def get_video(video_id:UUID,database:DatabaseSession,user:CurrentUser)->Video: return owned(database,user,video_id)
@router.get("/{video_id}/preview")
def get_preview(video_id:UUID,database:DatabaseSession,user:CurrentUser)->FileResponse:
    video=owned(database,user,video_id)
    if not video.preview_storage_key: raise HTTPException(status_code=404,detail="Annotated preview not found")
    path=VideoStorage().path_for(video.preview_storage_key)
    if not path.is_file(): raise HTTPException(status_code=404,detail="Annotated preview not found")
    return FileResponse(path, media_type="image/jpeg")
@router.delete("/{video_id}",status_code=204)
def delete_video(video_id:UUID,database:DatabaseSession,user:CurrentUser)->None:
    from app.api.v1.zones import locked_video
    from app.models.alert import AlertRule
    from sqlalchemy import delete
    video=locked_video(database,user,video_id)
    database.execute(delete(AlertRule).where(AlertRule.video_id == video_id))
    VideoStorage().delete(video.storage_key)
    if video.preview_storage_key: VideoStorage().delete(video.preview_storage_key)
    database.delete(video); database.commit()
