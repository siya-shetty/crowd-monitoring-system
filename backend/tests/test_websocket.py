import time
import uuid
import pytest
from starlette.websockets import WebSocketDisconnect
from app.websocket.manager import ConnectionManager
from app.websocket.routes import consume, tickets, ticket_lock
from app.websocket.events import Event, State
from test_live import setup, send


def test_bounded_mailbox_isolation_cleanup_and_sequence():
    m = ConnectionManager()
    a, b, foreign = m.connect('a',2), m.connect('a',2), m.connect('b')
    with pytest.raises(ValueError):
        m.connect('a',2)
    state=State(id=uuid.uuid4(),status='RUNNING',processed_frame_count=0,dropped_frame_count=0,last_frame_at=None,is_stale=False,error_summary=None,latest_snapshot=None,alerts=[])
    started=time.perf_counter()
    previous=0
    for _ in range(10000):
        e=Event(event='session.snapshot',session_id=state.id,data=state)
        m.publish('a',[e])
        assert e.sequence>previous
        previous=e.sequence
    assert time.perf_counter()-started<3
    assert len(a.pending)==1 and a.replaced==9999 and not foreign.pending
    assert m.take(a)==m.take(b)
    m.disconnect('a',a)
    m.disconnect('a',b)
    m.disconnect('b',foreign)
    assert not m.rooms and not a.pending


def test_ticket_expiry_session_binding_and_single_use():
    user,session=uuid.uuid4(),uuid.uuid4()
    with ticket_lock:
        tickets['expired']=(user,session,time.monotonic()-1)
        tickets['wrong']=(user,session,time.monotonic()+30)
        tickets['valid']=(user,session,time.monotonic()+30)
    for token,target in [('expired',session),('wrong',uuid.uuid4()),('invalid',session)]:
        with pytest.raises(ValueError):consume(token,target)
    assert consume('valid',session)==user
    with pytest.raises(ValueError):consume('valid',session)


def test_authenticated_sockets_initial_frame_two_subscribers_reconnect_stop(monkeypatch):
    c,owner,other,base=setup(monkeypatch)
    s=c.post(base+'/sessions',headers=owner).json()
    url='/api/v1/live/sessions/'+s['id']
    assert c.post(url+'/ws-ticket').status_code==401
    assert c.post(url+'/ws-ticket',headers=other).status_code==404
    assert c.post('/api/v1/live/sessions/'+str(uuid.uuid4())+'/ws-ticket',headers=owner).status_code==404
    def credential():return c.post(url+'/ws-ticket',headers=owner).json()['ticket']
    def connect(origin='http://localhost:5173'):return c.websocket_connect(url+'/ws',headers={'origin':origin})
    with pytest.raises(WebSocketDisconnect):
        with connect('https://foreign.invalid'):pass
    with connect() as ws:
        ws.send_text('invalid')
        with pytest.raises(WebSocketDisconnect):ws.receive_json()
    token=credential()
    with connect() as a:
        a.send_text(token)
        initial=a.receive_json()
        assert initial['event']=='session.snapshot' and initial['data']['processed_frame_count']==0
        # Subscription must never invoke the CV adapter.
        from app.services import live
        original=live.cv
        monkeypatch.setattr(live,'cv',lambda *a,**k:pytest.fail('Subscription invoked CV'))
        with connect('http://127.0.0.1:5173') as b:
            b.send_text(credential())
            assert b.receive_json()['data']['processed_frame_count']==0
            monkeypatch.setattr(live,'cv',original)
            assert send(c,url,owner).status_code==200
            def processed(ws):
                for _ in range(5):
                    event=ws.receive_json()
                    if event['data']['processed_frame_count']==1:return event
                pytest.fail('No frame event')
            ea,eb=processed(a),processed(b)
            assert ea['sequence']==eb['sequence']>initial['sequence']
            assert 'tracks' not in ea['data']['latest_snapshot']
        with connect() as replay:
            replay.send_text(token)
            with pytest.raises(WebSocketDisconnect):replay.receive_json()
        with connect() as recovered:
            recovered.send_text(credential())
            assert recovered.receive_json()['data']['processed_frame_count']==1
        c.post(url+'/stop',headers=owner)
        for _ in range(5):
            final=a.receive_json()
            if final['event']=='session.stopped':break
        assert final['data']['status']=='STOPPED'
    c.delete(base,headers=owner)


