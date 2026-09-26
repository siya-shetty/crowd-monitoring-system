import { request } from './apiClient'

export type TimeRange = '7d' | '30d' | 'all'
export type Breakdown = { total:number; by_severity:Record<string,number>; by_type:Record<string,number> }
export type SessionAnalytics = {
  id:string; camera_name:string; status:string; started_at:string; stopped_at:string|null
  duration_seconds:number|null; processed_frames:number; dropped_frames:number
  average_count:number|null; peak_count:number|null; maximum_crowd_level:string|null
  maximum_operational_risk:string|null; final_operational_risk:string|null; summary:string|null
  zones:Array<{id:string;name:string;peak_count:number|null}>; alerts:Breakdown
  alert_history?:Array<{id:string;created_at:string;resolved_at:string|null;severity:string;rule_type:string;rule_name:string;zone_name:string|null}>
}
type Metrics = {observations:number;average_count:number|null;peak_count:number|null;average_image_occupancy:number|null;average_image_space_concentration:number|null;crowd_levels?:Record<string,number>;maximum_crowd_levels?:Record<string,number>;risk_distribution:Record<string,number>}
type History = {date:string;video_average:number|null;live_average:number|null;video_peak:number|null;live_peak:number|null}
export type Analytics = {
  range:TimeRange;total_analyzed_videos:number;total_live_sessions:number
  video_statuses:Record<string,number>;session_statuses:Record<string,number>;alerts:Breakdown
  video:Metrics;live:Metrics;history:History[];history_total_days:number
  peak_periods:Record<'video'|'live',History|null>;sessions:SessionAnalytics[]
  video_zones:Array<{id:string;name:string;video_id:string;peak_count:number|null;average_count:number|null}>
}
export const getAnalytics = (range:TimeRange) => request<Analytics>(`/api/v1/analytics?range=${range}`,{},true)
export const getSessionAnalytics = (id:string) => request<SessionAnalytics>(`/api/v1/analytics/sessions/${id}`,{},true)
