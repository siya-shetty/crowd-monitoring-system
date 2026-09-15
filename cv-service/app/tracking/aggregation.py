from collections import defaultdict
from app.tracking.config import TrackingConfig
from app.tracking.schemas import TrackingAnalysis, TrackingFrame, TrackingSummary, TrackHistory, TrajectoryPoint


def aggregate(frames: list[TrackingFrame], width: int, height: int, config: TrackingConfig) -> TrackingAnalysis:
    observations = defaultdict(list)
    for frame in frames:
        for person in frame.tracked_persons:
            observations[person.track_id].append((frame, person))
    tracks = []
    for track_id, items in sorted(observations.items()):
        first, last = items[0][0], items[-1][0]
        tracks.append(TrackHistory(track_id=track_id,
            first_observed_frame=first.frame_index, last_observed_frame=last.frame_index,
            first_observed_timestamp=first.timestamp_seconds, last_observed_timestamp=last.timestamp_seconds,
            observation_count=len(items), average_confidence=sum(p.confidence for _, p in items) / len(items),
            trajectory=[TrajectoryPoint(frame_index=f.frame_index, timestamp_seconds=f.timestamp_seconds,
                center_x=(p.x1 + p.x2) / (2 * width), center_y=(p.y1 + p.y2) / (2 * height)) for f, p in items]))
    counts = [f.active_track_count for f in frames]
    lengths = [t.observation_count for t in tracks]
    return TrackingAnalysis(summary=TrackingSummary(
        frame_stride=config.frame_stride, track_high_threshold=config.track_high_thresh,
        track_low_threshold=config.track_low_thresh, track_match_threshold=config.match_thresh,
        track_buffer=config.track_buffer, processed_frames=len(frames),
        frames_with_active_tracks=sum(c > 0 for c in counts),
        maximum_simultaneous_active_tracks=max(counts, default=0),
        average_active_tracks_per_processed_frame=sum(counts) / len(counts) if counts else 0,
        distinct_track_ids=len(tracks), average_track_observation_length=sum(lengths) / len(lengths) if lengths else 0,
        longest_track_observation_length=max(lengths, default=0)), frames=frames, tracks=tracks)
