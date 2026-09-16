import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { beforeEach, expect, test, vi } from 'vitest'
import { SpatialResults } from './SpatialResults'
import * as api from '../services/apiClient'

vi.mock('../services/apiClient', async()=>({...await vi.importActual('../services/apiClient'),listZones:vi.fn(),createZone:vi.fn(),updateZone:vi.fn(),deleteZone:vi.fn(),generateHeatmap:vi.fn()}))
const polygon=[{x:.1,y:.1},{x:.8,y:.1},{x:.8,y:.9}]
const analysis:api.ZoneAnalysis={schema_version:1,frames:[{frame_index:0,timestamp_seconds:0,active_tracks_in_zone:2,track_ids_in_zone:[1,2]}],summary:{processed_frames:1,frames_with_people:1,maximum_simultaneous_tracks:2,average_simultaneous_tracks:2,median_simultaneous_tracks:2,earliest_peak_frame:0,earliest_peak_timestamp_seconds:0,distinct_anonymous_track_ids:2,total_track_observations:2}}
const zone:api.Zone={id:'z',video_id:'v',name:'Path',description:'Pedestrian route',polygon,active:true,analysis,created_at:'now',updated_at:'now'}
const video={id:'v',width:640,height:360,has_annotated_preview:false,heatmap_analysis:{schema_version:1,grid_width:2,grid_height:1,raw_counts:[[1,3]],total_valid_spatial_observations:4,maximum_cell_observation_count:3,hottest_cell:[1,0],hottest_cell_center:{x:.75,y:.5}}} as api.Video
beforeEach(()=>{vi.clearAllMocks();vi.mocked(api.listZones).mockResolvedValue([]);vi.mocked(api.createZone).mockResolvedValue(zone);vi.mocked(api.deleteZone).mockResolvedValue()})
async function ready(){await waitFor(()=>expect(screen.getByRole('button',{name:'Create zone'})).toBeEnabled())}
function draw(){const svg=screen.getByRole('img');vi.spyOn(svg,'getBoundingClientRect').mockReturnValue({left:0,top:0,width:640,height:360} as DOMRect);for(const p of polygon)fireEvent.click(svg,{clientX:p.x*640,clientY:p.y*360})}

test('renders raw heatmap summary and toggles layers',async()=>{
  render(<SpatialResults video={video}/>);await ready()
  expect(screen.getByText(/4 total spatial observations/)).toBeInTheDocument()
  expect(screen.getByText(/normalized center \(0.750, 0.500\)/)).toBeInTheDocument()
  expect(screen.getByLabelText('Observation heatmap').querySelectorAll('rect')).toHaveLength(2)
  fireEvent.click(screen.getByLabelText('Show heatmap'))
  expect(screen.queryByLabelText('Observation heatmap')).not.toBeInTheDocument()
  fireEvent.click(screen.getByLabelText('Show heatmap'))
  expect(screen.getByLabelText('Observation heatmap')).toBeInTheDocument()
})

test('creates normalized polygon, undo, clear and cancel',async()=>{
  render(<SpatialResults video={video}/>);await ready();fireEvent.click(screen.getByRole('button',{name:'Create zone'}))
  expect(screen.getByRole('button',{name:'Save zone'})).toBeDisabled()
  fireEvent.change(screen.getByLabelText('Zone name'),{target:{value:'Path'}});draw()
  fireEvent.click(screen.getByText('Undo last point'));expect(screen.getByRole('button',{name:'Save zone'})).toBeDisabled()
  fireEvent.click(screen.getByText('Clear points'));expect(screen.getByText(/0 \/ 50 vertices/)).toBeInTheDocument()
  draw();fireEvent.click(screen.getByText('Save zone'))
  await waitFor(()=>expect(api.createZone).toHaveBeenCalledWith('v',{name:'Path',description:null,polygon,active:true}))
  expect(await screen.findByRole('button',{name:'Path'})).toHaveAttribute('aria-pressed','true')
  fireEvent.click(screen.getByText('Edit selected zone'));fireEvent.click(screen.getByText('Cancel'))
  expect(api.updateZone).not.toHaveBeenCalled()
})

test('selects, renames, edits polygon, activates and deletes',async()=>{
  vi.mocked(api.listZones).mockResolvedValue([zone]);render(<SpatialResults video={video}/>);await ready()
  expect(screen.getByLabelText('Zone count timeline')).toBeInTheDocument()
  expect(within(screen.getByLabelText('Selected zone analytics')).getByText('Peak simultaneous tracks')).toBeInTheDocument()
  fireEvent.click(screen.getByText('Edit selected zone'))
  fireEvent.change(screen.getByLabelText('Zone name'),{target:{value:'Entrance'}})
  vi.mocked(api.updateZone).mockResolvedValue({...zone,name:'Entrance'})
  fireEvent.click(screen.getByText('Save zone'))
  expect(await screen.findByRole('button',{name:'Entrance'})).toBeInTheDocument()
  vi.mocked(api.updateZone).mockResolvedValue({...zone,name:'Entrance',active:false,analysis:null})
  fireEvent.click(screen.getByText('Deactivate zone'))
  expect(await screen.findByText(/Zone inactive/)).toBeInTheDocument()
  vi.mocked(api.updateZone).mockResolvedValue({...zone,name:'Entrance'})
  fireEvent.click(screen.getByText('Reactivate zone'))
  await waitFor(()=>expect(screen.getByText('Deactivate zone')).toBeEnabled())
  fireEvent.click(screen.getByText('Delete selected zone'))
  await waitFor(()=>expect(api.deleteZone).toHaveBeenCalledWith('v','z'))
  expect(await screen.findByText('No zones yet.')).toBeInTheDocument()
})

test('retains invalid polygon draft on server rejection',async()=>{
  vi.mocked(api.createZone).mockRejectedValue(new api.ApiError(422,'Polygon must not self-intersect'))
  render(<SpatialResults video={video}/>);await ready();fireEvent.click(screen.getByRole('button',{name:'Create zone'}));draw()
  fireEvent.change(screen.getByLabelText('Zone name'),{target:{value:'Bad'}});fireEvent.click(screen.getByText('Save zone'))
  expect(await screen.findByRole('alert')).toHaveTextContent('Polygon must not self-intersect')
  expect(screen.getByLabelText('Zone name')).toHaveValue('Bad')
})

test('reports ownership/API failure',async()=>{
  vi.mocked(api.listZones).mockRejectedValue(new api.ApiError(404,'Video not found'))
  render(<SpatialResults video={video}/>);expect(await screen.findByRole('alert')).toHaveTextContent('Unable to load zones')
})

test('backfills old heatmap from stored tracking',async()=>{
  vi.mocked(api.generateHeatmap).mockResolvedValue(video.heatmap_analysis!)
  render(<SpatialResults video={{...video,heatmap_analysis:null}}/>);await ready()
  fireEvent.click(screen.getByText('Generate heatmap from stored tracking'))
  expect(await screen.findByText(/4 total spatial observations/)).toBeInTheDocument()
})
