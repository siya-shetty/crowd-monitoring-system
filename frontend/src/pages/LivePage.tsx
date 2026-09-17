import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, type Point } from '../services/apiClient'
import { liveApi, sendFrame, type Camera, type CameraZone, type LiveConfig, type LiveEvent, type LiveSession } from '../services/live'
import { CameraConfiguration } from '../components/CameraConfiguration'
import { normalizedPoint } from '../lib/spatial'
import { cameraError } from '../lib/camera'

export function LivePage() {
  const [cameras,setCameras]=useState<Camera[]>([]), [cameraId,setCameraId]=useState(''), [name,setName]=useState('')
  const [config,setConfig]=useState<LiveConfig|null>(null), [session,setSession]=useState<LiveSession|null>(null), [history,setHistory]=useState<LiveSession[]>([]), [events,setEvents]=useState<LiveEvent[]>([])
  const [active,setActive]=useState(false), [busy,setBusy]=useState(false), [error,setError]=useState(''), [notice,setNotice]=useState('Camera is off')
  const [points,setPoints]=useState<Point[]>([]), [zones,setZones]=useState<CameraZone[]>([])
  const [aspect,setAspect]=useState(16/9)
  const video=useRef<HTMLVideoElement>(null), stream=useRef<MediaStream|null>(null), current=useRef<string|null>(null), mounted=useRef(false), generation=useRef(0)
  const upload=useRef<AbortController|null>(null), sequence=useRef(0)
  const release=useCallback(()=>{generation.current++;upload.current?.abort();stream.current?.getTracks().forEach(t=>t.stop());stream.current=null;if(video.current)video.current.srcObject=null;if(mounted.current)setActive(false)},[])
  useEffect(()=>{
    mounted.current=true
    void Promise.all([liveApi<Camera[]>('/cameras'),liveApi<LiveConfig>('/live/config')]).then(([c,s])=>{if(mounted.current){setCameras(c);setCameraId(c[0]?.id??'');setConfig(s)}}).catch(()=>{if(mounted.current)setError('Unable to load cameras. Refresh to try again.')})
    return()=>{mounted.current=false;release();const id=current.current;current.current=null;if(id)void liveApi(`/live/sessions/${id}/stop`,'POST').catch(()=>{})}
  },[release])
  useEffect(()=>{if(!cameraId)return;let valid=true;void liveApi<LiveSession[]>(`/cameras/${cameraId}/sessions`).then(items=>{if(valid){setHistory(items);setSession(items.find(s=>['STARTING','RUNNING','STOPPING'].includes(s.status))??null)}}).catch(()=>{if(valid)setError('Unable to load session history')});return()=>{valid=false}},[cameraId])
  const sessionId=session?.id
  const running=session?.status==='RUNNING'
  useEffect(()=>{
    if(!sessionId||!running)return
    let cancelled=false, timer:ReturnType<typeof setTimeout>
    const poll=async()=>{try{const [s,e]=await Promise.all([liveApi<LiveSession>(`/live/sessions/${sessionId}`),liveApi<LiveEvent[]>(`/live/sessions/${sessionId}/alerts`)]);if(!cancelled){setSession(s);setEvents(e);if(s.status!=='RUNNING'){release();current.current=null}}}catch{if(!cancelled)setError('Session snapshot unavailable. Stop monitoring or retry when connected.')}finally{if(!cancelled)timer=setTimeout(()=>void poll(),1000)}}
    void poll();return()=>{cancelled=true;clearTimeout(timer)}
  },[sessionId,running,release])
  useEffect(()=>{
    if(!sessionId||!running||!active||!config||current.current!==sessionId)return
    let cancelled=false, timer:ReturnType<typeof setTimeout>
    const controller=new AbortController();upload.current=controller
    const canvas=document.createElement('canvas')
    const tick=async()=>{
      try {
        const v=video.current
        if(v&&v.readyState>=2&&v.videoWidth&&document.visibilityState!=='hidden'){
          const scale=Math.min(config.capture_width/v.videoWidth,config.capture_height/v.videoHeight,1)
          canvas.width=Math.round(v.videoWidth*scale);canvas.height=Math.round(v.videoHeight*scale)
          canvas.getContext('2d')?.drawImage(v,0,0,canvas.width,canvas.height)
          const captured=Date.now()/1000
          const blob=await new Promise<Blob|null>(resolve=>canvas.toBlob(resolve,'image/jpeg',.8))
          if(blob&&!cancelled){if(blob.size>config.max_frame_bytes)throw new Error('Captured frame exceeds server size limit.');await sendFrame(sessionId,++sequence.current,captured,blob,controller.signal)}
        }
      } catch(e) {
        if(!cancelled&&!(e instanceof DOMException&&e.name==='AbortError')){
          if(e instanceof ApiError&&e.status===429)setNotice('Processing at capacity; excess frames are dropped.')
          else {setError(e instanceof ApiError?e.message:'Frame upload failed. Stop and restart monitoring.');release();const id=current.current;current.current=null;if(id)void liveApi<LiveSession>(`/live/sessions/${id}/stop`,'POST').then(s=>{if(mounted.current)setSession(s)}).catch(()=>{})}
        }
      } finally {if(!cancelled)timer=setTimeout(()=>void tick(),1000/config.target_fps)}
    }
    void tick();return()=>{cancelled=true;clearTimeout(timer);controller.abort()}
  },[sessionId,running,active,config,release])
  const run=async(action:()=>Promise<void>)=>{setBusy(true);setError('');try{await action()}catch(e){if(mounted.current)setError(e instanceof Error?e.message:'Request failed')}finally{if(mounted.current)setBusy(false)}}
  const startCamera=()=>run(async()=>{
    if(!window.isSecureContext)throw new Error('Camera capture requires HTTPS or localhost.')
    if(!navigator.mediaDevices?.getUserMedia)throw new Error('This browser does not support camera capture.')
    const token=++generation.current
    let media:MediaStream
    try{media=await navigator.mediaDevices.getUserMedia({video:{width:{ideal:960},height:{ideal:540}},audio:false})}catch(e){throw new Error(cameraError(e))}
    if(!mounted.current||token!==generation.current){media.getTracks().forEach(t=>t.stop());return}
    stream.current=media
    media.getVideoTracks().forEach(t=>{t.onended=()=>{release();setNotice('Camera disconnected. Stop this session before restarting.')}})
    try {if(video.current){video.current.srcObject=media;await video.current.play()}} catch {release();throw new Error('Local preview could not start. Try another browser or camera.')}
    if(!mounted.current||token!==generation.current){media.getTracks().forEach(t=>t.stop());return}
    setActive(true);setNotice('Camera active — local preview. Frames upload only while monitoring.')
  })
  const stop=()=>run(async()=>{release();const id=session?.id;current.current=null;if(id){const s=await liveApi<LiveSession>(`/live/sessions/${id}/stop`,'POST');setSession(s);setHistory(await liveApi<LiveSession[]>(`/cameras/${cameraId}/sessions`));setEvents(await liveApi<LiveEvent[]>(`/live/sessions/${id}/alerts`))}setNotice('Camera is off')})
  const start=()=>run(async()=>{
    const token=generation.current
    const s=await liveApi<LiveSession>(`/cameras/${cameraId}/sessions`,'POST')
    if(!mounted.current||token!==generation.current){await liveApi(`/live/sessions/${s.id}/stop`,'POST');return}
    sequence.current=0;current.current=s.id;setSession(s);setEvents([])
  })
  const locked=busy||active||!!session&&['STARTING','RUNNING','STOPPING'].includes(session.status)
  const metrics=session?.latest_snapshot
  return <div className="live-page"><header><p className="eyebrow">SENTINEL GRID / LIVE</p><h1>Live camera monitoring</h1><p>Browser camera · REST snapshots · Anonymous session-local tracking</p></header>
    {error&&<p role="alert" className="card">{error}</p>}
    <section className="card"><h2>Camera sources</h2>
      <label>Camera<select disabled={locked} value={cameraId} onChange={e=>{setCameraId(e.target.value);setPoints([]);setZones([]);setEvents([])}}><option value="">Choose camera</option>{cameras.map(c=><option value={c.id} key={c.id}>{c.name}{c.enabled?'':' (disabled)'}</option>)}</select></label>
      <form onSubmit={e=>{e.preventDefault();void run(async()=>{const c=await liveApi<Camera>('/cameras','POST',{name,source_type:'BROWSER'});setCameras(await liveApi<Camera[]>('/cameras'));setCameraId(c.id);setName('')})}}><label>New browser camera name<input required maxLength={100} disabled={locked} value={name} onChange={e=>setName(e.target.value)}/></label><button disabled={locked}>Register camera</button></form>
      {cameraId&&<><button disabled={locked} onClick={()=>void run(async()=>{const c=cameras.find(c=>c.id===cameraId)!;await liveApi(`/cameras/${cameraId}`,'PATCH',{enabled:!c.enabled});setCameras(await liveApi<Camera[]>('/cameras'))})}>Toggle camera enabled</button> <button disabled={locked} onClick={()=>void run(async()=>{await liveApi(`/cameras/${cameraId}`,'DELETE');const c=await liveApi<Camera[]>('/cameras');setCameras(c);setCameraId(c[0]?.id??'')})}>Delete camera and its history</button></>}
      <p>This camera belongs to your browser device. HTTPS (or localhost) and camera permission are required. Raw frames are processed transiently, not saved.</p>
    </section>
    <section className="card"><h2>Local preview</h2><p role="status">{notice}</p>
      <div className="live-preview" style={{aspectRatio:aspect}}><video ref={video} autoPlay muted playsInline onLoadedMetadata={()=>{if(video.current?.videoWidth)setAspect(video.current.videoWidth/video.current.videoHeight)}}/>
        {active&&<svg viewBox="0 0 1 1" preserveAspectRatio="none" aria-label="Draw camera zone" onClick={e=>{const p=normalizedPoint(e.clientX,e.clientY,e.currentTarget.getBoundingClientRect());if(p&&points.length<50)setPoints(v=>[...v,p])}}>{zones.filter(z=>z.active).map(z=><polygon key={z.id} points={z.polygon.map(p=>`${p.x},${p.y}`).join(' ')} fill="#38bdf833" stroke="#38bdf8" strokeWidth=".003"/>)}<polyline points={points.map(p=>`${p.x},${p.y}`).join(' ')} fill="#fbbf2422" stroke="#fbbf24" strokeWidth=".004"/>{points.map((p,i)=><circle key={i} cx={p.x} cy={p.y} r=".006" fill="#fbbf24"/>)}</svg>}
      </div>
      <button disabled={busy||active||!cameraId} onClick={()=>void startCamera()}>Start Camera</button> <button disabled={busy||!active||running||!cameras.find(c=>c.id===cameraId)?.enabled} onClick={()=>void start()}>Start Monitoring</button> <button disabled={busy||(!active&&!running)} onClick={()=>void stop()}>Stop Monitoring / Camera</button>
      <p>{config?`Target ${config.target_fps} FPS; one upload at a time. Snapshots refresh every second.`:'Loading capture settings…'} Background tabs pause capture.</p>
    </section>
    {session&&<section className="card"><h2>Session {session.status}{session.is_stale?' · OFFLINE / STALE':''}</h2><p>Processed {session.processed_frame_count} · Dropped {session.dropped_frame_count}</p>{session.error_summary&&<p>{session.error_summary}</p>}
      {metrics&&<><div className="live-metrics"><p>Observed crowd <strong>{metrics.observed_crowd_count}</strong></p><p>Crowd level <strong>{metrics.crowd_level}</strong></p><p>Image occupancy <strong>{(metrics.image_occupancy_ratio*100).toFixed(1)}%</strong></p><p>Concentration <strong>{metrics.crowd_concentration.toFixed(3)}</strong></p><p>Operational risk <strong>{metrics.current_operational_risk}</strong></p><p>Active alerts <strong>{metrics.active_alert_count}</strong></p></div><p>Last processing duration {(metrics.processing_duration_seconds*1000).toFixed(0)} ms. Rule-derived status does not predict danger.{session.is_stale?' Last observation is stale; current conditions are unknown.':''}</p>{Object.entries(metrics.zones).map(([id,z])=><p key={id}>{z.name}: {z.active_tracks_in_zone} active tracks</p>)}</>}
      <details><summary>Persisted session summary</summary><pre>{JSON.stringify(session.summary,null,2)}</pre></details>
      {events.map(e=><article key={e.id}><strong>{e.rule_snapshot.name} · {e.severity} · {e.resolved_at?'Resolved':'Active'}</strong><details><summary>Alert evidence</summary><pre>{JSON.stringify(e.evidence,null,2)}</pre></details></article>)}
    </section>}
    {cameraId&&<CameraConfiguration key={cameraId} cameraId={cameraId} points={points} clear={()=>setPoints([])} onZones={setZones}/>}
    {!!history.length&&<section className="card"><h2>Session history</h2>{history.map(s=><p key={s.id}><button disabled={running} onClick={()=>{setSession(s);void liveApi<LiveEvent[]>(`/live/sessions/${s.id}/alerts`).then(setEvents).catch(()=>setError('Unable to load alert history'))}}>{s.status} · {s.processed_frame_count} frames · {s.id.slice(0,8)}</button></p>)}</section>}
  </div>
}
