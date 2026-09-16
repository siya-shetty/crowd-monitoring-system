import { useEffect, useState } from 'react'
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ApiError, createZone, deleteZone, generateHeatmap, getVideoPreview, listZones, updateZone, type Point, type Video, type Zone } from '../services/apiClient'
import { intensity, normalizedPoint } from '../lib/spatial'

export function SpatialResults({video}:{video:Video}) {
  const [heatmap,setHeatmap] = useState(video.heatmap_analysis ?? null)
  const [zones,setZones] = useState<Zone[]>([])
  const [selectedId,setSelectedId] = useState('')
  const [preview,setPreview] = useState<string|null>(null)
  const [showHeatmap,setShowHeatmap] = useState(true)
  const [showZones,setShowZones] = useState(true)
  const [opacity,setOpacity] = useState(.65)
  const [editing,setEditing] = useState<string|null>(null)
  const [name,setName] = useState('')
  const [description,setDescription] = useState('')
  const [points,setPoints] = useState<Point[]>([])
  const [x,setX] = useState('0.5')
  const [y,setY] = useState('0.5')
  const [busy,setBusy] = useState(false)
  const [loading,setLoading] = useState(true)
  const [error,setError] = useState('')
  const selected = zones.find(z=>z.id===selectedId)
  const width = video.width ?? 1, height = video.height ?? 1
  useEffect(()=>{
    let active=true
    void listZones(video.id).then(items=>{if(active){setZones(items);setSelectedId(items[0]?.id??'')}})
      .catch(()=>{if(active)setError('Unable to load zones. Check your access and try again.')})
      .finally(()=>{if(active)setLoading(false)})
    return ()=>{active=false}
  },[video.id])
  useEffect(()=>{
    let active=true, url:string|null=null
    if(video.has_annotated_preview) void getVideoPreview(video.id).then(blob=>{if(active){url=URL.createObjectURL(blob);setPreview(url)}}).catch(()=>{})
    return ()=>{active=false;if(url)URL.revokeObjectURL(url)}
  },[video.id,video.has_annotated_preview])
  const run = async(action:()=>Promise<void>)=>{
    setBusy(true);setError('')
    try {await action()} catch(failure) {setError(failure instanceof ApiError && typeof failure.message==='string' ? failure.message : 'Unable to save spatial changes. Check the polygon and your access, then retry.')}
    finally {setBusy(false)}
  }
  const begin = (zone?:Zone)=>{
    setEditing(zone?.id??'new');setName(zone?.name??'');setDescription(zone?.description??'');setPoints(zone?.polygon??[]);setError('')
  }
  const replace = (zone:Zone)=>{setZones(items=>items.some(z=>z.id===zone.id)?items.map(z=>z.id===zone.id?zone:z):[...items,zone]);setSelectedId(zone.id)}
  const add = (point:Point|null)=>{if(point && points.length<50 && !busy)setPoints(current=>[...current,point])}
  const save = ()=>void run(async()=>{
    const payload={name:name.trim(),description:description.trim()||null,polygon:points,active:editing==='new'?true:selected?.active??true}
    const zone = editing==='new'?await createZone(video.id,payload):await updateZone(video.id,editing!,payload)
    replace(zone);setEditing(null)
  })
  const s=selected?.analysis?.summary
  return <section className="tracking-results spatial-results" aria-label="Spatial Analysis">
    <p className="eyebrow">SPATIAL ANALYSIS · IMAGE SPACE</p><h4>Observation heatmap & monitoring zones</h4>
    <p className="video-analysis-note">Accumulated anonymous tracked-person foot-point observations across this video. Repeated observations count; this is not unique visitors, physical density, exact dwell time, or risk.</p>
    {loading && <p role="status">Loading zones…</p>}
    {error && <p role="alert">{error}</p>}
    <div className="spatial-controls">
      <label><input type="checkbox" checked={showHeatmap} onChange={e=>setShowHeatmap(e.target.checked)}/> Show heatmap</label>
      <label><input type="checkbox" checked={showZones} onChange={e=>setShowZones(e.target.checked)}/> Show zones</label>
      <label>Heatmap opacity <input type="range" min="0.1" max="1" step="0.05" value={opacity} onChange={e=>setOpacity(Number(e.target.value))}/></label>
    </div>
    {!heatmap && <button disabled={busy} onClick={()=>void run(async()=>setHeatmap(await generateHeatmap(video.id)))}>Generate heatmap from stored tracking</button>}
    {heatmap && <>
      <p>{heatmap.total_valid_spatial_observations} total spatial observations · maximum {heatmap.maximum_cell_observation_count} observations per cell</p>
      <p>Highest-observation region: {heatmap.hottest_cell_center ? `cell (${heatmap.hottest_cell?.join(', ')}), normalized center (${heatmap.hottest_cell_center.x.toFixed(3)}, ${heatmap.hottest_cell_center.y.toFixed(3)})` : 'No observations'}. Grid {heatmap.grid_width} × {heatmap.grid_height}.</p>
      <p className="heatmap-legend"><span aria-hidden="true"/> Relative observation intensity: 0 (transparent) → 1 (bright); cell count / maximum cell count.</p>
    </>}
    <div className="spatial-canvas" style={{aspectRatio:`${width} / ${height}`}}>
      {preview && <img src={preview} alt="Representative annotated video frame for spatial analysis"/>}
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Spatial overlay and polygon drawing surface" onClick={e=>{if(editing)add(normalizedPoint(e.clientX,e.clientY,e.currentTarget.getBoundingClientRect()))}}>
        <title>Normalized image coordinates, top-left origin. Click to add polygon vertices or use the coordinate fields below.</title>
        {showHeatmap && heatmap && <g aria-label="Observation heatmap" pointerEvents="none">{heatmap.raw_counts.flatMap((row,iy)=>row.map((count,ix)=>count>0 && <rect key={`${ix}-${iy}`} x={ix*width/heatmap.grid_width} y={iy*height/heatmap.grid_height} width={width/heatmap.grid_width} height={height/heatmap.grid_height} fill="#fbbf24" opacity={intensity(count,heatmap.maximum_cell_observation_count)*opacity}><title>{count} observations</title></rect>))}</g>}
        {showZones && zones.filter(z=>z.id!==editing).map(z=><g key={z.id} pointerEvents="none"><polygon points={z.polygon.map(p=>`${p.x*width},${p.y*height}`).join(' ')} fill={z.id===selectedId?'#2dd4bf33':'none'} stroke={z.active?'#2dd4bf':'#94a3b8'} strokeDasharray={z.active?undefined:'6 4'} strokeWidth="2" vectorEffect="non-scaling-stroke"/><text x={z.polygon[0].x*width} y={z.polygon[0].y*height} fontSize={width/45} fill="white" stroke="#102334" strokeWidth={width/500} paintOrder="stroke">{z.name}</text></g>)}
        {editing && <g pointerEvents="none"><polygon points={points.map(p=>`${p.x*width},${p.y*height}`).join(' ')} fill="#60a5fa33" stroke="#60a5fa" strokeWidth="2" vectorEffect="non-scaling-stroke"/>{points.map((p,i)=><circle key={i} cx={p.x*width} cy={p.y*height} r={width/140} fill="#fff"/>)}</g>}
      </svg>
    </div>
    {!preview && <p className="video-analysis-note">Preview unavailable; the analysis canvas matches the source aspect ratio.</p>}
    <p className="video-analysis-note">Foot point = clipped box bottom-center. Edges count inside; overlapping zones can count the same track. Zone counts are simultaneous observations, not physical venue occupancy.</p>
    {editing ? <fieldset disabled={busy} className="zone-editor"><legend>{editing==='new'?'Create zone':'Edit zone'}</legend>
      <label>Zone name <input value={name} maxLength={100} onChange={e=>setName(e.target.value)}/></label>
      <label>Description <textarea value={description} maxLength={1000} onChange={e=>setDescription(e.target.value)}/></label>
      <p>Click the frame to add 3–50 vertices. The last point connects to the first on save. To redraw, clear the points. Self-intersecting or degenerate polygons are rejected by the server.</p>
      <p aria-live="polite">{points.length} / 50 vertices{points.length<3?' — add at least 3 vertices':''}</p>
      <details><summary>Enter normalized coordinates with the keyboard</summary><label>Point X <input type="number" min="0" max="1" step="0.01" value={x} onChange={e=>setX(e.target.value)}/></label><label>Point Y <input type="number" min="0" max="1" step="0.01" value={y} onChange={e=>setY(e.target.value)}/></label><button disabled={points.length>=50||x===''||y===''||![Number(x),Number(y)].every(v=>Number.isFinite(v)&&v>=0&&v<=1)} onClick={()=>add({x:Number(x),y:Number(y)})}>Add point</button></details>
      <div className="spatial-controls"><button disabled={!points.length} onClick={()=>setPoints(p=>p.slice(0,-1))}>Undo last point</button><button disabled={!points.length} onClick={()=>setPoints([])}>Clear points</button><button onClick={()=>setEditing(null)}>Cancel</button><button className="primary" disabled={points.length<3||!name.trim()} onClick={save}>Save zone</button></div>
    </fieldset> : <>
      <button className="primary" disabled={busy||loading||zones.length>=50} onClick={()=>begin()}>Create zone</button>
      <h4>Monitoring zones</h4>{!loading&&!zones.length&&<p>No zones yet.</p>}
      <div className="spatial-controls">{zones.map(z=><button key={z.id} aria-pressed={z.id===selectedId} onClick={()=>setSelectedId(z.id)}>{z.name}{!z.active?' (inactive)':''}</button>)}</div>
      {selected && <><p>{selected.description}</p><div className="spatial-controls"><button disabled={busy} onClick={()=>begin(selected)}>Edit selected zone</button><button disabled={busy} onClick={()=>void run(async()=>replace(await updateZone(video.id,selected.id,{active:!selected.active})))}>{selected.active?'Deactivate':'Reactivate'} zone</button><button disabled={busy} onClick={()=>void run(async()=>{await deleteZone(video.id,selected.id);setZones(items=>items.filter(z=>z.id!==selected.id));setSelectedId('')})}>Delete selected zone</button></div></>}
    </>}
    {selected && <section aria-label="Selected zone analytics"><h4>{selected.name} — observed activity</h4>
      {!selected.active?<p>Zone inactive. Analytics are cleared; reactivation recalculates from stored tracking.</p>:!s?<p>Tracking analysis is not available yet.</p>:<>
        <dl className="tracking-metrics"><div><dt>Peak simultaneous tracks</dt><dd>{s.maximum_simultaneous_tracks}</dd></div><div><dt>Average simultaneous tracks</dt><dd>{s.average_simultaneous_tracks.toFixed(2)}</dd></div><div><dt>Median simultaneous tracks</dt><dd>{s.median_simultaneous_tracks}</dd></div><div><dt>Frames with activity</dt><dd>{s.frames_with_people} / {s.processed_frames}</dd></div><div><dt>Distinct anonymous track IDs</dt><dd>{s.distinct_anonymous_track_ids}</dd></div><div><dt>Total track observations</dt><dd>{s.total_track_observations}</dd></div><div><dt>Earliest peak time</dt><dd>{s.earliest_peak_timestamp_seconds?.toFixed(2)??'Unavailable'} s</dd></div></dl>
        <p className="video-analysis-note">Distinct IDs are tracking instances, not guaranteed unique people. Counts include zero-activity processed frames; an all-zero timeline peaks at its first frame.</p>
        <div aria-label="Zone count timeline"><ResponsiveContainer width="100%" height={180}><LineChart data={selected.analysis!.frames}><XAxis dataKey="timestamp_seconds" type="number" domain={['dataMin','dataMax']} unit="s"/><YAxis allowDecimals={false}/><Tooltip contentStyle={{background:'#102334',border:'1px solid #2b4355'}}/><Line name="Simultaneous tracks in zone" dataKey="active_tracks_in_zone" stroke="#2dd4bf" isAnimationActive={false} dot={selected.analysis!.frames.length===1}/></LineChart></ResponsiveContainer></div>
        <details><summary>View zone timeline values</summary><div className="tracking-table"><table><thead><tr><th>Frame</th><th>Time (s)</th><th>Active tracks in zone</th><th>Anonymous IDs</th></tr></thead><tbody>{selected.analysis!.frames.map(f=><tr key={f.frame_index}><td>{f.frame_index}</td><td>{f.timestamp_seconds.toFixed(2)}</td><td>{f.active_tracks_in_zone}</td><td>{f.track_ids_in_zone.join(', ')||'None'}</td></tr>)}</tbody></table></div></details>
      </>}
    </section>}
  </section>
}
