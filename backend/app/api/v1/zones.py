from uuid import UUID
from fastapi import APIRouter, HTTPException
from sqlalchemy import select, func
from app.api.v1.dependencies import DatabaseSession
from app.api.v1.videos import CurrentUser, owned
from app.models.video import Video
from app.models.zone import MonitoringZone
from app.schemas.spatial import Heatmap, ZoneCreate, ZoneUpdate, ZoneResponse
from app.services.spatial import refresh_heatmap, refresh_zone

router = APIRouter(prefix="/videos/{video_id}", tags=["spatial"])


def locked_video(database, user, video_id):
    # Serialize zone edits with video deletion and other zone writes.
    video = database.scalar(select(Video).where(Video.id == video_id, Video.owner_id == user.id).with_for_update())
    if video is None:
        raise HTTPException(404, "Video not found")
    return video


def zone_for(database, video_id, zone_id):
    zone = database.scalar(select(MonitoringZone).where(MonitoringZone.video_id == video_id, MonitoringZone.id == zone_id))
    if zone is None:
        raise HTTPException(404, "Zone not found")
    return zone


@router.post("/heatmap", response_model=Heatmap)
def generate_heatmap(video_id: UUID, database: DatabaseSession, user: CurrentUser):
    """Explicit lightweight backfill for earlier videos; no CV service request."""
    video = locked_video(database, user, video_id)
    if video.tracking_analysis is None or not video.width or not video.height:
        raise HTTPException(409, "Tracking results are not available")
    refresh_heatmap(video)
    database.commit()
    return video.heatmap_analysis


@router.get("/zones", response_model=list[ZoneResponse])
def list_zones(video_id: UUID, database: DatabaseSession, user: CurrentUser):
    owned(database, user, video_id)
    return list(database.scalars(select(MonitoringZone).where(MonitoringZone.video_id == video_id).order_by(MonitoringZone.created_at, MonitoringZone.id)))


@router.post("/zones", response_model=ZoneResponse, status_code=201)
def create_zone(video_id: UUID, payload: ZoneCreate, database: DatabaseSession, user: CurrentUser):
    video = locked_video(database, user, video_id)
    if database.scalar(select(func.count()).select_from(MonitoringZone).where(MonitoringZone.video_id == video_id)) >= 50:
        raise HTTPException(409, "A video can have at most 50 zones")
    zone = MonitoringZone(video_id=video_id, **payload.model_dump(mode="json"))
    refresh_zone(video, zone)
    database.add(zone)
    database.commit()
    database.refresh(zone)
    return zone


@router.get("/zones/{zone_id}", response_model=ZoneResponse)
def get_zone(video_id: UUID, zone_id: UUID, database: DatabaseSession, user: CurrentUser):
    owned(database, user, video_id)
    return zone_for(database, video_id, zone_id)


@router.patch("/zones/{zone_id}", response_model=ZoneResponse)
def update_zone(video_id: UUID, zone_id: UUID, payload: ZoneUpdate, database: DatabaseSession, user: CurrentUser):
    video = locked_video(database, user, video_id)
    zone = zone_for(database, video_id, zone_id)
    for key, value in payload.model_dump(mode="json", exclude_unset=True).items():
        setattr(zone, key, value)
    refresh_zone(video, zone)
    database.commit()
    database.refresh(zone)
    return zone


@router.delete("/zones/{zone_id}", status_code=204)
def delete_zone(video_id: UUID, zone_id: UUID, database: DatabaseSession, user: CurrentUser):
    locked_video(database, user, video_id)
    database.delete(zone_for(database, video_id, zone_id))
    database.commit()
