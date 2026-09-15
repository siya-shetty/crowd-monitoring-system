"""Opt-in real CPU gate: python scripts/verify_crowd.py CLIP IGNORED_OUTPUT_DIR."""
import json
import statistics
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.video.processor import analyze_video
from app.crowd.aggregation import aggregate
from app.crowd.analysis import image_occupancy
from app.crowd.schemas import CrowdConfig
from app.tracking.schemas import TrackingFrame


def main():
    clip, output = Path(sys.argv[1]), Path(sys.argv[2])
    output.mkdir(parents=True, exist_ok=True)
    result = analyze_video(clip, 'yolo11n.pt', .35, 640, 5)
    crowd = result['crowd']
    frames = [TrackingFrame.model_validate(f) for f in result['tracking']['frames']]
    assert len(frames) > 1 and crowd['summary']['maximum_observed_crowd_count'] > 0
    assert [f['observed_crowd_count'] for f in crowd['frames']] == [f.active_track_count for f in frames]
    width, height = result['width'], result['height']
    # Independent exact integration: partition the first populated frame into
    # cells along every x AND y edge, and test each cell's midpoint for coverage.
    chosen = next(f for f in frames if f.tracked_persons)
    boxes = chosen.tracked_persons
    xs = sorted({p.x1 for p in boxes} | {p.x2 for p in boxes})
    ys = sorted({p.y1 for p in boxes} | {p.y2 for p in boxes})
    union = sum((b-a)*(d-c) for a,b in zip(xs,xs[1:]) for c,d in zip(ys,ys[1:])
        if any(p.x1 <= (a+b)/2 < p.x2 and p.y1 <= (c+d)/2 < p.y2 for p in boxes)) / (width*height)
    actual = next(f['image_occupancy_ratio'] for f in crowd['frames'] if f['frame_index']==chosen.frame_index)
    assert abs(actual-union) < 1e-9
    sums = [sum((p.x2-p.x1)*(p.y2-p.y1) for p in f.tracked_persons)/(width*height) for f in frames]
    overlap = [i for i,(s,f) in enumerate(zip(sums,crowd['frames'])) if s > f['image_occupancy_ratio']+1e-9]
    # Deterministic overlap proof regardless of what the real clip contains.
    assert image_occupancy([SimpleNamespace(x1=0,y1=0,x2=4,y2=4),
        SimpleNamespace(x1=2,y1=2,x2=6,y2=6)],10,10) == .28
    timings = []
    for _ in range(30):
        started = time.perf_counter()
        repeated = aggregate(frames,width,height,CrowdConfig())
        timings.append(time.perf_counter()-started)
        assert repeated.model_dump(mode='json') == crowd
    report = dict(clip_frames=result['frame_count'], fps=result['fps'], cpu_torch=torch.__version__,
        cuda_available=torch.cuda.is_available(), summary=crowd['summary'], frames=crowd['frames'],
        independent_occupancy_check=dict(frame_index=chosen.frame_index,union_ratio=union,actual_ratio=actual),
        real_overlapping_frames=len(overlap), first_overlap=(dict(frame_index=frames[overlap[0]].frame_index,
            summed_box_ratio=sums[overlap[0]],union_ratio=crowd['frames'][overlap[0]]['image_occupancy_ratio']) if overlap else None),
        processing_seconds=result['processing_duration_seconds'],
        median_crowd_seconds=statistics.median(timings),
        crowd_fraction_of_pipeline=statistics.median(timings)/result['processing_duration_seconds'],
        deterministic_repeats=30)
    (output/'analysis.json').write_text(json.dumps(result),encoding='utf-8')
    (output/'real-crowd-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='frames'},indent=2))


if __name__ == '__main__':
    main()