def test_slow_sender_does_not_block_frames_and_cleans_up(monkeypatch):
    import asyncio
    from threading import Event as Signal
    from starlette.websockets import WebSocket
    from app.websocket.manager import manager
    c,owner,_,base=setup(monkeypatch)
    sid=c.post(base+'/sessions',headers=owner).json()['id']
    url='/api/v1/live/sessions/'+sid
    entered=Signal()
    async def slow_send(self,data):
        entered.set()
        await asyncio.sleep(30)
    monkeypatch.setattr(WebSocket,'send_text',slow_send)
    ticket=c.post(url+'/ws-ticket',headers=owner).json()['ticket']
    with c.websocket_connect(url+'/ws',headers={'origin':'http://localhost:5173'}) as ws:
        ws.send_text(ticket)
        assert entered.wait(2)
        start=time.perf_counter()
        assert send(c,url,owner).status_code==200
        assert time.perf_counter()-start<1.5
        with pytest.raises(WebSocketDisconnect):ws.receive_json()
    assert uuid.UUID(sid) not in manager.rooms
    c.post(url+'/stop',headers=owner)
    c.delete(base,headers=owner)


def test_alert_transitions_failure_and_stale_snapshot(monkeypatch):
    from app.services import live
    from fastapi import HTTPException
    from app.core.config import get_settings
    c,owner,_,base=setup(monkeypatch)
    c.post(base+'/alert-rules',headers=owner,json=dict(name='Count',scope='CAMERA',rule_type='CROWD_COUNT_ABOVE',severity='WARNING',configuration={'threshold':1}))
    sid=c.post(base+'/sessions',headers=owner).json()['id']
    url='/api/v1/live/sessions/'+sid
    ticket=c.post(url+'/ws-ticket',headers=owner).json()['ticket']
    original=live.cv
    with c.websocket_connect(url+'/ws',headers={'origin':'http://localhost:5173'}) as ws:
        ws.send_text(ticket);ws.receive_json()
        assert send(c,url,owner).status_code==200
        event=ws.receive_json();assert event['event']=='alert.triggered'
        assert event['alert']['rule_snapshot']['name']=='Count'
        assert ws.receive_json()['data']['latest_snapshot']['current_operational_risk']=='HIGH'
        live.runtime[uuid.UUID(sid)].last_accept=None
        def empty(*a,**k):
            result=original(*a,**k)
            if a[1]=='frame':result.update(tracks=[],observed_crowd_count=0)
            return result
        monkeypatch.setattr(live,'cv',empty)
        assert send(c,url,owner,2).status_code==200
        assert ws.receive_json()['event']=='alert.resolved'
        assert ws.receive_json()['data']['latest_snapshot']['current_operational_risk']=='NORMAL'
        monkeypatch.setattr(get_settings(),'live_session_stale_seconds',2)
        # Heartbeat-driven state refresh must mark stale without another frame.
        heartbeat=ws.receive_json();assert heartbeat['event']=='heartbeat';ws.send_text('pong')
        assert ws.receive_json()['data']['is_stale']
        live.runtime[uuid.UUID(sid)].last_accept=None
        def fail(*a,**k):raise HTTPException(503,'worker down')
        monkeypatch.setattr(live,'cv',fail)
        assert send(c,url,owner,3).status_code==503
        event=ws.receive_json();assert event['event']=='session.failed'
        assert event['data']['error_summary']=='worker_unavailable'
    c.delete(base,headers=owner)


def test_credentials_cannot_cross_session_or_user_and_terminal_recovery(monkeypatch):
    c,owner,other,base=setup(monkeypatch)
    sid=c.post(base+'/sessions',headers=owner).json()['id']
    url='/api/v1/live/sessions/'+sid
    response=c.post(url+'/ws-ticket',headers=owner)
    assert response.headers['cache-control']=='no-store'
    value=response.json()['ticket']
    with c.websocket_connect('/api/v1/live/sessions/'+str(uuid.uuid4())+'/ws',headers={'origin':'http://localhost:5173'}) as ws:
        ws.send_text(value)
        with pytest.raises(WebSocketDisconnect):ws.receive_json()
    # A ticket cannot authorize a REST request, including a different user's request.
    assert c.get(url,headers={'Authorization':'Bearer '+value}).status_code==401
    assert c.get(url,headers=other).status_code==404
    for message in [b'binary', 'x'*1025]:
        with c.websocket_connect(url+'/ws',headers={'origin':'http://localhost:5173'}) as ws:
            if isinstance(message,bytes):ws.send_bytes(message)
            else:ws.send_text(message)
            with pytest.raises(WebSocketDisconnect) as error:ws.receive_json()
            assert error.value.code==1008
    c.post(url+'/stop',headers=owner)
    value=c.post(url+'/ws-ticket',headers=owner).json()['ticket']
    with c.websocket_connect(url+'/ws',headers={'origin':'http://localhost:5173'}) as ws:
        ws.send_text(value)
        assert ws.receive_json()['event']=='session.stopped'
        with pytest.raises(WebSocketDisconnect):ws.receive_json()
    c.delete(base,headers=owner)
