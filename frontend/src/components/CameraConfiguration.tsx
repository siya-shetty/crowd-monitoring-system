import { useEffect, useState } from 'react'
import { liveApi, type CameraRule, type CameraZone } from '../services/live'
import { ruleTypes, type RuleType, type Severity } from '../services/alerts'
import type { Point } from '../services/apiClient'

export function CameraConfiguration({cameraId,points,clear,onZones}:{cameraId:string;points:Point[];clear:()=>void;onZones:(zones:CameraZone[])=>void}) {
  const [zones,setZones]=useState<CameraZone[]>([]), [rules,setRules]=useState<CameraRule[]>([])
  const [zoneName,setZoneName]=useState(''), [name,setName]=useState(''), [kind,setKind]=useState<RuleType>('CROWD_COUNT_ABOVE')
  const [severity,setSeverity]=useState<Severity>('WARNING'), [threshold,setThreshold]=useState(1), [duration,setDuration]=useState(0), [gap,setGap]=useState(2), [lookback,setLookback]=useState(3), [level,setLevel]=useState('HIGH'), [zoneId,setZoneId]=useState('')
  const [error,setError]=useState(''), [busy,setBusy]=useState(false)
  const base=`/cameras/${cameraId}`
  const reload=async()=>{const [z,r]=await Promise.all([liveApi<CameraZone[]>(base+'/zones'),liveApi<CameraRule[]>(base+'/alert-rules')]);setZones(z);onZones(z);setRules(r)}
  useEffect(()=>{let active=true;void Promise.all([liveApi<CameraZone[]>(base+'/zones'),liveApi<CameraRule[]>(base+'/alert-rules')]).then(([z,r])=>{if(active){setZones(z);onZones(z);setRules(r)}}).catch(()=>{if(active)setError('Unable to load camera configuration')});return()=>{active=false}},[base,onZones])
  const run=async(action:()=>Promise<unknown>)=>{setBusy(true);setError('');try{await action();await reload()}catch(e){setError(e instanceof Error?e.message:'Configuration failed')}finally{setBusy(false)}}
  const zone=kind.startsWith('ZONE_')
  const saveRule=()=>run(async()=>{
    const configuration:Record<string,number|string>={minimum_duration_seconds:duration,maximum_gap_seconds:gap}
    if(kind==='CROWD_LEVEL_AT_LEAST')configuration.minimum_level=level
    else if(kind==='SUDDEN_CROWD_INCREASE'){configuration.increase_count=threshold;configuration.lookback_seconds=lookback}
    else configuration[kind==='ZONE_PRESENCE'?'minimum_presence_count':'threshold']=threshold
    await liveApi(base+'/alert-rules','POST',{name,rule_type:kind,scope:zone?'ZONE':'CAMERA',zone_id:zone?zoneId:null,severity,enabled:true,configuration});setName('')
  })
  return <section className="card"><h2>Camera zones & rules</h2><p>Changes apply to the next monitoring session. Draw polygon vertices on the local preview; boundaries count inside.</p>
    {error&&<p role="alert">{error}</p>}
    <form onSubmit={e=>{e.preventDefault();void run(async()=>{await liveApi(base+'/zones','POST',{name:zoneName,polygon:points,active:true});clear();setZoneName('')})}}>
      <label>Zone name<input required maxLength={100} value={zoneName} onChange={e=>setZoneName(e.target.value)}/></label>
      <p>{points.length} polygon vertices</p><button disabled={busy||points.length<3}>Save drawn zone</button><button type="button" onClick={clear}>Clear drawing</button>
    </form>
    {zones.map(z=><p key={z.id}>{z.name} · {z.active?'Enabled':'Disabled'} <button disabled={busy} onClick={()=>void run(()=>liveApi(base+'/zones/'+z.id,'PATCH',{active:!z.active}))}>{z.active?'Disable':'Enable'} zone {z.name}</button> <button disabled={busy} onClick={()=>void run(()=>liveApi(base+'/zones/'+z.id,'DELETE'))}>Delete zone {z.name}</button></p>)}
    <h3>Alert rules</h3>
    {rules.map(r=><p key={r.id}>{r.name} · {r.severity} · {r.enabled?'Enabled':'Disabled'} <button disabled={busy} onClick={()=>void run(()=>{const {id,camera_id,...body}=r;void camera_id;return liveApi(base+'/alert-rules/'+id,'PUT',{...body,enabled:!r.enabled})})}>Toggle rule {r.name}</button> <button disabled={busy} onClick={()=>void run(()=>liveApi(base+'/alert-rules/'+r.id,'DELETE'))}>Delete rule {r.name}</button></p>)}
    <form className="alert-form" onSubmit={e=>{e.preventDefault();void saveRule()}}>
      <label>Rule name<input required maxLength={100} value={name} onChange={e=>setName(e.target.value)}/></label>
      <label>Rule type<select value={kind} onChange={e=>setKind(e.target.value as RuleType)}>{ruleTypes.map(t=><option key={t}>{t}</option>)}</select></label>
      <label>Severity<select value={severity} onChange={e=>setSeverity(e.target.value as Severity)}>{['INFO','WARNING','CRITICAL'].map(s=><option key={s}>{s}</option>)}</select></label>
      {zone&&<label>Rule zone<select required value={zoneId} onChange={e=>setZoneId(e.target.value)}><option value="">Choose zone</option>{zones.map(z=><option value={z.id} key={z.id}>{z.name}</option>)}</select></label>}
      {kind==='CROWD_LEVEL_AT_LEAST'?<label>Minimum level<select value={level} onChange={e=>setLevel(e.target.value)}>{['LOW','MODERATE','HIGH','VERY_HIGH'].map(l=><option key={l}>{l}</option>)}</select></label>:<label>Count threshold<input type="number" min={1} required value={threshold} onChange={e=>setThreshold(Number(e.target.value))}/></label>}
      <label>Sustained duration (seconds)<input type="number" min={0} step="0.1" required value={duration} onChange={e=>setDuration(Number(e.target.value))}/></label>
      <label>Maximum observation gap (seconds)<input type="number" min={0.1} step="0.1" required value={gap} onChange={e=>setGap(Number(e.target.value))}/></label>
      {kind==='SUDDEN_CROWD_INCREASE'&&<label>Lookback seconds<input type="number" min={0.1} max={60} step="0.1" value={lookback} onChange={e=>setLookback(Number(e.target.value))}/></label>}
      <p>Trigger {severity} when {kind==='CROWD_LEVEL_AT_LEAST'?`crowd level is at least ${level}`:kind==='SUDDEN_CROWD_INCREASE'?`count increases by at least ${threshold} over approximately ${lookback} seconds`:`${zone?'zone':'camera'} count is at least ${threshold}`} for {duration} seconds, allowing gaps up to {gap} seconds.</p>
      <button disabled={busy}>Create live rule</button>
    </form>
  </section>
}
