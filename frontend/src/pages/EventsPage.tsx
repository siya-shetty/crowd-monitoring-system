import { useEffect, useState } from 'react'
import { downloadReport, eventStatuses, isoTime, localTime, operationsApi, type EventInput, type OperationalEvent } from '../services/operations'

const fresh = ():EventInput=>({name:'',description:'',location:'',status:'PLANNED',start_time:new Date().toISOString(),end_time:null})
export function EventsPage(){
  const [events,setEvents]=useState<OperationalEvent[]>([]),[loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[error,setError]=useState('')
  const [editing,setEditing]=useState<string|null>(null),[form,setForm]=useState<EventInput>(fresh)
  useEffect(()=>{let active=true;operationsApi<OperationalEvent[]>('/events').then(data=>{if(active)setEvents(data)}).catch(()=>{if(active)setError('Unable to load events.')}).finally(()=>{if(active)setLoading(false)});return()=>{active=false}},[])
  async function run(action:()=>Promise<unknown>){setBusy(true);setError('');try{await action();setEvents(await operationsApi<OperationalEvent[]>('/events'))}catch(e){setError(e instanceof Error?e.message:'Unable to update event')}finally{setBusy(false)}}
  function edit(item?:OperationalEvent){setEditing(item?.id??'new');setForm(item?{name:item.name,description:item.description,location:item.location,start_time:item.start_time,end_time:item.end_time,status:item.status}:fresh())}
  return <div className="page operations-page"><div className="page-heading"><div><p className="eyebrow">OPERATIONAL RECORDS</p><h1>Events</h1><p>Plan and document monitored activities. Event status is maintained by an operator.</p></div><button className="primary" disabled={busy} onClick={()=>edit()}>Create event</button></div>
    {error&&<p role="alert">{error}</p>}{loading&&<p role="status">Loading events...</p>}
    {editing&&<form className="card operations-form" aria-label="Event form" onSubmit={e=>{e.preventDefault();void run(async()=>{await operationsApi(editing==='new'?'/events':`/events/${editing}`,editing==='new'?'POST':'PUT',form);setEditing(null)})}}>
      <h2>{editing==='new'?'Create event':'Edit event'}</h2><label>Name<input required maxLength={120} value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></label>
      <label>Description<textarea maxLength={4000} value={form.description??''} onChange={e=>setForm({...form,description:e.target.value})}/></label>
      <label>Location / venue<input maxLength={200} value={form.location??''} onChange={e=>setForm({...form,location:e.target.value})}/></label>
      <label>Start time<input required type="datetime-local" value={localTime(form.start_time)} onChange={e=>setForm({...form,start_time:isoTime(e.target.value)})}/></label>
      <label>End time<input type="datetime-local" value={localTime(form.end_time)} onChange={e=>setForm({...form,end_time:e.target.value?isoTime(e.target.value):null})}/></label>
      <label>Status<select value={form.status} onChange={e=>setForm({...form,status:e.target.value as EventInput['status']})}>{eventStatuses.map(s=><option key={s}>{s}</option>)}</select></label>
      <p className="analytics-note">Times use your local timezone. Completing an event does not automatically resolve incidents.</p>
      <div className="operations-actions"><button className="primary" disabled={busy||!form.name.trim()}>Save event</button><button type="button" disabled={busy} onClick={()=>setEditing(null)}>Cancel</button></div>
    </form>}
    {!loading&&!error&&!events.length&&<article className="card"><h2>No events yet</h2><p>Create an operational event, then associate incidents with it.</p></article>}
    <p className="analytics-note">Latest 200 events by start time.</p><div className="operations-list">{events.map(item=><article className="card" key={item.id}><div className="section-title"><h2>{item.name}</h2><span className="status">{item.status}</span></div><p>{item.location||'No venue specified'}</p><p>{new Date(item.start_time).toLocaleString()} - {item.end_time?new Date(item.end_time).toLocaleString():'No end time'}</p><p className="operations-description">{item.description}</p>
      <div className="operations-actions"><button disabled={busy} onClick={()=>edit(item)}>Edit {item.name}</button><a href={`/incidents?event_id=${item.id}`}>View associated incidents</a><button disabled={busy} onClick={()=>void run(()=>downloadReport(`?event_id=${item.id}`))}>Export incident CSV</button><button disabled={busy} onClick={()=>{if(window.confirm('Delete this event? Incidents and their saved event labels will remain.'))void run(()=>operationsApi(`/events/${item.id}`,'DELETE'))}}>Delete {item.name}</button></div>
    </article>)}</div>
  </div>
}
