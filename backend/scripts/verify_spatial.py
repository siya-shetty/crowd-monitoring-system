"""Verify a real, already uploaded video's persisted spatial results.

Run from backend: .venv/Scripts/python.exe scripts/verify_spatial.py VIDEO_UUID OUTPUT_JSON
Outputs geometry/anonymous IDs to ignored storage only. Does not invoke inference.
"""
import json
from pathlib import Path
import statistics
import sys
import time
import uuid
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.session import SessionLocal
from app.models.video import Video
from app.services.spatial import analyze_zone, heatmap


def main():
    with SessionLocal() as db:
        video = db.get(Video, uuid.UUID(sys.argv[1]))
        assert video is not None and video.status == 'completed'
        frames = video.tracking_analysis['frames']
        stored = video.heatmap_analysis
        assert len(frames) > 1 and stored['total_valid_spatial_observations'] > 1
        # Independent cell oracle from the already validated pixel boxes.
        cells = Counter()
        for f in frames:
            for p in f['tracked_persons']:
                x = (max(0, p['x1']) + min(video.width, p['x2'])) / (2 * video.width)
                y = min(video.height, p['y2']) / video.height
                cells[min(stored['grid_width']-1, int(x*stored['grid_width'])),
                      min(stored['grid_height']-1, int(y*stored['grid_height']))] += 1
        for y, row in enumerate(stored['raw_counts']):
            for x, count in enumerate(row):
                assert count == cells[x,y]
        total = sum(cells.values())
        assert total == stored['total_valid_spatial_observations']
        assert max(c / stored['maximum_cell_observation_count'] for c in cells.values()) == 1
        assert heatmap(frames,video.width,video.height,stored['grid_width'],stored['grid_height']).model_dump(mode='json') == stored
        times = []
        polygon = [dict(x=x,y=y) for x,y in [(0,.3),(1,.3),(1,1),(0,1)]]
        quiet = [dict(x=x,y=y) for x,y in [(0,0),(.2,0),(.2,.2),(0,.2)]]
        for _ in range(30):
            start = time.perf_counter()
            heatmap(frames,video.width,video.height)
            active = analyze_zone(frames,video.width,video.height,polygon)
            outside = analyze_zone(frames,video.width,video.height,quiet)
            times.append(time.perf_counter()-start)
        assert active.summary.total_track_observations > outside.summary.total_track_observations
        report = dict(video_id=str(video.id), frames=len(frames), dimensions=[video.width,video.height],
            total_observations=total, max_cell_count=stored['maximum_cell_observation_count'],
            hottest_cell=stored['hottest_cell'], hottest_cell_center=stored['hottest_cell_center'],
            normalized_intensity_max=1, active_zone=active.summary.model_dump(), quiet_zone=outside.summary.model_dump(),
            heatmap_plus_two_zones_median_seconds=statistics.median(times),
            original_cv_processing_seconds=video.detection_summary['processing_duration_seconds'],
            persisted_zones=[dict(id=str(z.id),name=z.name,active=z.active,summary=z.analysis['summary'] if z.analysis else None) for z in video.zones])
        output=Path(sys.argv[2]);output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(report,indent=2))
        print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
