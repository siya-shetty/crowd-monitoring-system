import { useEffect, useRef, useState } from 'react'
import { FileVideo, Trash2, Upload } from 'lucide-react'
import { ApiError, deleteVideo, listVideos, uploadVideo, type Video } from '../services/apiClient'

const formats = ['video/mp4', 'video/webm', 'video/quicktime']
const max = 100 * 1024 * 1024
const size = (bytes: number) => `${(bytes / 1024 / 1024).toFixed(1)} MB`
const metadata = (video: Video) => video.status === 'completed'
  ? `${video.width} x ${video.height} · ${video.fps?.toFixed(1)} FPS · ${video.duration_seconds?.toFixed(1)} sec · ${video.frame_count} frames`
  : 'Metadata pending'

export function VideosPage() {
  const [file, setFile] = useState<File | null>(null)
  const [videos, setVideos] = useState<Video[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const input = useRef<HTMLInputElement>(null)

  const load = async () => {
    try { setVideos(await listVideos()) } catch { setError('Unable to load your video library.') }
  }
  useEffect(() => { void load() }, [])

  const select = (candidate: File | undefined) => {
    if (!candidate) return
    if (!formats.includes(candidate.type) || candidate.size === 0 || candidate.size > max) {
      setError('Choose a non-empty MP4, WebM, or MOV file under 100 MB.')
      setFile(null)
      return
    }
    setError('')
    setFile(candidate)
  }

  const submit = async () => {
    if (!file) return
    setLoading(true); setError('')
    try { const video = await uploadVideo(file); setVideos(current => [video, ...current]); setFile(null) }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : 'Upload failed.') }
    finally { setLoading(false) }
  }
  const remove = async (id: string) => {
    if (!window.confirm('Delete this uploaded video and its stored file?')) return
    try { await deleteVideo(id); setVideos(items => items.filter(item => item.id !== id)) }
    catch { setError('Unable to delete this video.') }
  }

  return <div className="page">
    <div className="page-heading"><div><p className="eyebrow">VIDEO ANALYSIS</p><h1>Upload video for inspection</h1><p>Store crowd footage securely and inspect technical metadata. AI crowd analysis begins in the next phase.</p></div></div>
    <section className="card upload-zone" onDragOver={event => event.preventDefault()} onDrop={event => { event.preventDefault(); select(event.dataTransfer.files[0]) }}>
      <Upload/><h2>Drop a video here</h2><p>MP4, WebM, or MOV · maximum 100 MB</p>
      <input ref={input} aria-label="Choose video file" type="file" accept="video/mp4,video/webm,video/quicktime" hidden onChange={event => select(event.target.files?.[0])}/>
      <button className="primary" onClick={() => input.current?.click()}>Choose video</button>
      {file && <div className="selected-file">{file.name} · {size(file.size)} <button className="primary" disabled={loading} onClick={submit}>{loading ? 'Inspecting…' : 'Upload & inspect'}</button></div>}
      {error && <p role="alert" className="form-error">{error}</p>}
    </section>
    <section className="video-library"><h2>Your video library</h2>{videos.length === 0
      ? <article className="empty-state card"><FileVideo/><h2>No video analyses yet</h2><p>Upload a crowd video to inspect duration, resolution, and frame metadata. Person detection is not implemented yet.</p></article>
      : videos.map(video => <article className="card video-row" key={video.id}><FileVideo/><div><h3>{video.original_filename}</h3><p>{size(video.file_size)} · {new Date(video.created_at).toLocaleString()}</p><p>{metadata(video)}</p><p className="video-analysis-note">AI Crowd Analysis: person detection and crowd analytics will be added in the next phase.</p>{video.error_message && <p className="form-error">{video.error_message}</p>}</div><span className={`status ${video.status}`}>{video.status}</span><button className="icon" aria-label={`Delete ${video.original_filename}`} onClick={() => remove(video.id)}><Trash2/></button></article>)}</section>
  </div>
}
