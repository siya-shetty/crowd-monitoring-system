import time
from threading import Event
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import live
from app.tracking.schemas import TrackedPerson


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    live.states.clear()
    class Detector:
        def detect(self, frame):
            return []
    class Tracker:
        def __init__(self,*args):
            self.calls=0
        def update(self, detections):
            self.calls+=1
            return [TrackedPerson(track_id=1,x1=1,y1=1,x2=20,y2=20,confidence=.9)]
    monkeypatch.setattr(live,'get_detector',lambda *a:Detector())
    monkeypatch.setattr(live,'PersonTracker',Tracker)
    yield
    live.states.clear()


def image(width=64,height=64):
    return cv2.imencode('.jpg',np.zeros((height,width,3),dtype=np.uint8))[1].tobytes()


def send(client,id,sequence=1,capture=1,data=None):
    return client.post(f'/live/sessions/{id}/frame',params={'sequence':sequence,'capture_timestamp':capture},content=image() if data is None else data,headers={'Content-Type':'image/jpeg'})


def test_sequences_isolation_cleanup_and_bounded_history():
    client=TestClient(app);first,second=uuid4(),uuid4()
    for id in (first,second):
        assert client.post(f'/live/sessions/{id}/start').status_code==200
    for sequence in (1,2,3):
        assert send(client,first,sequence,sequence).status_code==200
    tracker=live.states[first].tracker
    for sequence in (3,2):
        assert send(client,first,sequence,sequence).status_code==409
    assert send(client,first,4,4).status_code==200
    assert tracker.calls==4
    assert send(client,second).json()['tracks'][0]['track_id']==1
    assert live.states[second].tracker is not tracker
    for sequence in range(5,25):
        assert send(client,first,sequence,sequence).status_code==200
    assert len(live.states[first].counts)==10
    for _ in range(2):
        assert client.post(f'/live/sessions/{first}/stop').status_code==200
    assert first not in live.states
    assert send(client,first,25,25).status_code==410


@pytest.mark.parametrize('data,code',[(b'',413),(b'broken',422),(b'x'*524289,413),(image(2000,16),422),(image(8,8),422)],ids=['empty','malformed','oversized','wide','tiny'])
def test_invalid_frames(data,code):
    client=TestClient(app);id=uuid4();client.post(f'/live/sessions/{id}/start')
    assert send(client,id,data=data).status_code==code
    assert live.states[id].tracker is None
    assert send(client,id).status_code==200
    assert send(client,id,2,2,image(80,64)).status_code==422


def test_busy_rejection_failure_and_expiry(monkeypatch):
    client=TestClient(app);id=uuid4();client.post(f'/live/sessions/{id}/start')
    entered,release=Event(),Event()
    class Slow:
        def detect(self, frame):
            entered.set();assert release.wait(5);return []
    monkeypatch.setattr(live,'get_detector',lambda *a:Slow())
    with ThreadPoolExecutor() as pool:
        first=pool.submit(send,client,id)
        assert entered.wait(5)
        assert send(client,id,2,2).status_code==429
        release.set();assert first.result().status_code==200
    live.states[id].touched=time.monotonic()-live.TTL-1
    live.reap();assert id not in live.states
    client.post(f'/live/sessions/{id}/start')
    def fail(*a):raise RuntimeError('private details')
    monkeypatch.setattr(live,'get_detector',fail)
    response=send(client,id)
    assert response.status_code==503 and 'private' not in response.text and id not in live.states
