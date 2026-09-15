"""Opt-in real inference gate: python scripts/verify_tracking.py SOURCE OUTPUT_DIR.

SOURCE must be a real person-containing video. OUTPUT_DIR must be ignored/local.
Creates a 40-frame MP4, runs YOLO + ByteTrack twice and saves a metrics report.
This is deliberately separate from the deterministic unit suite.
"""
import json
import sys
from pathlib import Path
import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.video.processor import analyze_video
from app.tracking.config import TrackingConfig
from app.tracking.tracker import PersonTracker


def main():
    source, output = Path(sys.argv[1]), Path(sys.argv[2])
    output.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(source))
    width, height = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = capture.get(cv2.CAP_PROP_FPS)
    clip = output / 'pedestrians.mp4'
    writer = cv2.VideoWriter(str(clip), cv2.VideoWriter_fourcc(*'mp4v'), fps, (width, height))
    assert writer.isOpened()
    try:
        for _ in range(40):
            ok, frame = capture.read()
            assert ok, 'At least 40 consecutive real frames are required'
            writer.write(frame)
    finally:
        capture.release()
        writer.release()
    results = [analyze_video(clip, 'yolo11n.pt', .35, 640, 5) for _ in range(2)]
    for result in results:
        tracking = result['tracking']
        assert result['total_person_detections'] > 0
        assert tracking['summary']['processed_frames'] == 40
        assert max(t['observation_count'] for t in tracking['tracks']) > 1
        assert all(f['active_track_count'] == len(f['tracked_persons']) for f in tracking['frames'])
        assert any(len({(p['center_x'], p['center_y']) for p in t['trajectory']}) > 1 for t in tracking['tracks'])
    assert results[0]['tracking'] == results[1]['tracking'], 'State leaked between analyses'
    # Interleave real tracker instances, including a later new ID in each session.
    a, b = PersonTracker(TrackingConfig(), 400, 400), PersonTracker(TrackingConfig(), 400, 400)
    box = dict(x1=10., y1=10., x2=50., y2=100., confidence=.9)
    second = dict(x1=200., y1=10., x2=240., y2=100., confidence=.9)
    assert [p.track_id for p in a.update([box])] == [1]
    assert [p.track_id for p in b.update([box])] == [1]
    for tracker in (a, b):
        tracker.update([box, second])
        assert [p.track_id for p in tracker.update([box, second])] == [1, 2]
    report = dict(source=str(source.name), clip_frames=40, fps=fps,
        runs=[dict(duration_seconds=r['processing_duration_seconds'], detections=r['total_person_detections'],
                   summary=r['tracking']['summary'], observations={str(t['track_id']):t['observation_count'] for t in r['tracking']['tracks']}) for r in results],
        repeat_state_isolated=True, interleaved_state_isolated=True)
    (output / 'real-tracking-report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
