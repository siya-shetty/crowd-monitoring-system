from types import SimpleNamespace
import pytest
from app.schemas.spatial import Point, ZoneCreate, ZoneUpdate, Heatmap, ZoneAnalysis
from app.services.spatial_geometry import contains, foot_point
from app.services.spatial import heatmap, analyze_zone

SQUARE = [dict(x=x, y=y) for x, y in [(0,0),(.5,0),(.5,1),(0,1)]]


def frame(index=0, persons=None):
    persons = persons if persons is not None else [(1, 10, 10, 30, 50)]
    return dict(frame_index=index,timestamp_seconds=index/10,active_track_count=len(persons),
        tracked_persons=[dict(track_id=i,x1=a,y1=b,x2=c,y2=d,confidence=.9) for i,a,b,c,d in persons])


@pytest.mark.parametrize('box,expected', [
    ((10,10,30,50),(.2,.5)), ((-10,-10,30,110),(.15,1)),
    ((0,0,100,100),(.5,1)), ((101,0,110,100),None), ((2,2,2,5),None)])
def test_foot_point(box,expected):
    assert foot_point(SimpleNamespace(**dict(zip(('x1','y1','x2','y2'),box))),100,100) == expected


@pytest.mark.parametrize('x,y,result',[(.2,.5,True),(.8,.5,False),(.5,.5,True),(0,0,True),(.5,1,True)])
def test_boundary_membership(x,y,result):
    assert contains([Point(**p) for p in SQUARE],Point(x=x,y=y)) == result


def test_concave_membership():
    polygon=ZoneCreate(name='L',polygon=[dict(x=x,y=y) for x,y in [(0,0),(1,0),(1,.3),(.3,.3),(.3,1),(0,1)]]).polygon
    assert contains(polygon,Point(x=.1,y=.8))
    assert not contains(polygon,Point(x=.8,y=.8))


@pytest.mark.parametrize('polygon', [[],SQUARE[:2],SQUARE+[SQUARE[0]],
    [dict(x=x,y=y) for x,y in [(0,0),(.2,.2),(.4,.4)]],
    [dict(x=x,y=y) for x,y in [(0,0),(1,1),(0,1),(1,0)]],
    [dict(x=x,y=y) for x,y in [(0,0),(.8,0),(.4,0),(.4,1)]],
    [dict(x=-.1,y=0)]+SQUARE[1:], [dict(x=float('nan'),y=0)]+SQUARE[1:],
    [dict(x=float('inf'),y=0)]+SQUARE[1:], SQUARE*13])
def test_invalid_polygons(polygon):
    with pytest.raises(ValueError): ZoneCreate(name='Invalid',polygon=polygon)


@pytest.mark.parametrize('patch',[{'name':None},{'active':None},{'polygon':None},{'name':'  '},{'extra':1}])
def test_invalid_update(patch):
    with pytest.raises(ValueError): ZoneUpdate.model_validate(patch)


def test_heatmap_empty():
    result=heatmap([],100,100)
    assert result.total_valid_spatial_observations == result.maximum_cell_observation_count == 0
    assert result.hottest_cell is result.hottest_cell_center is None


def test_heatmap_repeated_and_deterministic():
    frames=[frame(i) for i in range(3)]+[frame(3,[(2,80,10,100,100)])]
    result=heatmap(frames,100,100,2,2)
    assert result.raw_counts == [[0,0],[3,1]]
    assert result.maximum_cell_observation_count == 3
    assert result.total_valid_spatial_observations == 4
    assert result.hottest_cell == (0,1)
    assert result.hottest_cell_center == Point(x=.25,y=.75)
    assert result == heatmap(frames,100,100,2,2)
    assert max(c/result.maximum_cell_observation_count for r in result.raw_counts for c in r) == 1


def test_upper_grid_boundary(monkeypatch):
    # Exact x=1 cannot be a positive-width clipped box center, but grid mapping is safe.
    monkeypatch.setattr('app.services.spatial.foot_point',lambda *args:(1,1))
    assert heatmap([frame()],100,100,2,2).raw_counts == [[0,0],[0,1]]


@pytest.mark.parametrize('mutation',[
    lambda p:p.update(raw_counts=[[0]]),lambda p:p.update(maximum_cell_observation_count=8),
    lambda p:p.update(total_valid_spatial_observations=8),lambda p:p.update(hottest_cell=[1,1]),
    lambda p:p['raw_counts'][0].__setitem__(0,-1),lambda p:p['raw_counts'][0].__setitem__(0,float('nan'))])
def test_malformed_heatmap(mutation):
    p=heatmap([frame()],100,100,2,2).model_dump(mode='json');mutation(p)
    with pytest.raises(ValueError): Heatmap.model_validate(p)


def test_zone_statistics_and_overlaps():
    frames=[frame(0,[]),frame(1),frame(2,[(1,10,10,30,50),(2,40,0,60,100),(3,80,0,100,50)]),frame(3)]
    result=analyze_zone(frames,100,100,SQUARE)
    assert [f.active_tracks_in_zone for f in result.frames] == [0,1,2,1]
    assert result.frames[2].track_ids_in_zone == [1,2]
    assert result.summary.model_dump() == dict(processed_frames=4,frames_with_people=3,maximum_simultaneous_tracks=2,
        average_simultaneous_tracks=1.,median_simultaneous_tracks=1.,earliest_peak_frame=2,
        earliest_peak_timestamp_seconds=.2,distinct_anonymous_track_ids=2,total_track_observations=4)
    assert result == analyze_zone(frames,100,100,SQUARE)
    whole=[dict(x=x,y=y) for x,y in [(0,0),(1,0),(1,1),(0,1)]]
    assert analyze_zone(frames,100,100,whole).frames[2].track_ids_in_zone == [1,2,3]


@pytest.mark.parametrize('frames,peak',[([],None),([frame(0,[])],0),([frame(0),frame(1)],0)])
def test_zone_zero_and_tied_peak(frames,peak):
    assert analyze_zone(frames,100,100,SQUARE).summary.earliest_peak_frame == peak


def test_zone_payload_validation():
    p=analyze_zone([frame()],100,100,SQUARE).model_dump(mode='json')
    p['summary']['total_track_observations']=100
    with pytest.raises(ValueError): ZoneAnalysis.model_validate(p)


@pytest.mark.parametrize('frames',[[frame(1),frame(0)],[frame(),frame()]])
def test_invalid_chronology(frames):
    with pytest.raises(ValueError): heatmap(frames,100,100)


@pytest.mark.parametrize('width,height',[(0,100),(100,-1),(float('nan'),100),(100,float('inf'))])
def test_invalid_dimensions_even_for_empty_frames(width,height):
    with pytest.raises(ValueError): heatmap([],width,height)


@pytest.mark.parametrize('grid',[(0,1),(1,129),(1.5,2),(True,1)])
def test_invalid_grid_bounds(grid):
    with pytest.raises(ValueError): heatmap([],100,100,*grid)


def test_one_observation_and_row_major_tie():
    result=heatmap([frame()],100,100,2,2)
    assert result.raw_counts==[[0,0],[1,0]]
    assert result.total_valid_spatial_observations==1
    tied=heatmap([frame(0,[(1,80,0,100,25),(2,0,0,20,100)])],100,100,2,2)
    assert tied.hottest_cell==(1,0)


def test_zone_count_uses_foot_not_center_or_box_overlap():
    top=[dict(x=x,y=y) for x,y in [(0,0),(1,0),(1,.4),(0,.4)]]
    assert analyze_zone([frame()],100,100,top).summary.total_track_observations==0
