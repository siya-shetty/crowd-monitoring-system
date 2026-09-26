import { ApiError, getStoredToken, request } from './apiClient'
export const eventStatuses = ['PLANNED','ACTIVE','COMPLETED','CANCELLED'] as const
export const incidentStatuses = ['OPEN','INVESTIGATING','RESOLVED','CLOSED'] as const
export const severities = ['INFO','WARNING','CRITICAL'] as const
export type EventInput = {name:string;description:string|null;location:string|null;start_time:string;end_time:string|null;status:typeof eventStatuses[number]}
export type OperationalEvent = EventInput & {id:string;created_at:string;updated_at:string}
export type IncidentInput = {title:string;description:string;severity:typeof severities[number];status:typeof incidentStatuses[number];occurred_at:string;resolved_at:string|null;event_id:string|null;camera_id:string|null;video_id:string|null;live_session_id:string|null;alert_event_id:string|null;live_alert_event_id:string|null}
export type Context = Record<string,{id:string;label:string;rule_type?:string;severity?:string;zone?:string;recorded_at?:string;video_offset_seconds?:number}>
export type Incident = IncidentInput & {id:string;context:Context;created_at:string;updated_at:string}
export type Option = {id:string;label:string;camera_id?:string}
export type Options = {cameras:Option[];videos:Option[];sessions:Option[]}
export type AlertDraft = Omit<Partial<IncidentInput>, 'occurred_at'> & {occurred_at:string|null;context:{label:string;rule_type:string;recorded_at:string;video_offset_seconds?:number}}
export const operationsApi = <T,>(path:string,method='GET',body?:unknown) => request<T>('/api/v1'+path,{method,...(body===undefined?{}:{body:JSON.stringify(body)})},true)
export function incidentInput(item:Incident):IncidentInput {
  const {title,description,severity,status,occurred_at,resolved_at,event_id,camera_id,video_id,live_session_id,alert_event_id,live_alert_event_id}=item
  return {title,description,severity,status,occurred_at,resolved_at,event_id,camera_id,video_id,live_session_id,alert_event_id,live_alert_event_id}
}
export function blankIncident():IncidentInput{return {title:'',description:'',severity:'WARNING',status:'OPEN',occurred_at:new Date().toISOString(),resolved_at:null,event_id:null,camera_id:null,video_id:null,live_session_id:null,alert_event_id:null,live_alert_event_id:null}}
export function localTime(value:string|null){if(!value)return '';const d=new Date(value);return new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,16)}
export function isoTime(value:string){return value?new Date(value).toISOString():''}
export async function downloadReport(query=''){
  const response=await fetch(`${import.meta.env.VITE_API_BASE_URL??'http://localhost:8000'}/api/v1/incidents/export.csv${query}`,{headers:{Authorization:`Bearer ${getStoredToken()??''}`}})
  if(!response.ok){if(response.status===401)window.dispatchEvent(new Event('auth:unauthorized'));const body=await response.json().catch(()=>({detail:'Unable to download report'}));throw new ApiError(response.status,typeof body.detail==='string'?body.detail:'Unable to download report')}
  const url=URL.createObjectURL(await response.blob()),link=document.createElement('a')
  link.href=url;link.download='incidents.csv';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000)
}
