import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { getAnalytics, getSessionAnalytics, type Analytics, type SessionAnalytics, type TimeRange } from '../services/analytics'

const number = (value:number|null|undefined) => value == null ? 'Unavailable' : value.toLocaleString(undefined,{maximumFractionDigits:2})
const percent = (value:number|null) => value == null ? 'Unavailable' : `${(value*100).toFixed(1)}%`
const date = (value:string|null) => value ? new Date(value).toLocaleString() : 'Unavailable'
const distribution = (values:Record<string,number>) => Object.entries(values).map(([name,count])=>({name,count}))

export function AnalyticsPage(){
  const [range,setRange]=useState<TimeRange>('30d'),[data,setData]=useState<Analytics|null>(null),[error,setError]=useState('')
  const [selected,setSelected]=useState<string|null>(null),[session,setSession]=useState<SessionAnalytics|null>(null),[detailError,setDetailError]=useState('')
  useEffect(()=>{let active=true
    getAnalytics(range).then(result=>{if(active)setData(result)}).catch(()=>{if(active)setError('Unable to load analytics. Please try again.')})
    return()=>{active=false}
  },[range])
  useEffect(()=>{if(!selected)return;let active=true
    getSessionAnalytics(selected).then(result=>{if(active)setSession(result)}).catch(()=>{if(active)setDetailError('Unable to load session details.')})
    return()=>{active=false}
  },[selected])
  function selectRange(value:TimeRange){setRange(value);setData(null);setError('');setSelected(null);setSession(null);setDetailError('')}
  return <div className="page analytics-page">
    <div className="page-heading"><div><p className="eyebrow">HISTORICAL INTELLIGENCE</p><h1>Analytics</h1><p>Stored observations, operational alerts, and monitoring history.</p></div>
      <label>Time range <select value={range} onChange={e=>selectRange(e.target.value as TimeRange)}><option value="7d">7 days</option><option value="30d">30 days</option><option value="all">All time</option></select></label></div>
    <p className="analytics-note">Filters use video upload and session start times (UTC), including their full stored results. Counts describe observations of anonymous tracks, never unique people.</p>
    {error?<p role="alert">{error}</p>:!data?<p role="status">Loading analytics…</p>:<>
      <div className="metrics">
        <Metric label="Analyzed videos" value={data.total_analyzed_videos}/><Metric label="Live sessions" value={data.total_live_sessions}/>
        <Metric label="Completed sessions" value={data.session_statuses.STOPPED??0}/><Metric label="Failed sessions" value={data.session_statuses.FAILED??0}/>
        <Metric label="Alert events" value={data.alerts.total}/><Metric label="Completed videos" value={data.video_statuses.completed??0}/>
      </div>
      {!data.total_analyzed_videos&&!data.total_live_sessions&&<article className="card"><h2>No analytics yet</h2><p>Analyze an uploaded video or run a monitoring session to build history in this range.</p></article>}
      <div className="dashboard-grid">{(['video','live'] as const).map(source=><article className="card" key={source}><p className="eyebrow">{source==='video'?'UPLOADED VIDEO':'LIVE MONITORING'}</p><h2>Observed crowd count</h2><dl className="tracking-metrics">
        <Stat label="Average observed crowd count" value={number(data[source].average_count)}/><Stat label="Peak observed crowd count" value={number(data[source].peak_count)}/>
        <Stat label="Processed observations" value={number(data[source].observations)}/>
        {source==='video'&&<><Stat label="Average image occupancy" value={percent(data.video.average_image_occupancy)}/><Stat label="Average image-space concentration" value={percent(data.video.average_image_space_concentration)}/></>}
      </dl><p className="analytics-note">{source==='video'?'Weighted by processed crowd frames. Image metrics are uncalibrated image-space measurements.':'Weighted by processed live frames. Historical image occupancy and concentration are unavailable.'}</p>
      <p>Peak cohort date (UTC): {data.peak_periods[source]?.date??'Unavailable'}</p>
      <Distribution label={source==='video'?'Crowd levels · processed frames':'Maximum crowd levels · sessions'} values={source==='video'?data.video.crowd_levels??{}:data.live.maximum_crowd_levels??{}}/></article>)}</div>
      <div className="dashboard-grid">
        <article className="card chart" aria-label="Crowd history"><h2>Observed crowd history</h2><p className="analytics-note">Daily cohort averages, grouped by upload / session start date. Latest 90 populated dates; gaps are not zero.</p>
          <ResponsiveContainer width="100%" height={250}><LineChart data={data.history}><CartesianGrid strokeDasharray="3 3" stroke="#294055"/><XAxis dataKey="date"/><YAxis/><Tooltip/><Legend/><Line type="linear" dataKey="video_average" name="Uploaded video" stroke="#2dd4bf" connectNulls={false}/><Line type="linear" dataKey="live_average" name="Live sessions" stroke="#a78bfa" connectNulls={false}/></LineChart></ResponsiveContainer>
        </article>
        <article className="card chart" aria-label="Alert severity"><h2>Alerts by severity</h2><Bars values={data.alerts.by_severity}/><Distribution label="Alert types" values={data.alerts.by_type}/></article>
        <article className="card chart" aria-label="Operational risk distribution"><h2>Rule-derived operational risk</h2><p className="analytics-note">Maximum per analyzed video / session. Sessions with no stored risk are excluded.</p>
          <ResponsiveContainer width="100%" height={240}><BarChart data={['NORMAL','ELEVATED','HIGH','CRITICAL'].map(name=>({name,video:data.video.risk_distribution[name]??0,live:data.live.risk_distribution[name]??0}))}><XAxis dataKey="name"/><YAxis allowDecimals={false}/><Tooltip/><Legend/><Bar dataKey="video" name="Uploaded video" fill="#2dd4bf"/><Bar dataKey="live" name="Live sessions" fill="#a78bfa"/></BarChart></ResponsiveContainer>
        </article>
        <article className="card"><h2>Uploaded-video zones</h2><p className="analytics-note">Latest 50 zones. Each row belongs to one video; counts are not summed across zones.</p>{data.video_zones.length?<div className="analytics-table"><table><thead><tr><th>Zone</th><th>Video</th><th>Average count</th><th>Peak count</th></tr></thead><tbody>{data.video_zones.map(z=><tr key={z.id}><td>{z.name}</td><td>{z.video_id.slice(0,8)}</td><td>{number(z.average_count)}</td><td>{number(z.peak_count)}</td></tr>)}</tbody></table></div>:<p>No stored zone activity.</p>}</article>
      </div>
      <article className="card"><div className="section-title"><h2>Recent monitoring sessions</h2><span>Latest 30</span></div>{!data.sessions.length?<p>No sessions in this range.</p>:data.sessions.map(s=><article className="analytics-session" key={s.id}><div><h3>{s.camera_name}</h3><span className="status">{s.status}</span></div><p className="analytics-note">{date(s.started_at)}</p><p>{s.summary??'Session is in progress. Metrics reflect persisted observations so far.'}</p><button className="primary" onClick={()=>{if(selected===s.id)return;setSelected(s.id);setSession(null);setDetailError('')}}>Inspect session {s.id.slice(0,8)}</button></article>)}</article>
      {selected&&<section className="card analytics-detail" aria-label="Session details"><div className="section-title"><h2>Session details</h2><button onClick={()=>{setSelected(null);setSession(null)}}>Close details</button></div>{detailError?<p role="alert">{detailError}</p>:!session?<p role="status">Loading session…</p>:<>
        <h3>{session.camera_name} · {session.status}</h3><p>{session.summary??'Session is in progress.'}</p><p>Started: {date(session.started_at)} · Ended: {date(session.stopped_at)}</p><dl className="tracking-metrics">
          <Stat label="Duration (minutes)" value={number(session.duration_seconds==null?null:session.duration_seconds/60)}/><Stat label="Processed frames" value={number(session.processed_frames)}/><Stat label="Dropped frames" value={number(session.dropped_frames)}/>
          <Stat label="Average observed crowd count" value={number(session.average_count)}/><Stat label="Peak observed crowd count" value={number(session.peak_count)}/><Stat label="Maximum crowd level" value={session.maximum_crowd_level??'Unavailable'}/>
          <Stat label="Maximum rule-derived operational risk" value={session.maximum_operational_risk??'Unavailable'}/><Stat label="Final stored operational risk" value={session.final_operational_risk??'Unavailable'}/>
        </dl><p className="analytics-note">Final risk resets to NORMAL when a session closes. Maximum risk preserves the observed history. Peak image occupancy and concentration were not persisted.</p>
        <h3>Zone activity · peak simultaneous anonymous tracks</h3>{session.zones.length?session.zones.map(z=><p key={z.id}>{z.name}: {number(z.peak_count)}</p>):<p>No stored zones.</p>}
        <h3>Alert history · {session.alerts.total} events</h3><Distribution label="Severity" values={session.alerts.by_severity}/><Distribution label="Rule types" values={session.alerts.by_type}/>
        <p className="analytics-note">Latest 100 events; breakdowns include all session events.</p>{session.alert_history?.length?session.alert_history.map(e=><article className="analytics-session" key={e.id}><strong>{e.rule_name} · {e.severity}</strong><p>{e.rule_type} {e.zone_name&&`· ${e.zone_name}`}</p><p>{date(e.created_at)} · Resolved: {date(e.resolved_at)}</p></article>):<p>No alert events.</p>}
      </>}</section>}
    </>}
  </div>
}
function Metric({label,value}:{label:string;value:number}){return <article className="metric card"><div><p>{label}</p><strong>{number(value)}</strong></div></article>}
function Stat({label,value}:{label:string;value:string}){return <div><dt>{label}</dt><dd>{value}</dd></div>}
function Distribution({label,values}:{label:string;values:Record<string,number>}){return <div className="analytics-distribution"><h3>{label}</h3>{Object.keys(values).length?Object.entries(values).map(([name,count])=><span key={name}>{name}: <strong>{count}</strong></span>):<p>No stored observations.</p>}</div>}
function Bars({values}:{values:Record<string,number>}){return <ResponsiveContainer width="100%" height={240}><BarChart data={distribution(values)}><XAxis dataKey="name"/><YAxis allowDecimals={false}/><Tooltip/><Bar dataKey="count" name="Alert events" fill="#fbbf24" radius={[5,5,0,0]}/></BarChart></ResponsiveContainer>}

