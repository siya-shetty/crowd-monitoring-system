import { useEffect, useState } from 'react'
import { getVideoPreview } from '../services/apiClient'

export function VideoPreview({ videoId }: { videoId: string }) {
  const [preview, setPreview] = useState<{ id: string; url: string } | null>(null)
  const url = preview?.id === videoId ? preview.url : null
  useEffect(() => { let active = true; let objectUrl: string | null = null; void getVideoPreview(videoId).then(blob => { if (!active) return; objectUrl = URL.createObjectURL(blob); setPreview({ id: videoId, url: objectUrl }) }).catch(() => { if (active) setPreview(null) }); return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl) } }, [videoId])
  return url ? <img className="detection-preview" alt="Annotated person detection preview" src={url}/> : <p className="video-analysis-note">Annotated preview unavailable.</p>
}
