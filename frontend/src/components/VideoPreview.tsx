import { useEffect, useState } from 'react'
import { getVideoPreview } from '../services/apiClient'

export function VideoPreview({ videoId }: { videoId: string }) {
  const [url, setUrl] = useState<string | null>(null)
  useEffect(() => { let active = true; let objectUrl: string | null = null; void getVideoPreview(videoId).then(blob => { objectUrl = URL.createObjectURL(blob); if (active) setUrl(objectUrl) }).catch(() => { if (active) setUrl(null) }); return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl) } }, [videoId])
  return url ? <img className="detection-preview" alt="Annotated person detection preview" src={url}/> : <p className="video-analysis-note">Annotated preview unavailable.</p>
}
