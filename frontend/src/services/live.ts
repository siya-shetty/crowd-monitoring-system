import { request, type Point, type CrowdFrame } from './apiClient'
import type { RuleInput } from './alerts'

export type Camera = { id:string; name:string; description:string|null; enabled:boolean; source_type:'BROWSER' }
export type CameraZone = { id:string; camera_id:string; name:string; description:string|null; polygon:Point[]; active:boolean }
export type CameraRule = Omit<RuleInput,'scope'> & { id:string; camera_id:string; scope:'CAMERA'|'ZONE' }
export type LiveObservation = Omit<CrowdFrame,'frame_index'> & { sequence:number; width:number; height:number; processing_duration_seconds:number; current_operational_risk:string; active_alert_count:number; zones:Record<string,{name:string;active_tracks_in_zone:number;track_ids_in_zone:number[]}> }
export type LiveSession = { id:string; camera_id:string; status:'STARTING'|'RUNNING'|'STOPPING'|'STOPPED'|'FAILED'; is_stale?:boolean; processed_frame_count:number; dropped_frame_count:number; latest_snapshot:LiveObservation|null; summary:Record<string,unknown>; error_summary:string|null }
export type LiveEvent = {id:string; severity:string; rule_snapshot:CameraRule; evidence:Record<string,unknown>; resolved_at:string|null}
export type LiveConfig = {target_fps:number;capture_width:number;capture_height:number;max_frame_bytes:number;stale_seconds:number}
export const liveApi = <T,>(path:string,method='GET',body?:unknown) => request<T>('/api/v1'+path,{method,...(body===undefined?{}:{body:JSON.stringify(body)})},true)
export const sendFrame = (id:string,sequence:number,timestamp:number,blob:Blob,signal:AbortSignal) => request<LiveObservation>(`/api/v1/live/sessions/${id}/frames?sequence=${sequence}&capture_timestamp=${timestamp}`,{method:'POST',body:blob,headers:{'Content-Type':blob.type},signal},true)
