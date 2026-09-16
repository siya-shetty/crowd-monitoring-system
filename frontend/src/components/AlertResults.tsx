import { useEffect, useState } from 'react'
import { listZones, type Zone } from '../services/apiClient'
import { deleteRule, getAlertSummary, listAlerts, listRules, ruleTypes, saveRule, toggleRule, type AlertEvent, type AlertSummary, type Rule, type RuleInput, type RuleType, type Severity } from '../services/alerts'

const typeLabels:Record<RuleType,string> = {CROWD_COUNT_ABOVE:'Observed crowd count',CROWD_LEVEL_AT_LEAST:'Operational crowd level',SUDDEN_CROWD_INCREASE:'Sudden crowd increase',ZONE_COUNT_ABOVE:'Zone count',ZONE_PRESENCE:'Zone presence'}

export function AlertEvents({events,videoNames={}}:{events:AlertEvent[];videoNames?:Record<string,string>}) {
  const [severity,setSeverity]=useState('')
  const [kind,setKind]=useState('')
  const filtered=events.filter(e=>(!severity||e.severity===severity)&&(!kind||e.rule_type===kind))
  return <section aria-label="Alert history">
    <h4>Historical alert events</h4>
    <label>Filter severity <select value={severity} onChange={e=>setSeverity(e.target.value)}><option value="">All severities</option>{['INFO','WARNING','CRITICAL'].map(s=><option key={s}>{s}</option>)}</select></label>
    <label>Filter rule type <select value={kind} onChange={e=>setKind(e.target.value)}><option value="">All rule types</option>{ruleTypes.map(t=><option key={t} value={t}>{typeLabels[t]}</option>)}</select></label>
    {!filtered.length&&<p>No alert events match. This does not establish safety.</p>}
    {filtered.map(e=><article className="card alert-event" key={e.id}>
      <h4>{e.rule_name} · {e.severity}</h4><p>{typeLabels[e.rule_type]} · {e.state} {e.rule_id===null?'· Deleted rule history':''}</p>
      <p>Video: {videoNames[e.video_id]??e.video_id} · {e.evidence.zone_name??'Whole video'}</p>
      <p>Condition start {e.condition_start_seconds.toFixed(2)} s · Trigger {e.trigger_seconds.toFixed(2)} s · Last qualifying observation {e.end_seconds.toFixed(2)} s</p>
      <details><summary>Why this alert fired</summary>
        <p>{e.rule_type==='ZONE_PRESENCE'?'Presence detected in monitored zone. ':''}{e.evidence.metric}: {e.evidence.trigger_value} at trigger, against configured threshold {e.evidence.threshold}. Peak: {e.evidence.peak_value}.</p>
        <p>Required duration: {e.evidence.minimum_duration_seconds} s. Observed qualifying interval: {e.evidence.observed_duration_seconds.toFixed(2)} s. Maximum allowed observation gap: {e.evidence.maximum_gap_seconds} s. Closure: {e.evidence.closure}.</p>
        {e.evidence.baseline_seconds!==null&&<p>Lookback baseline: {e.evidence.baseline_count} tracks at {e.evidence.baseline_seconds} s; current count: {e.evidence.current_count}.</p>}
      </details>
    </article>)}
  </section>
}

