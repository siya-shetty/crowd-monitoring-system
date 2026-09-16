import { useEffect, useState } from 'react'
import { AlertEvents } from '../components/AlertResults'
import { listAlerts, type AlertEvent } from '../services/alerts'
import { listVideos } from '../services/apiClient'

export function AlertsPage(){
  const [events,setEvents]=useState<AlertEvent[]>([]),[names,setNames]=useState<Record<string,string>>({}),[error,setError]=useState(''),[loading,setLoading]=useState(true)
  useEffect(()=>{let active=true;void Promise.all([listAlerts(),listVideos()]).then(([e,v])=>{if(active){setEvents(e);setNames(Object.fromEntries(v.map(item=>[item.id,item.original_filename])))}}).catch(()=>{if(active)setError('Unable to load alert history.')}).finally(()=>{if(active)setLoading(false)});return()=>{active=false}},[])
  return <div className="page alerts-page"><div className="page-heading"><p className="eyebrow">OPERATIONAL REVIEW</p><h1>Alerts</h1><p>Historical operational alerts across your uploaded videos. Severity is user-configured prioritization, not a predictive safety classification.</p></div>{loading?<p role="status">Loading alerts…</p>:error?<p role="alert">{error}</p>:<AlertEvents events={events} videoNames={names}/>}</div>
}
