import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { CrowdAnalysis } from '../services/apiClient'

export function CrowdResults({ analysis }: { analysis: CrowdAnalysis }) {
  const { summary: s, config, frames } = analysis
  const occupancy = frames.map(f => ({ ...f, occupancy_percent: f.image_occupancy_ratio * 100 }))
  const occupancyAxisMax = Math.min(100, Math.max(5, Math.ceil(s.maximum_image_occupancy * 100 / 5) * 5))
  const tooltipStyle = { background: '#102334', border: '1px solid #2b4355', color: '#e2e8f0' }
  const trend = s.final_crowd_trend
  return <section className="tracking-results" aria-label="Crowd Analysis">
    <p className="eyebrow">CROWD ANALYSIS · IMAGE SPACE</p>
    <h4>Observed crowd overview</h4>
    <p className="video-analysis-note">Crowd count means simultaneous active anonymous person tracks observed in a frame. It does not measure attendance or unique visitors.</p>
    <dl className="tracking-metrics">
      <div><dt>Peak observed crowd</dt><dd>{s.maximum_observed_crowd_count} active tracks</dd></div>
      <div><dt>Average observed crowd</dt><dd>{s.average_observed_crowd_count.toFixed(2)} active tracks</dd></div>
      <div><dt>Peak time (earliest tie)</dt><dd>{s.peak_crowd_timestamp_seconds === null ? 'Unavailable' : `${s.peak_crowd_timestamp_seconds.toFixed(2)} s`}</dd></div>
      <div><dt>Average image occupancy</dt><dd>{(s.average_image_occupancy * 100).toFixed(2)}%</dd></div>
      <div><dt>Maximum image occupancy</dt><dd>{(s.maximum_image_occupancy * 100).toFixed(2)}%</dd></div>
      <div><dt>Average crowd concentration</dt><dd>{s.average_crowd_concentration.toFixed(3)} / 1</dd></div>
    </dl>
    <p>Crowd trend at final observation: <strong>{trend.charAt(0).toUpperCase() + trend.slice(1)}</strong></p>
    <p className="video-analysis-note">Trend describes fitted count change over the last 10 processed tracking frames; fewer frames are stable. This is descriptive, not predictive.</p>
    {s.frames_with_observed_people === 0 && <p>No active anonymous person tracks were observed.</p>}
    <h4>Observed crowd count over time</h4>
    <div aria-label="Crowd count timeline">
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={frames}><XAxis dataKey="timestamp_seconds" type="number" domain={['dataMin', 'dataMax']} unit="s"/><YAxis allowDecimals={false}/><Tooltip contentStyle={tooltipStyle} labelFormatter={value => `${Number(value).toFixed(2)} s`} formatter={(value, name, item) => [value, `${name} · ${item.payload.crowd_level}`]}/><Line name="Observed active tracks" dataKey="observed_crowd_count" stroke="#2dd4bf" dot={frames.length === 1} isAnimationActive={false}/></LineChart>
      </ResponsiveContainer>
    </div>
    <h4>Image occupancy</h4>
    <p className="video-analysis-note">Percentage of image area covered by the union of tracked person bounding boxes. This is an image-space metric, not physical venue occupancy.</p>
    <div aria-label="Image occupancy timeline">
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={occupancy}><XAxis dataKey="timestamp_seconds" type="number" domain={['dataMin', 'dataMax']} unit="s"/><YAxis domain={[0, occupancyAxisMax]} unit="%"/><Tooltip contentStyle={tooltipStyle} labelFormatter={value => `${Number(value).toFixed(2)} s`} formatter={value => [`${Number(value).toFixed(2)}%`, 'Image occupancy']}/><Line name="Image occupancy (%)" dataKey="occupancy_percent" stroke="#60a5fa" dot={frames.length === 1} isAnimationActive={false}/></LineChart>
      </ResponsiveContainer>
    </div>
    <p className="video-analysis-note">The occupancy axis starts at zero and scales to this video. Concentration ranges from 0 to 1: tighter normalized box centers score higher. Zero or one track scores 0. Neither metric is people/m²; camera perspective and occlusion affect both.</p>
    <h4>Crowd level distribution</h4>
    <p className="video-analysis-note">Configurable operational count categories, not universal safety standards. MODERATE ≥ {config.moderate_count}; HIGH ≥ {config.high_count}; VERY_HIGH ≥ {config.very_high_count} active tracks.</p>
    <dl className="tracking-metrics" aria-label="Crowd level distribution">
      {s.level_distribution.map(item => <div key={item.level}><dt>{item.level.replaceAll('_', ' ')}</dt><dd>{item.frames} frames · {item.percentage.toFixed(1)}%</dd></div>)}
    </dl>
    <p className="video-analysis-note">Distribution and averages weight processed frames equally; skipped source frames are not observations.</p>
    <details><summary>View crowd frame metrics</summary><div className="tracking-table"><table>
      <thead><tr><th>Frame</th><th>Time (s)</th><th>Active tracks</th><th>Image occupancy (%)</th><th>Concentration</th><th>Level</th><th>Count delta</th><th>Trend</th></tr></thead>
      <tbody>{frames.map(f => <tr key={f.frame_index}><td>{f.frame_index}</td><td>{f.timestamp_seconds.toFixed(2)}</td><td>{f.observed_crowd_count}</td><td>{(f.image_occupancy_ratio * 100).toFixed(2)}</td><td>{f.crowd_concentration.toFixed(3)}</td><td>{f.crowd_level}</td><td>{f.crowd_count_delta}</td><td>{f.crowd_trend}</td></tr>)}</tbody>
    </table></div></details>
  </section>
}
