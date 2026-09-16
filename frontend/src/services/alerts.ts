import { request } from './apiClient'
export const ruleTypes = ['CROWD_COUNT_ABOVE','CROWD_LEVEL_AT_LEAST','SUDDEN_CROWD_INCREASE','ZONE_COUNT_ABOVE','ZONE_PRESENCE'] as const
export type RuleType = typeof ruleTypes[number]
export type Severity = 'INFO'|'WARNING'|'CRITICAL'
export type RuleInput = {name:string;description:string|null;rule_type:RuleType;scope:'VIDEO'|'ZONE';severity:Severity;enabled:boolean;zone_id:string|null;configuration:Record<string,number|string>}
export type Rule = RuleInput & {id:string;video_id:string}
export type AlertEvent = {id:string;video_id:string;rule_id:string|null;zone_id:string|null;rule_name:string;rule_type:RuleType;severity:Severity;condition_start_seconds:number;trigger_seconds:number;end_seconds:number;state:string;evidence:{metric:string;threshold:number|string;trigger_value:number|string;peak_value:number|string;minimum_duration_seconds:number;observed_duration_seconds:number;maximum_gap_seconds:number;closure:string;zone_name:string|null;baseline_seconds:number|null;baseline_count:number|null;current_count:number|null}}
export type AlertSummary = {total_events:number;maximum_operational_risk:string;events_by_severity:Record<Severity,number>;configured_rules:number;enabled_rules:number;earliest_alert_seconds:number|null}
const base=(video:string)=>`/api/v1/videos/${video}`
export const listRules=(video:string)=>request<Rule[]>(base(video)+'/alert-rules',{},true)
export const saveRule=(video:string,payload:RuleInput,id?:string)=>request<Rule>(base(video)+'/alert-rules'+(id?'/'+id:''),{method:id?'PATCH':'POST',body:JSON.stringify(payload)},true)
export const toggleRule=(video:string,id:string,enabled:boolean)=>request<Rule>(base(video)+'/alert-rules/'+id,{method:'PATCH',body:JSON.stringify({enabled})},true)
export const deleteRule=(video:string,id:string)=>request<void>(base(video)+'/alert-rules/'+id,{method:'DELETE'},true)
export const listAlerts=(video?:string)=>request<AlertEvent[]>(video?base(video)+'/alerts':'/api/v1/alerts',{},true)
export const getAlertSummary=(video:string)=>request<AlertSummary>(base(video)+'/alert-summary',{},true)
