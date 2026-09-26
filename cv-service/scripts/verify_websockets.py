"""Real sequential frames -> REST -> YOLO/ByteTrack -> two real WebSockets.

Usage: python scripts/verify_websockets.py VIDEO [--api http://127.0.0.1:8010]
Prints aggregate evidence only; never writes media, tickets or credentials.
"""
import argparse
import json
import statistics
import time
import uuid
from threading import Thread
from collections import deque
from websockets.exceptions import ConnectionClosed
from contextlib import ExitStack
import cv2
import httpx
from websockets.sync.client import connect


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('video')
    parser.add_argument('--api',default='http://127.0.0.1:8010')
    args=parser.parse_args()
    client=httpx.Client(base_url=args.api+'/api/v1',timeout=90,trust_env=False)
    def api(method,path,**kwargs):
        result=client.request(method,path,**kwargs)
        result.raise_for_status()
        return result.json() if result.status_code!=204 else None
    email=uuid.uuid4().hex+'@example.com';password=uuid.uuid4().hex+'Aa1!'
    api('POST','/auth/register',json=dict(email=email,password=password,full_name='Socket verification'))
    client.headers['Authorization']='Bearer '+api('POST','/auth/login',json=dict(email=email,password=password))['access_token']
    cameras=[];sessions=[];sockets=[]
    connections=ExitStack()
    def subscribe(sid):
        ticket=api('POST',f'/live/sessions/{sid}/ws-ticket')['ticket']
        ws=connections.enter_context(connect(args.api.replace('http','ws',1)+f'/api/v1/live/sessions/{sid}/ws',origin='http://localhost:5173',max_size=262144))
        ws.send(ticket);sockets.append(ws)
        return ws
    sizes=[];latencies=[];types=set()
    def receive(ws,count=0,terminal=False):
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            raw=ws.recv(timeout=15)
            event=json.loads(raw)
            if event['event']=='heartbeat':ws.send('pong');continue
            sizes.append(len(raw.encode()));types.add(event['event'])
            if terminal and event['event']=='session.stopped':return event
            if not terminal and event['event']=='session.snapshot' and event['data']['processed_frame_count']>=count:return event
        raise AssertionError('Expected socket state missing')
    try:
        for name in ['Primary','Isolated']:
            cameras.append(api('POST','/cameras',json={'name':name}))
        base='/cameras/'+cameras[0]['id']
        zone=api('POST',base+'/zones',json={'name':'Whole view','polygon':[{'x':0,'y':0},{'x':1,'y':0},{'x':1,'y':1},{'x':0,'y':1}]})
        api('POST',base+'/alert-rules',json=dict(name='Observed presence',scope='ZONE',zone_id=zone['id'],rule_type='ZONE_PRESENCE',severity='WARNING',configuration={}))
        for camera in cameras:sessions.append(api('POST','/cameras/'+camera['id']+'/sessions')['id'])
        a,b,isolated=[subscribe(s) for s in [sessions[0],sessions[0],sessions[1]]]
        assert receive(a)['data']['processed_frame_count']==0
        assert receive(b)['data']['processed_frame_count']==0
        assert receive(isolated)['session_id']==sessions[1]
        isolated_states=deque(maxlen=5)
        def read_isolated():
            try:
                while True:
                    raw=json.loads(isolated.recv())
                    if raw['event']=='heartbeat':isolated.send('pong')
                    else:isolated_states.append(raw)
            except ConnectionClosed:
                pass
        isolated_reader=Thread(target=read_isolated,daemon=True)
        isolated_reader.start()
        capture=cv2.VideoCapture(args.video);durations=[];ids=[];last_sequence=0
        for sequence in range(1,13):
            ok,frame=capture.read();assert ok
            image=cv2.imencode('.jpg',frame)[1].tobytes()
            response=api('POST',f'/live/sessions/{sessions[0]}/frames',content=image,headers={'Content-Type':'image/jpeg'},params={'sequence':sequence,'capture_timestamp':time.time()})
            start=time.perf_counter()
            eb=receive(b,sequence);latencies.append(time.perf_counter()-start)
            assert eb['sequence']>last_sequence;last_sequence=eb['sequence']
            assert eb['data']['latest_snapshot']['current_operational_risk']=='HIGH'
            durations.append(response['processing_duration_seconds']);ids.append({t['track_id'] for t in response['tracks']})
            if sequence<=4:
                assert receive(a,sequence)['data']['processed_frame_count']==sequence
            if sequence==4:a.close()
            if sequence==7:
                a=subscribe(sessions[0]);assert receive(a,7)['data']['processed_frame_count']==7
            # a deliberately does not read frames 8-12; b and processing continue.
            time.sleep(.36)
        capture.release()
        assert receive(a,12)['data']['processed_frame_count']==12
        assert isolated_states and all(e['session_id']==sessions[1] and e['data']['processed_frame_count']==0 for e in isolated_states)
        assert set.intersection(*ids), 'No continuous anonymous track'
        api('POST',f'/live/sessions/{sessions[0]}/stop')
        final=receive(b,terminal=True)
        assert all(x['resolved_at'] for x in final['data']['alerts'])
        assert 'alert.triggered' in types
        print(json.dumps(dict(verification='real sequential-frame simulation; physical webcam not verified',
            processed_frames=12,two_subscribers=True,reconnect=True,isolation=True,continuous_tracks=len(set.intersection(*ids)),
            delayed_reader_processing_continued=True,events=sorted(types),final_alerts_resolved=True,
            median_payload_bytes=statistics.median(sizes),maximum_payload_bytes=max(sizes),
            median_post_rest_receive_ms=statistics.median(latencies)*1000,
            warm_cv_median_ms=statistics.median(durations[1:])*1000),indent=2))
    finally:
        for ws in sockets:ws.close()
        for sid in sessions:api('POST',f'/live/sessions/{sid}/stop')
        for camera in cameras:api('DELETE','/cameras/'+camera['id'])
        connections.close()
        client.close()


if __name__=='__main__':main()
