import { render, screen, waitFor } from '@testing-library/react'
import { vi } from 'vitest'
import { VideoPreview } from './VideoPreview'
import { getVideoPreview } from '../services/apiClient'
vi.mock('../services/apiClient', () => ({getVideoPreview:vi.fn()}))

test('renders authenticated blob preview and revokes its URL', async () => {
  vi.mocked(getVideoPreview).mockResolvedValue(new Blob(['preview']))
  URL.createObjectURL = vi.fn(() => 'blob:authenticated-preview')
  URL.revokeObjectURL = vi.fn()
  const view = render(<VideoPreview videoId="owner-video"/>)
  expect(await screen.findByRole('img')).toHaveAttribute('src','blob:authenticated-preview')
  expect(getVideoPreview).toHaveBeenCalledWith('owner-video')
  view.unmount()
  expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:authenticated-preview')
})

test('handles failed preview fetch safely', async () => {
  vi.mocked(getVideoPreview).mockRejectedValue(new Error('unavailable'))
  render(<VideoPreview videoId="missing"/>)
  await waitFor(() => expect(getVideoPreview).toHaveBeenCalledWith('missing'))
  expect(screen.queryByRole('img')).not.toBeInTheDocument()
  expect(screen.getByText('Annotated preview unavailable.')).toBeInTheDocument()
})
