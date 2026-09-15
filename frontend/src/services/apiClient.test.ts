import { afterEach, expect, test, vi } from 'vitest'
import { deleteVideo, getVideoPreview, storeToken } from './apiClient'
afterEach(() => { vi.unstubAllGlobals(); localStorage.clear() })
test('successful delete accepts 204 without attempting JSON parsing', async () => {
  storeToken('test-token')
  const fetch = vi.fn().mockResolvedValue(new Response(null, {status:204}))
  vi.stubGlobal('fetch', fetch)
  await expect(deleteVideo('video')).resolves.toBeUndefined()
  const headers = fetch.mock.calls[0][1].headers as Headers
  expect(headers.get('Authorization')).toBe('Bearer test-token')
})
test('preview uses JWT headers without a token in its URL', async () => {
  storeToken('test-token')
  const fetch = vi.fn().mockResolvedValue(new Response('jpeg'))
  vi.stubGlobal('fetch', fetch)
  await getVideoPreview('video')
  expect(fetch.mock.calls[0][0]).toMatch(/\/videos\/video\/preview$/)
  expect(fetch.mock.calls[0][1].headers.Authorization).toBe('Bearer test-token')
})
