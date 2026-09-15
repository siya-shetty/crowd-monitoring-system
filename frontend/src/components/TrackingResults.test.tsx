import { render, screen, fireEvent } from '@testing-library/react'
import { TrackingResults } from './TrackingResults'
import type { TrackingAnalysis } from '../services/apiClient'

const track = (id: number) => ({ track_id:id, first_observed_frame:0, last_observed_frame:1, first_observed_timestamp:0, last_observed_timestamp:.1, observation_count:2, average_confidence:.8, trajectory:[{frame_index:0,timestamp_seconds:0,center_x:.1,center_y:.2},{frame_index:1,timestamp_seconds:.1,center_x:.2,center_y:.3}] })
const analysis: TrackingAnalysis = { schema_version:1, summary:{tracker:'ByteTrack',frame_stride:1,track_high_threshold:.25,track_low_threshold:.1,track_match_threshold:.8,track_buffer:30,processed_frames:2,frames_with_active_tracks:2,maximum_simultaneous_active_tracks:2,average_active_tracks_per_processed_frame:2,distinct_track_ids:2,average_track_observation_length:2,longest_track_observation_length:2}, frames:[{frame_index:0,timestamp_seconds:0,active_track_count:2,tracked_persons:[]},{frame_index:1,timestamp_seconds:.1,active_track_count:2,tracked_persons:[]}], tracks:[track(1), track(3)] }

test('renders tracking metrics, disclaimer, and an accessible active track timeline', () => {
  render(<TrackingResults analysis={analysis} width={100} height={100}/>)
  expect(screen.getByText('2 distinct anonymous track IDs')).toBeInTheDocument()
  expect(screen.getByText(/do not represent verified unique individuals/)).toBeInTheDocument()
  expect(screen.getByText(/ByteTrack/)).toBeInTheDocument()
  expect(screen.getByLabelText('Active track timeline')).toBeInTheDocument()
  expect(screen.getByText('Maximum simultaneous active tracks')).toBeInTheDocument()
  expect(screen.getByText('0.10')).toBeInTheDocument()
})

test('selects real track histories and renders normalized center points', () => {
  render(<TrackingResults analysis={analysis} width={100} height={100}/>)
  fireEvent.change(screen.getByRole('combobox'), {target:{value:'3'}})
  const path = screen.getByRole('img', {name:/Track 3/})
  expect(path.querySelector('polyline')).toHaveAttribute('points','10,20 20,30')
  expect(screen.getByText(/Track 3: frames 0–1/)).toBeInTheDocument()
})

test('empty tracking results do not invent trajectories', () => {
  render(<TrackingResults analysis={{...analysis,tracks:[]}} width={100} height={100}/>)
  expect(screen.getByText('No confirmed anonymous tracks were observed.')).toBeInTheDocument()
  expect(screen.queryByRole('img')).not.toBeInTheDocument()
})
