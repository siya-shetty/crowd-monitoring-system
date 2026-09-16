"""Spatial analysis consumes validated tracking observations, never video/inference."""
import math
from app.schemas.spatial import Heatmap, Point, ZoneAnalysis, ZoneFrame, summarize
from app.schemas.tracking import TrackingFrame
from app.services.spatial_geometry import contains, foot_point, validate_polygon


def observations(frames, width, height):
    if not all(math.isfinite(v) and v > 0 for v in (width, height)):
        raise ValueError("Image dimensions must be positive")
    previous = None
    for raw in frames:
        frame = TrackingFrame.model_validate(raw)
        if previous and (frame.frame_index <= previous.frame_index or frame.timestamp_seconds <= previous.timestamp_seconds):
            raise ValueError("Tracking frames must be chronological")
        points = []
        for box in frame.tracked_persons:
            point = foot_point(box, width, height)
            if point is not None:
                points.append((box.track_id, Point(x=point[0], y=point[1])))
        yield frame, points
        previous = frame


def heatmap(frames, width, height, grid_width=32, grid_height=18):
    if any(type(v) is not int or not 1 <= v <= 128 for v in (grid_width, grid_height)):
        raise ValueError("Grid dimensions must be integers from 1 to 128")
    grid = [[0] * grid_width for _ in range(grid_height)]
    for _, points in observations(frames, width, height):
        for _, p in points:
            grid[min(grid_height - 1, int(p.y * grid_height))][min(grid_width - 1, int(p.x * grid_width))] += 1
    flat = [c for row in grid for c in row]
    maximum = max(flat)
    index = flat.index(maximum)
    cell = (index % grid_width, index // grid_width) if maximum else None
    return Heatmap(grid_width=grid_width, grid_height=grid_height, raw_counts=grid,
        total_valid_spatial_observations=sum(flat), maximum_cell_observation_count=maximum,
        hottest_cell=cell, hottest_cell_center=Point(x=(cell[0] + .5) / grid_width, y=(cell[1] + .5) / grid_height) if cell else None)


def analyze_zone(frames, width, height, polygon):
    points = validate_polygon([Point.model_validate(p) for p in polygon])
    results = []
    for frame, people in observations(frames, width, height):
        ids = sorted(i for i, p in people if contains(points, p))
        results.append(ZoneFrame(frame_index=frame.frame_index, timestamp_seconds=frame.timestamp_seconds,
                                 active_tracks_in_zone=len(ids), track_ids_in_zone=ids))
    return ZoneAnalysis(frames=results, summary=summarize(results))


def refresh_heatmap(video):
    from app.core.config import get_settings
    config = get_settings()
    if video.tracking_analysis is not None and video.width and video.height:
        video.heatmap_analysis = heatmap(video.tracking_analysis["frames"], video.width, video.height,
            config.heatmap_grid_width, config.heatmap_grid_height).model_dump(mode="json")


def refresh_zone(video, zone):
    zone.analysis = (analyze_zone(video.tracking_analysis["frames"], video.width, video.height, zone.polygon)
        .model_dump(mode="json") if zone.active and video.tracking_analysis is not None and video.width and video.height else None)
