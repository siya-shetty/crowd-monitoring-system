"""Real-frame live transport simulation. Run against disposable local services.

Usage: python scripts/verify_live.py VIDEO OUTPUT_JSON [--api http://127.0.0.1:8010]
No images, credentials, or tokens are written; OUTPUT_JSON must be in ignored storage.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import statistics
import time
import uuid
import cv2
import httpx


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('video',type=Path);parser.add_argument('output',type=Path)
    parser.add_argument('--api',default='http://127.0.0.1:8010')
    args=parser.parse_args()
    storage=Path(__file__).resolve().parents[2]/'storage'
    if not args.output.resolve().is_relative_to(storage.resolve()):
        parser.error('Verification output must be under the repository ignored storage directory')
    client=httpx.Client(base_url=args.api,timeout=60)
    email='live-'+uuid.uuid4().hex+'@example.com';password=uuid.uuid4().hex+'aA1!'
    def api(method,path,**kwargs):
        response=client.request(method,'/api/v1'+path,**kwargs)
        response.raise_for_status()
        return response.json() if response.status_code!=204 else None
    api('POST','/auth/register',json=dict(email=email,password=password,full_name='Live verification'))
    token=api('POST','/auth/login',json=dict(email=email,password=password))['access_token']
    client.headers['Authorization']='Bearer '+token
    camera=api('POST','/cameras',json={'name':'Real-frame live transport simulation'})
    base='/cameras/'+camera['id'];session=None
    try:
        zones=[]
        for name,coords in [('Active',[(0,0),(1,0),(1,1),(0,1)]),('Quiet',[(0,0),(.04,0),(.04,.04),(0,.04)])]:
            zones.append(api('POST',base+'/zones',json={'name':name,'polygon':[dict(x=x,y=y) for x,y in coords]}))
        for body in [dict(name='Trigger',scope='CAMERA',rule_type='CROWD_COUNT_ABOVE',severity='WARNING',configuration={'threshold':1,'minimum_duration_seconds':1.,'maximum_gap_seconds':3.}),
                     dict(name='Nontrigger',scope='CAMERA',rule_type='CROWD_COUNT_ABOVE',severity='CRITICAL',configuration={'threshold':999}),
                     dict(name='Zone presence',scope='ZONE',zone_id=zones[0]['id'],rule_type='ZONE_PRESENCE',severity='INFO',configuration={'maximum_gap_seconds':3.})]:
            api('POST',base+'/alert-rules',json=body)
        session=api('POST',base+'/sessions');url='/live/sessions/'+session['id']
        capture=cv2.VideoCapture(str(args.video));observations=[];sequence=0;last_image=None
        for _ in range(20):
            ok,frame=capture.read()
            if not ok:break
            sequence+=1
            last_image=cv2.imencode('.jpg',frame,[cv2.IMWRITE_JPEG_QUALITY,80])[1].tobytes()
            observation=api('POST',url+'/frames',content=last_image,headers={'Content-Type':'image/jpeg'},params={'sequence':sequence,'capture_timestamp':time.time()})
            observations.append(observation)
            time.sleep(.36)
        capture.release()
        assert len(observations)>=10
        # Concurrent burst exercises actual capacity rather than mocked delays.
        def burst(i):
            return client.post('/api/v1'+url+'/frames',content=last_image,headers={'Content-Type':'image/jpeg'},params={'sequence':sequence+i+1,'capture_timestamp':time.time()}).status_code
        with ThreadPoolExecutor(max_workers=8) as pool:
            burst_status=list(pool.map(burst,range(12)))
        snapshot=api('GET',url)
        events=api('GET',url+'/alerts')
        assert any(e['rule_snapshot']['name']=='Trigger' for e in events)
        assert not any(e['rule_snapshot']['name']=='Nontrigger' for e in events)
        assert any(e['rule_snapshot']['name']=='Zone presence' for e in events)
        assert any(e['evidence']['observed_duration_seconds']>=1 for e in events if e['rule_snapshot']['name']=='Trigger')
        assert snapshot['dropped_frame_count']>0 and 429 in burst_status
        assert snapshot['latest_snapshot']['current_operational_risk']=='HIGH'
        ids=Counter(t['track_id'] for o in observations for t in o['tracks'])
        assert any(n>1 for n in ids.values())
        active=max(o['zones'][zones[0]['id']]['active_tracks_in_zone'] for o in observations)
        quiet=max(o['zones'][zones[1]['id']]['active_tracks_in_zone'] for o in observations)
        assert active>0 and quiet==0
        stopped=api('POST',url+'/stop')
        assert stopped['status']=='STOPPED'
        assert api('POST',url+'/stop')['summary']==stopped['summary']
        rejected=client.post('/api/v1'+url+'/frames',content=last_image,headers={'Content-Type':'image/jpeg'},params={'sequence':999,'capture_timestamp':time.time()})
        assert rejected.status_code==409
        closed=api('GET',url+'/alerts')
        assert all(e['resolved_at'] is not None for e in closed)
        refreshed=api('GET',url)
        assert refreshed['summary']==stopped['summary'] and refreshed['recent_observations']==[]
        durations=[o['processing_duration_seconds'] for o in observations]
        report=dict(verification='real-frame live transport simulation',physical_webcam_verified=False,
            resolution=[observations[0]['width'],observations[0]['height']],model='yolo11n.pt',
            processed_frames=refreshed['processed_frame_count'],track_observation_counts=dict(ids),
            multiple_frame_continuity=True,active_zone_peak=active,quiet_zone_peak=quiet,
            burst_responses=dict(Counter(burst_status)),dropped_frames=refreshed['dropped_frame_count'],
            median_processing_seconds=statistics.median(durations),average_processing_seconds=statistics.mean(durations),
            approximate_processing_fps=1/statistics.median(durations),configured_target_fps=api('GET','/live/config')['target_fps'],
            risk_before_stop=snapshot['latest_snapshot']['current_operational_risk'],events=closed,
            persisted_summary=refreshed['summary'],stop_released_backend_buffer=True)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2))
        print(json.dumps({k:v for k,v in report.items() if k not in ('events','persisted_summary')},indent=2))
    finally:
        if session:api('POST','/live/sessions/'+session['id']+'/stop')
        api('DELETE',base)


if __name__=='__main__':main()