export function AlertResults({videoId}:{videoId:string}) {
  const [rules,setRules]=useState<Rule[]>([]), [events,setEvents]=useState<AlertEvent[]>([]), [zones,setZones]=useState<Zone[]>([])
  const [summary,setSummary]=useState<AlertSummary|null>(null), [error,setError]=useState(''), [busy,setBusy]=useState(false)
  const [editing,setEditing]=useState<string|null>(null), [name,setName]=useState(''), [description,setDescription]=useState('')
  const [kind,setKind]=useState<RuleType>('CROWD_COUNT_ABOVE'), [severity,setSeverity]=useState<Severity>('WARNING')
  const [threshold,setThreshold]=useState(1), [level,setLevel]=useState('HIGH'), [duration,setDuration]=useState(0), [gap,setGap]=useState(1), [lookback,setLookback]=useState(3), [zoneId,setZoneId]=useState(''), [enabled,setEnabled]=useState(true)
  const zone=kind.startsWith('ZONE_')
  const reload=async()=>{const [r,e,s,z]=await Promise.all([listRules(videoId),listAlerts(videoId),getAlertSummary(videoId),listZones(videoId)]);setRules(r);setEvents(e);setSummary(s);setZones(z)}
  useEffect(()=>{let active=true;void Promise.all([listRules(videoId),listAlerts(videoId),getAlertSummary(videoId),listZones(videoId)]).then(([r,e,s,z])=>{if(active){setRules(r);setEvents(e);setSummary(s);setZones(z)}}).catch(()=>{if(active)setError('Unable to load alert rules and history.')});return()=>{active=false}},[videoId])
  const run=async(action:()=>Promise<unknown>)=>{setBusy(true);setError('');try{await action();await reload()}catch(e){setError(e instanceof Error?e.message:'Unable to update alerts')}finally{setBusy(false)}}
  const begin=(r?:Rule)=>{setEditing(r?.id??'new');setName(r?.name??'');setDescription(r?.description??'');setKind(r?.rule_type??'CROWD_COUNT_ABOVE');setSeverity(r?.severity??'WARNING');setZoneId(r?.zone_id??'');setEnabled(r?.enabled??true);setThreshold(Number(r?.configuration.threshold??r?.configuration.increase_count??r?.configuration.minimum_presence_count??1));setLevel(String(r?.configuration.minimum_level??'HIGH'));setDuration(Number(r?.configuration.minimum_duration_seconds??0));setGap(Number(r?.configuration.maximum_gap_seconds??1));setLookback(Number(r?.configuration.lookback_seconds??3))}
  const condition=kind==='CROWD_LEVEL_AT_LEAST'?`operational crowd level is at least ${level}`:kind==='SUDDEN_CROWD_INCREASE'?`observed crowd count increases by at least ${threshold} over approximately ${lookback} seconds`:zone?`at least ${threshold} anonymous tracked persons are observed in ${zones.find(z=>z.id===zoneId)?.name??'the selected zone'}`:`observed crowd count is at least ${threshold}`
  const save=()=>run(async()=>{const configuration:Record<string,number|string>={minimum_duration_seconds:duration,maximum_gap_seconds:gap};if(kind==='CROWD_LEVEL_AT_LEAST')configuration.minimum_level=level;else if(kind==='SUDDEN_CROWD_INCREASE'){configuration.increase_count=threshold;configuration.lookback_seconds=lookback}else configuration[kind==='ZONE_PRESENCE'?'minimum_presence_count':'threshold']=threshold;const payload:RuleInput={name:name.trim(),description:description.trim()||null,rule_type:kind,scope:zone?'ZONE':'VIDEO',zone_id:zone?zoneId:null,severity,enabled,configuration};await saveRule(videoId,payload,editing==='new'?undefined:editing!);setEditing(null)})
  return <section className="tracking-results alert-results" aria-label="Alert Rules">
    <h3>Alert Rules</h3><p>User-configured operational conditions evaluated retrospectively from stored measurements. No inference is rerun.</p>
    <p>Severity prioritizes review; operational risk is rule-derived and does not predict accidents. Disabled and deleted rules retain historical events and their risk contribution.</p>
    {error&&<p role="alert">{error}</p>}
    {summary&&<div role="status"><strong>Maximum operational risk: {summary.maximum_operational_risk}</strong><p>{summary.total_events} alert events · {summary.enabled_rules}/{summary.configured_rules} enabled rules</p><p>INFO {summary.events_by_severity.INFO} · WARNING {summary.events_by_severity.WARNING} · CRITICAL {summary.events_by_severity.CRITICAL}</p></div>}
    <button disabled={busy} onClick={()=>begin()}>Create alert rule</button> <button disabled={busy} onClick={()=>void run(async()=>{})}>Refresh alerts and zones</button>
    {!rules.length&&<p>No rules configured.</p>}
    {rules.map(r=><div className="alert-rule" key={r.id}><strong>{r.name}</strong> · {r.severity} · {r.enabled?'Enabled':'Disabled'} · {events.filter(e=>e.rule_id===r.id).length} events <button disabled={busy} onClick={()=>begin(r)}>Edit {r.name}</button> <button disabled={busy} onClick={()=>void run(()=>toggleRule(videoId,r.id,!r.enabled))}>{r.enabled?'Disable':'Enable'} {r.name}</button> <button disabled={busy} onClick={()=>void run(()=>deleteRule(videoId,r.id))}>Delete {r.name}</button></div>)}
    {editing&&<form className="alert-form" onSubmit={e=>{e.preventDefault();void save()}}>
      <label>Rule name<input required maxLength={100} value={name} onChange={e=>setName(e.target.value)}/></label>
      <label>Description<input maxLength={1000} value={description} onChange={e=>setDescription(e.target.value)}/></label>
      <label>Rule type<select value={kind} onChange={e=>setKind(e.target.value as RuleType)}>{ruleTypes.map(t=><option key={t} value={t}>{typeLabels[t]}</option>)}</select></label>
      <p>Scope: {zone?'ZONE':'VIDEO'}</p>
      {zone&&<label>Monitoring zone<select required value={zoneId} onChange={e=>setZoneId(e.target.value)}><option value="">Choose a zone</option>{zones.map(z=><option key={z.id} value={z.id}>{z.name}{z.active?'':' (inactive; no measurements)'}</option>)}</select></label>}
      {kind==='CROWD_LEVEL_AT_LEAST'?<label>Minimum crowd level<select value={level} onChange={e=>setLevel(e.target.value)}>{['LOW','MODERATE','HIGH','VERY_HIGH'].map(l=><option key={l}>{l}</option>)}</select></label>:<label>{kind==='SUDDEN_CROWD_INCREASE'?'Increase count':kind==='ZONE_PRESENCE'?'Minimum presence count':'Count threshold'}<input type="number" required min={1} step={1} value={threshold} onChange={e=>setThreshold(e.target.valueAsNumber)}/></label>}
      {kind==='SUDDEN_CROWD_INCREASE'&&<label>Lookback seconds<input type="number" required min={0.001} step="any" value={lookback} onChange={e=>setLookback(e.target.valueAsNumber)}/></label>}
      <label>Minimum duration seconds<input type="number" required min={0} step="any" value={duration} onChange={e=>setDuration(e.target.valueAsNumber)}/></label>
      <label>Maximum observation gap seconds<input type="number" required min={0.001} step="any" value={gap} onChange={e=>setGap(e.target.valueAsNumber)}/></label>
      <label>Severity<select value={severity} onChange={e=>setSeverity(e.target.value as Severity)}>{['INFO','WARNING','CRITICAL'].map(s=><option key={s}>{s}</option>)}</select></label>
      <label><input type="checkbox" checked={enabled} onChange={e=>setEnabled(e.target.checked)}/>Enabled</label>
      <p>Trigger {severity} when {condition} for {duration} seconds.</p>
      <button disabled={busy||!name.trim()} type="submit">Save alert rule</button> <button type="button" disabled={busy} onClick={()=>setEditing(null)}>Cancel</button>
    </form>}
    <AlertEvents events={events}/>
  </section>
}

