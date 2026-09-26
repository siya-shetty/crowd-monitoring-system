import { afterEach, expect, test, vi } from 'vitest'
import { downloadReport } from './operations'
import { storeToken } from './apiClient'
afterEach(()=>{vi.restoreAllMocks();vi.unstubAllGlobals();localStorage.clear()})
test('CSV download sends auth in headers and uses a safe filename',async()=>{
  storeToken('fixture-token')
  const fetch=vi.fn().mockResolvedValue(new Response('incident_id,title\n1,Review',{headers:{'Content-Type':'text/csv'}}))
  vi.stubGlobal('fetch',fetch)
  Object.defineProperty(URL,'createObjectURL',{configurable:true,value:vi.fn().mockReturnValue('blob:report')})
  Object.defineProperty(URL,'revokeObjectURL',{configurable:true,value:vi.fn()})
  const click=vi.spyOn(HTMLAnchorElement.prototype,'click').mockImplementation(function(this:HTMLAnchorElement){expect(this.download).toBe('incidents.csv')})
  await downloadReport('?status=OPEN')
  expect(fetch).toHaveBeenCalledWith(expect.stringContaining('/incidents/export.csv?status=OPEN'),{headers:{Authorization:'Bearer fixture-token'}})
  expect(click).toHaveBeenCalledOnce()
})
test('export failure does not create a download',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({detail:'Not authorized'}),{status:401})))
  const event=vi.spyOn(window,'dispatchEvent')
  await expect(downloadReport()).rejects.toThrow('Not authorized')
  expect(event).toHaveBeenCalledWith(expect.objectContaining({type:'auth:unauthorized'}))
})
