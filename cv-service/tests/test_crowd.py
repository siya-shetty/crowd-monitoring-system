from types import SimpleNamespace
import random
import pytest
from app.crowd.analysis import image_occupancy, crowd_concentration
from app.crowd.aggregation import aggregate
from app.crowd.schemas import CrowdConfig, count_trend
from app.crowd.config import from_environment
from app.tracking.schemas import TrackingFrame, TrackedPerson


def boxes(rectangles):
    return [SimpleNamespace(x1=a, y1=b, x2=c, y2=d) for a, b, c, d in rectangles]


@pytest.mark.parametrize('rectangles,area', [
    ([], 0), ([(0, 0, 2, 2)], 4),
    ([(0, 0, 2, 2), (3, 3, 5, 5)], 8),
    ([(0, 0, 4, 4), (2, 2, 6, 6)], 28),
    ([(0, 0, 4, 4), (0, 0, 4, 4)], 16),
    ([(0, 0, 10, 10), (2, 2, 4, 4)], 100),
    ([(0, 0, 5, 10), (5, 0, 10, 10)], 100),
    ([(-2, -2, 5, 5), (8, 8, 12, 12)], 29),
    ([(2, 2, 2, 4), (4, 4, 1, 1), (20, 20, 30, 30)], 0),
])
def test_union(rectangles, area):
    assert image_occupancy(boxes(rectangles), 10, 10) == pytest.approx(area / 100)


def test_union_matches_independent_pixel_cells_for_random_integer_boxes():
    rng = random.Random(6)
    for _ in range(100):
        rectangles = [tuple(rng.randint(-3, 13) for _ in range(4)) for _ in range(12)]
        expected = sum(any(a <= x < c and b <= y < d for a, b, c, d in rectangles)
                       for x in range(10) for y in range(10)) / 100
        result = image_occupancy(boxes(rectangles), 10, 10)
        assert 0 <= result <= 1
        assert result == pytest.approx(expected)


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf')])
def test_non_finite_boxes_rejected(value):
    with pytest.raises(ValueError): image_occupancy(boxes([(0, 0, value, 2)]), 10, 10)


def test_concentration_and_resolution_independence():
    assert crowd_concentration([], 100, 100) == 0
    assert crowd_concentration(boxes([(1, 1, 2, 2)]), 100, 100) == 0
    clustered = [(45, 45, 55, 55), (46, 46, 56, 56)]
    spread = [(0, 0, 10, 10), (90, 90, 100, 100)]
    c = crowd_concentration(boxes(clustered), 100, 100)
    assert 0 <= crowd_concentration(boxes(spread), 100, 100) < c <= 1
    assert crowd_concentration(boxes([(a*2,b*2,c*2,d*2) for a,b,c,d in clustered]), 200, 200) == c
    assert crowd_concentration(boxes([(1,1,2,2)] * 3), 10, 10) == 1


@pytest.mark.parametrize('count,level', [(0,'LOW'),(4,'LOW'),(5,'MODERATE'),(9,'MODERATE'),(10,'HIGH'),(19,'HIGH'),(20,'VERY_HIGH')])
def test_thresholds(count, level):
    assert CrowdConfig().level(count) == level


@pytest.mark.parametrize('config', [dict(moderate_count=0),dict(high_count=5),dict(very_high_count=9),
    dict(moderate_count=float('nan')),dict(high_count=2.5),dict(trend_window_frames=0)])
def test_invalid_config(config):
    with pytest.raises(ValueError): CrowdConfig(**config)


def test_environment(monkeypatch):
    monkeypatch.setenv('CROWD_MODERATE_COUNT', '3')
    assert from_environment().moderate_count == 3
    monkeypatch.setenv('CROWD_HIGH_COUNT', '2')
    with pytest.raises(ValueError): from_environment()


@pytest.mark.parametrize('counts,trend', [(list(range(10)),'increasing'),(list(range(10,0,-1)),'decreasing'),
    ([4]*10,'stable'),([0,1]*5,'stable'),([0,100],'stable')])
def test_trend(counts, trend):
    assert count_trend(counts, CrowdConfig()) == trend


def test_aggregation_peaks_delta_distribution_and_determinism():
    frames = [TrackingFrame(frame_index=i*2, timestamp_seconds=i*.2, active_track_count=count,
        tracked_persons=[TrackedPerson(track_id=j+1,x1=1,y1=1,x2=3,y2=3,confidence=.8) for j in range(count)])
        for i,count in enumerate([0,1,5,10,20,20,0])]
    result = aggregate(frames, 10, 10, CrowdConfig())
    assert result == aggregate(frames, 10, 10, CrowdConfig())
    s = result.summary
    assert (s.minimum_observed_crowd_count, s.maximum_observed_crowd_count, s.median_observed_crowd_count) == (0,20,5)
    assert s.average_observed_crowd_count == 8
    assert (s.peak_crowd_frame, s.peak_crowd_timestamp_seconds) == (8,.8)
    assert (s.peak_occupancy_frame, s.peak_occupancy_timestamp_seconds) == (2,.2)
    assert [f.crowd_count_delta for f in result.frames] == [0,1,4,5,10,0,-20]
    assert [d.frames for d in s.level_distribution] == [3,1,1,2]
    assert sum(d.percentage for d in s.level_distribution) == pytest.approx(100)
    assert s.frames_with_observed_people == 5
    assert result.frames[0].image_occupancy_ratio == result.frames[0].crowd_concentration == 0
    assert result.frames[1].crowd_concentration == 0
    assert aggregate([],10,10,CrowdConfig()).summary.peak_crowd_frame is None
