import { useEffect, useRef, useState } from 'react'
import { FileVideo, Trash2, Upload } from 'lucide-react'
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ApiError, deleteVideo, listVideos, uploadVideo, type Video } from '../services/apiClient'
import { VideoPreview } from '../components/VideoPreview'
import { TrackingResults } from '../components/TrackingResults'
import { CrowdResults } from '../components/CrowdResults'
import { SpatialResults } from '../components/SpatialResults'

const formats = ['video/mp4', 'video/webm', 'video/quicktime']
const max = 100 * 1024 * 1024

export function VideosPage() {
  const [file, setFile] = useState<File | null>(null)
  const [videos, setVideos] = useState<Video[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const input = useRef<HTMLInputElement>(null)

  useEffect(() => {
    let active = true
    void listVideos().then(items => { if (active) setVideos(items) })
      .catch(() => { if (active) setError('Unable to load your video library.') })
    return () => { active = false }
  }, [])

  const select = (selected: File | undefined) => {
    if (!selected || !formats.includes(selected.type) || !selected.size || selected.size > max) {
      setError('Choose a non-empty MP4, WebM, or MOV file under 100 MB.')
      setFile(null)
      return
    }
    setError('')
    setFile(selected)
  }

  const submit = async () => {
    if (!file) return
    setLoading(true)
    setError('')
    try {
      const uploaded = await uploadVideo(file)
      setVideos(current => [uploaded, ...current])
      setFile(null)
      if (input.current) input.current.value = ''
    } catch (failure) {
      setError(failure instanceof ApiError ? failure.message : 'Upload failed.')
    } finally {
      setLoading(false)
    }
  }

  const remove = async (id: string) => {
    if (!window.confirm('Delete this uploaded video and its stored analysis and preview?')) return
    try {
      await deleteVideo(id)
      setVideos(current => current.filter(video => video.id !== id))
    } catch {
      setError('Unable to delete this video. Please try again.')
    }
  }

  return <div className="page">
    <div className="page-heading">
      <p className="eyebrow">VIDEO ANALYSIS</p>
      <h1>Upload video for person detection and tracking</h1>
      <p>Person detections from sampled frames and temporary anonymous tracks within each video.</p>
    </div>
    <section className="card upload-zone">
      <Upload/><h2>Choose a video to analyze</h2>
      <p>MP4, WebM, or MOV &middot; maximum 100 MB</p>
      <input ref={input} aria-label="Choose video file" type="file" accept={formats.join(',')} hidden onChange={event => select(event.target.files?.[0])}/>
      <button className="primary" disabled={loading} onClick={() => input.current?.click()}>Choose video</button>
      {file && <button className="primary" disabled={loading} onClick={() => void submit()}>{loading ? 'Analyzing...' : `Upload ${file.name}`}</button>}
      {error && <p role="alert">{error}</p>}
    </section>
    <section className="video-library">
      <h2>Your video library</h2>
      {videos.map(video => <article className="card video-row" key={video.id}>
        <FileVideo/>
        <div>
          <h3>{video.original_filename}</h3>
          <p>Analysis status: {video.status}</p>
          <p>Tracking status: {video.tracking_analysis ? 'Completed' : video.status === 'completed' ? 'Not available for this earlier analysis' : video.status}</p>
          <p>Crowd analysis status: {video.crowd_analysis ? 'Completed' : video.status === 'completed' ? 'Not available for this earlier analysis' : video.status}</p>
          {video.width && video.height && <p>{video.width} x {video.height} pixels; {video.fps} FPS; {video.duration_seconds?.toFixed(2)} seconds</p>}
          {video.detection_summary && <>
            <h4>Person Detection</h4>
            <p>{video.detection_summary.total_person_detections} total person detections &mdash; not unique people, attendance, or crowd size.</p>
            <p>Model {video.detection_summary.model}; confidence {video.detection_summary.confidence_threshold}; stride {video.detection_summary.frame_stride}</p>
            <p>{video.detection_summary.sampled_frames_processed} sampled frames; {video.detection_summary.frames_with_people} with people; maximum {video.detection_summary.maximum_persons_in_sampled_frame}; average {video.detection_summary.average_persons_per_sampled_frame.toFixed(1)}</p>
            {video.detection_frames && <ResponsiveContainer width="100%" height={150}>
              <LineChart data={video.detection_frames}><XAxis dataKey="frame_index"/><YAxis allowDecimals={false}/><Tooltip/><Line name="Person detections (sampled)" dataKey="person_count" stroke="#2dd4bf"/></LineChart>
            </ResponsiveContainer>}
          </>}
          {video.has_annotated_preview && <VideoPreview videoId={video.id}/>}
          {video.crowd_analysis && <CrowdResults analysis={video.crowd_analysis}/>}
          {video.tracking_analysis && <details><summary>Spatial Analysis</summary><SpatialResults video={video}/></details>}
          {video.tracking_analysis && <TrackingResults analysis={video.tracking_analysis} width={video.width ?? 1} height={video.height ?? 1}/>}
          {video.error_message && <p role="alert">{video.error_message}</p>}
        </div>
        <button aria-label={`Delete ${video.original_filename}`} onClick={() => void remove(video.id)}><Trash2/></button>
      </article>)}
    </section>
  </div>
}
