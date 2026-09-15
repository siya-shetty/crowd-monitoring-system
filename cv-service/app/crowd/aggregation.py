from app.crowd.analysis import crowd_concentration, image_occupancy
from app.crowd.schemas import CrowdAnalysis, CrowdConfig, CrowdFrame, count_trend, summarize
from app.tracking.schemas import TrackingFrame


def aggregate(frames: list[TrackingFrame], width: int, height: int, config: CrowdConfig) -> CrowdAnalysis:
    results, counts = [], []
    for frame in frames:
        count = frame.active_track_count
        delta = count - counts[-1] if counts else 0
        counts.append(count)
        results.append(CrowdFrame(frame_index=frame.frame_index, timestamp_seconds=frame.timestamp_seconds,
            observed_crowd_count=count, image_occupancy_ratio=image_occupancy(frame.tracked_persons, width, height),
            crowd_concentration=crowd_concentration(frame.tracked_persons, width, height),
            crowd_level=config.level(count), crowd_count_delta=delta, crowd_trend=count_trend(counts, config)))
    return CrowdAnalysis(config=config, frames=results, summary=summarize(results))
