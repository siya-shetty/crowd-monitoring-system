import { ApiError } from './apiClient'
import { liveApi, type LiveSession, type LiveEvent } from './live'

export type SocketHealth = 'CONNECTED' | 'RECONNECTING' | 'DISCONNECTED'
export type LiveState = Pick<LiveSession,'id'|'status'|'processed_frame_count'|'dropped_frame_count'|'is_stale'|'error_summary'|'latest_snapshot'> & {alerts:LiveEvent[]}
export type Envelope = {version:1;event:string;session_id:string;sequence:number;emitted_at:string;data:LiveState}
const object = (v:unknown):v is Record<string,unknown> => !!v && typeof v==='object' && !Array.isArray(v)
const number = (v:unknown) => typeof v==='number' && Number.isFinite(v) && v>=0
export function parseEvent(raw:string,id:string):Envelope|null {
  try {
    const e:unknown=JSON.parse(raw)
    if(!object(e)||e.version!==1||e.session_id!==id||!Number.isSafeInteger(e.sequence)||typeof e.emitted_at!=='string'||!['session.snapshot','session.stopped','session.failed','alert.triggered','alert.resolved'].includes(String(e.event))||!object(e.data))return null
    const d=e.data, m=d.latest_snapshot
    if(d.error_summary!==null&&typeof d.error_summary!=='string')return null
    if(d.id!==id||!['STARTING','RUNNING','STOPPING','STOPPED','FAILED'].includes(String(d.status))||!number(d.processed_frame_count)||!number(d.dropped_frame_count)||typeof d.is_stale!=='boolean'||!Array.isArray(d.alerts)||d.alerts.length>50)return null
    if(!d.alerts.every(a=>object(a)&&typeof a.id==='string'&&typeof a.severity==='string'&&object(a.rule_snapshot)&&typeof a.rule_snapshot.name==='string'&&typeof a.rule_snapshot.rule_type==='string'&&typeof a.rule_snapshot.scope==='string'&&object(a.evidence)&&(a.resolved_at===null||typeof a.resolved_at==='string')))return null
    if(m!==null){
      if(!object(m)||!['sequence','observed_crowd_count','image_occupancy_ratio','crowd_concentration','processing_duration_seconds','active_alert_count'].every(k=>number(m[k]))||!['LOW','MODERATE','HIGH','VERY_HIGH'].includes(String(m.crowd_level))||!['NORMAL','ELEVATED','HIGH','CRITICAL'].includes(String(m.current_operational_risk))||!object(m.zones))return null
      if(!Object.values(m.zones).every(z=>object(z)&&typeof z.name==='string'&&number(z.active_tracks_in_zone)&&(z.active===undefined||typeof z.active==='boolean')&&(z.peak===undefined||number(z.peak))))return null
    }
    return e as unknown as Envelope
  }catch{return null}
}

export function connectLive(id:string,onState:(state:LiveState)=>void,onHealth:(health:SocketHealth)=>void) {
  let closed=false, socket:WebSocket|undefined, timer:ReturnType<typeof setTimeout>, watchdog:ReturnType<typeof setTimeout>, attempt=0, sequence=-1
  const reconnect=()=>{
    if(closed)return
    onHealth('RECONNECTING')
    clearTimeout(timer)
    timer=setTimeout(()=>void open(),Math.min(8000,500*2**Math.min(attempt++,5))*(.8+Math.random()*.4))
  }
  const touch=()=>{clearTimeout(watchdog);watchdog=setTimeout(()=>socket?.close(),16000)}
  const open=async()=>{
    onHealth('RECONNECTING')
    try {
      const ticket=await liveApi<{ticket:string}>(`/live/sessions/${id}/ws-ticket`,'POST')
      if(closed)return
      const url=new URL(`${import.meta.env.VITE_API_BASE_URL??'http://localhost:8000'}/api/v1/live/sessions/${id}/ws`,window.location.href)
      url.protocol=url.protocol==='https:'?'wss:':'ws:'
      socket=new WebSocket(url)
      socket.onopen=()=>{socket?.send(ticket.ticket);touch()}
      socket.onmessage=message=>{
        if(closed||typeof message.data!=='string'||message.data.length>262144)return
        if(message.data==='{"version":1,"event":"heartbeat"}'){socket?.send('pong');touch();return}
        const event=parseEvent(message.data,id)
        if(!event||event.sequence<=sequence)return
        sequence=event.sequence;attempt=0;touch();onHealth('CONNECTED');onState(event.data)
        if(['STOPPED','FAILED'].includes(event.data.status)){closed=true;clearTimeout(watchdog);socket?.close();onHealth('DISCONNECTED')}
      }
      socket.onclose=()=>{clearTimeout(watchdog);reconnect()}
      socket.onerror=()=>socket?.close()
    }catch(e){
      if(e instanceof ApiError&&[401,403,404].includes(e.status)){closed=true;onHealth('DISCONNECTED');return}
      reconnect()
    }
  }
  void open()
  return()=>{closed=true;clearTimeout(timer);clearTimeout(watchdog);socket?.close();onHealth('DISCONNECTED')}
}
