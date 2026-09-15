import { useState } from 'react'
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { TrackingAnalysis } from '../services/apiClient'

export function TrackingResults({ analysis, width, height }: { analysis: TrackingAnalysis; width: number; height: number }) {
  const { summary: s, frames, tracks } = analysis
  const [selectedId, setSelectedId] = useState(tracks[0]?.track_id ?? 0)
  const selected = tracks.find(track => track.track_id === selectedId)
  return <section className="tracking-results" aria-label="Anonymous tracking results">
    <p className="eyebrow">ANONYMOUS TRACKING · {s.tracker}</p>
    <h4>{s.distinct_track_ids} distinct anonymous track IDs</h4>
    <p className="video-analysis-note">Track IDs are temporary anonymous identifiers and do not represent verified unique individuals.</p>
    <dl className="tracking-metrics">
      <div><dt>Processed frames</dt><dd>{s.processed_frames}</dd></div>
      <div><dt>Frames with active tracks</dt><dd>{s.frames_with_active_tracks}</dd></div>
      <div><dt>Maximum simultaneous active tracks</dt><dd>{s.maximum_simultaneous_active_tracks}</dd></div>
      <div><dt>Average active tracks/frame</dt><dd>{s.average_active_tracks_per_processed_frame.toFixed(2)}</dd></div>
      <div><dt>Longest observed track</dt><dd>{s.longest_track_observation_length} observations</dd></div>
      <div><dt>Average track observation length</dt><dd>{s.average_track_observation_length.toFixed(1)} observations</dd></div>
    </dl>
    <p>Tracking stride {s.frame_stride}; skipped frames are not tracked.</p>
    <h4>Active anonymous tracks over time</h4>
    <div aria-label="Active track timeline">
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={frames}><XAxis dataKey="timestamp_seconds" name="Time" unit="s"/><YAxis allowDecimals={false}/><Tooltip labelFormatter={value => `${value}s`}/><Line name="Active anonymous tracks" dataKey="active_track_count" stroke="#2dd4bf" dot={false} isAnimationActive={false}/></LineChart>
      </ResponsiveContainer>
    </div>
    <details><summary>View processed frame counts</summary><div className="tracking-table"><table><thead><tr><th>Frame</th><th>Time (s)</th><th>Active tracks</th></tr></thead><tbody>{frames.map(f => <tr key={f.frame_index}><td>{f.frame_index}</td><td>{f.timestamp_seconds.toFixed(2)}</td><td>{f.active_track_count}</td></tr>)}</tbody></table></div></details>
    <h4>Observed trajectory</h4>
    {tracks.length ? <>
      <label>Anonymous track <select value={selectedId} onChange={event => setSelectedId(Number(event.target.value))}>{tracks.map(track => <option key={track.track_id} value={track.track_id}>Track {track.track_id} · {track.observation_count} observations</option>)}</select></label>
      {selected && <>
        <p>Track {selected.track_id}: frames {selected.first_observed_frame}–{selected.last_observed_frame}, {selected.first_observed_timestamp.toFixed(2)}–{selected.last_observed_timestamp.toFixed(2)}s</p>
        <svg className="track-trajectory" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`Normalized observed trajectory for Track ${selected.track_id}`}>
          <title>Bounding-box centers in image space, top-left origin</title>
          <polyline points={selected.trajectory.map(p => `${p.center_x * width},${p.center_y * height}`).join(' ')} fill="none" stroke="#2dd4bf" strokeWidth="2" vectorEffect="non-scaling-stroke"/>
          {selected.trajectory.map(p => <circle key={p.frame_index} cx={p.center_x * width} cy={p.center_y * height} r={Math.max(width, height) / 180} fill="#2dd4bf"><title>Frame {p.frame_index} · {p.timestamp_seconds.toFixed(2)}s</title></circle>)}
        </svg>
      </>}
      <p className="video-analysis-note">Normalized box centers; lines connect observed samples across gaps. No physical distance or speed is measured.</p>
    </> : <p>No confirmed anonymous tracks were observed.</p>}
  </section>
}
