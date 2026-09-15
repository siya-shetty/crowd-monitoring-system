import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'
import { VideosPage } from './VideosPage'

vi.mock('../services/apiClient', () => ({ listVideos: vi.fn().mockResolvedValue([{ id:'1', original_filename:'people.mp4', file_size:1, status:'completed', width:32, height:24, fps:10, duration_seconds:.5, frame_count:5, error_message:null, created_at:'2026-01-01', has_annotated_preview:false, detection_frames:[{frame_index:0,timestamp_seconds:0,person_count:4,detections:[]}], detection_summary:{model:'yolo11n.pt',confidence_threshold:.35,frame_stride:5,sampled_frames_processed:1,frames_with_people:1,total_person_detections:4,maximum_persons_in_sampled_frame:4,average_persons_per_sampled_frame:4,processing_duration_seconds:1} }]), uploadVideo:vi.fn(), deleteVideo:vi.fn(), ApiError:class ApiError extends Error {} }))
test('renders actual sampled person detection summary without claiming unique people', async () => { render(<MemoryRouter><VideosPage/></MemoryRouter>); expect(await screen.findByText(/4 total person detections/)).toBeInTheDocument(); expect(screen.getByText(/not unique people/)).toBeInTheDocument(); expect(screen.getByText(/yolo11n.pt/)).toBeInTheDocument(); expect(screen.getAllByText(/sampled frames/).length).toBeGreaterThan(1) })
