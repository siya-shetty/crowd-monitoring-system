import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'

import { VideosPage } from './VideosPage'

vi.mock('../services/apiClient', () => ({
  listVideos: vi.fn().mockResolvedValue([{ id: '1', original_filename: 'campus.mp4', file_size: 1048576, status: 'completed', width: 1920, height: 1080, fps: 30, duration_seconds: 12, content_type: 'video/mp4', frame_count: 360, error_message: null, created_at: '2026-09-15T00:00:00Z' }]),
  uploadVideo: vi.fn(), deleteVideo: vi.fn(),
  ApiError: class ApiError extends Error { status = 400 },
}))

test('renders upload interface and completed video metadata', async () => {
  render(<MemoryRouter><VideosPage/></MemoryRouter>)
  expect(screen.getByText('Drop a video here')).toBeInTheDocument()
  expect(await screen.findByText('campus.mp4')).toBeInTheDocument()
  expect(screen.getByText(/1920 x 1080/)).toBeInTheDocument()
})

test('rejects an unsupported selected file before upload', async () => {
  render(<MemoryRouter><VideosPage/></MemoryRouter>)
  await screen.findByText('campus.mp4')
  fireEvent.change(screen.getByLabelText('Choose video file'), { target: { files: [new File(['x'], 'notes.txt', { type: 'text/plain' })] } })
  expect(screen.getByRole('alert')).toHaveTextContent('Choose a non-empty MP4')
})
