const baseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
const tokenKey = 'sentinel-grid-access-token'
export type HealthResponse = { status: string; service: string; database?: string }
export type User = { id: string; email: string; full_name: string; role: 'admin' | 'operator' | 'viewer'; is_active: boolean }
export type UserCreate = { full_name: string; email: string; password: string }
export type UserLogin = { email: string; password: string }
export type TokenResponse = { access_token: string; token_type: 'bearer' }
export class ApiError extends Error { status: number; constructor(status: number, message: string) { super(message); this.status = status } }
export function getStoredToken(): string | null { return localStorage.getItem(tokenKey) }
export function storeToken(token: string): void { localStorage.setItem(tokenKey, token) }
export function clearStoredToken(): void { localStorage.removeItem(tokenKey) }
async function request<T>(path: string, init: RequestInit = {}, authenticated = false): Promise<T> {
  const headers = new Headers(init.headers); if (!(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  const token = authenticated ? getStoredToken() : null
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(`${baseUrl}${path}`, { ...init, headers })
  if (!response.ok) { if (response.status === 401) window.dispatchEvent(new Event('auth:unauthorized')); const body = await response.json().catch(() => ({ detail: 'Request failed' })) as { detail?: string }; throw new ApiError(response.status, body.detail ?? 'Request failed') }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}
export function getHealth(): Promise<HealthResponse> { return request<HealthResponse>('/health') }
export function register(payload: UserCreate): Promise<User> { return request<User>('/api/v1/auth/register', { method: 'POST', body: JSON.stringify(payload) }) }
export function login(payload: UserLogin): Promise<TokenResponse> { return request<TokenResponse>('/api/v1/auth/login', { method: 'POST', body: JSON.stringify(payload) }) }
export function getCurrentUser(): Promise<User> { return request<User>('/api/v1/auth/me', {}, true) }
export type DetectionSummary = { model:string; confidence_threshold:number; frame_stride:number; sampled_frames_processed:number; frames_with_people:number; total_person_detections:number; maximum_persons_in_sampled_frame:number; average_persons_per_sampled_frame:number; processing_duration_seconds:number }
export type DetectionFrame = { frame_index:number; timestamp_seconds:number; person_count:number; detections:Array<{x1:number;y1:number;x2:number;y2:number;confidence:number}> }
export type TrackingFrame = { frame_index:number; timestamp_seconds:number; active_track_count:number; tracked_persons:Array<{track_id:number;x1:number;y1:number;x2:number;y2:number;confidence:number}> }
export type TrackHistory = { track_id:number; first_observed_frame:number; last_observed_frame:number; first_observed_timestamp:number; last_observed_timestamp:number; observation_count:number; average_confidence:number; trajectory:Array<{frame_index:number;timestamp_seconds:number;center_x:number;center_y:number}> }
export type TrackingAnalysis = { schema_version:1; summary:{tracker:'ByteTrack';frame_stride:number;track_high_threshold:number;track_low_threshold:number;track_match_threshold:number;track_buffer:number;processed_frames:number;frames_with_active_tracks:number;maximum_simultaneous_active_tracks:number;average_active_tracks_per_processed_frame:number;distinct_track_ids:number;average_track_observation_length:number;longest_track_observation_length:number}; frames:TrackingFrame[]; tracks:TrackHistory[] }
export type Video = { id:string; original_filename:string; content_type:string; file_size:number; status:'uploaded'|'processing'|'completed'|'failed'; duration_seconds:number|null; width:number|null; height:number|null; fps:number|null; frame_count:number|null; error_message:string|null; created_at:string; detection_summary:DetectionSummary|null; detection_frames:DetectionFrame[]|null; has_annotated_preview:boolean; tracking_analysis?:TrackingAnalysis|null }
export function uploadVideo(file:File):Promise<Video>{const form=new FormData();form.append('file',file);return request<Video>('/api/v1/videos',{method:'POST',body:form},true)}
export function listVideos():Promise<Video[]>{return request<Video[]>('/api/v1/videos',{},true)}
export function deleteVideo(id:string):Promise<void>{return request<void>(`/api/v1/videos/${id}`,{method:'DELETE'},true)}
export async function getVideoPreview(id: string): Promise<Blob> { const response = await fetch(`${baseUrl}/api/v1/videos/${id}/preview`, { headers: { Authorization: `Bearer ${getStoredToken() ?? ''}` } }); if (!response.ok) throw new ApiError(response.status, 'Preview unavailable'); return response.blob() }
