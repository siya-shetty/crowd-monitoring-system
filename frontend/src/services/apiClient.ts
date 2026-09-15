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
  return response.json() as Promise<T>
}
export function getHealth(): Promise<HealthResponse> { return request<HealthResponse>('/health') }
export function register(payload: UserCreate): Promise<User> { return request<User>('/api/v1/auth/register', { method: 'POST', body: JSON.stringify(payload) }) }
export function login(payload: UserLogin): Promise<TokenResponse> { return request<TokenResponse>('/api/v1/auth/login', { method: 'POST', body: JSON.stringify(payload) }) }
export function getCurrentUser(): Promise<User> { return request<User>('/api/v1/auth/me', {}, true) }
export type Video = { id:string; original_filename:string; content_type:string; file_size:number; status:'uploaded'|'processing'|'completed'|'failed'; duration_seconds:number|null; width:number|null; height:number|null; fps:number|null; frame_count:number|null; error_message:string|null; created_at:string }
export function uploadVideo(file:File):Promise<Video>{const form=new FormData();form.append('file',file);return request<Video>('/api/v1/videos',{method:'POST',body:form},true)}
export function listVideos():Promise<Video[]>{return request<Video[]>('/api/v1/videos',{},true)}
export function deleteVideo(id:string):Promise<void>{return request<void>(`/api/v1/videos/${id}`,{method:'DELETE'},true)}
