import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { vi } from 'vitest'
import { LivePage } from './LivePage'
import { cameraError } from '../lib/camera'
import { liveApi, sendFrame } from '../services/live'

vi.mock('../services/live',()=>({liveApi:vi.fn(),sendFrame:vi.fn()}))
const camera={id:'camera',name:'Desk',enabled:true,source_type:'BROWSER'}
const session={id:'session',camera_id:'camera',status:'RUNNING',processed_frame_count:2,dropped_frame_count:1,summary:{},latest_snapshot:{observed_crowd_count:3,crowd_level:'LOW',image_occupancy_ratio:.2,crowd_concentration:.5,current_operational_risk:'HIGH',active_alert_count:1,processing_duration_seconds:.1,zones:{z:{name:'Entry',active_tracks_in_zone:2}}}}
const stopTrack=vi.fn()
beforeEach(()=>{
  vi.clearAllMocks()
  Object.defineProperty(window,'isSecureContext',{configurable:true,value:true})
  Object.defineProperty(navigator,'mediaDevices',{configurable:true,value:{getUserMedia:vi.fn().mockResolvedValue({getTracks:()=>[{stop:stopTrack}],getVideoTracks:()=>[]})}})
  vi.spyOn(HTMLMediaElement.prototype,'play').mockResolvedValue()
  vi.mocked(liveApi).mockImplementation(async(path,method)=>{
    if(path==='/cameras')return method==='POST'?camera:[camera]
    if(path==='/live/config')return {target_fps:3,capture_width:960,capture_height:540,max_frame_bytes:524288}
    if(path==='/cameras/camera/sessions')return method==='POST'?session:[]
    if(path.endsWith('/stop'))return {...session,status:'STOPPED'}
    if(path==='/live/sessions/session')return session
    return []
  })
  vi.mocked(sendFrame).mockResolvedValue(session.latest_snapshot as never)
})

test('camera creation, permission, monitoring metrics, stop and cleanup',async()=>{
  const view=render(<LivePage/>)
  await screen.findByRole('option',{name:'Desk'})
  fireEvent.change(screen.getByLabelText('New browser camera name'),{target:{value:'New camera'}})
  fireEvent.click(screen.getByRole('button',{name:'Register camera'}))
  await waitFor(()=>expect(liveApi).toHaveBeenCalledWith('/cameras','POST',{name:'New camera',source_type:'BROWSER'}))
  await waitFor(()=>expect(screen.getByRole('button',{name:'Start Camera'})).toBeEnabled())
  fireEvent.click(screen.getByRole('button',{name:'Start Camera'}))
  await screen.findByText(/Camera active/)
  fireEvent.click(screen.getByRole('button',{name:'Start Monitoring'}))
  await screen.findByText('HIGH')
  expect(screen.getByText('Entry: 2 active tracks')).toBeInTheDocument()
  expect(screen.getByText('Processed 2 · Dropped 1')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button',{name:'Stop Monitoring / Camera'}))
  await screen.findByText('Session STOPPED')
  expect(stopTrack).toHaveBeenCalledTimes(1)
  view.unmount()
})

test('insecure context and denied permission are actionable',async()=>{
  Object.defineProperty(window,'isSecureContext',{value:false})
  render(<LivePage/>);await screen.findByRole('option',{name:'Desk'})
  fireEvent.click(screen.getByRole('button',{name:'Start Camera'}))
  expect(await screen.findByRole('alert')).toHaveTextContent('HTTPS or localhost')
  Object.defineProperty(window,'isSecureContext',{value:true})
  vi.mocked(navigator.mediaDevices.getUserMedia).mockRejectedValue(new DOMException('denied','NotAllowedError'))
  fireEvent.click(screen.getByRole('button',{name:'Start Camera'}))
  await waitFor(()=>expect(screen.getByRole('alert')).toHaveTextContent('Camera permission denied'))
})

test.each(['NotFoundError','NotReadableError','OverconstrainedError'])('maps %s without exposing browser details',name=>{
  expect(cameraError(new DOMException('private stack',name))).not.toContain('private stack')
})

test('pending permission is released after unmount',async()=>{
  let resolve!:(value:MediaStream)=>void
  vi.mocked(navigator.mediaDevices.getUserMedia).mockReturnValue(new Promise(r=>{resolve=r}))
  const view=render(<LivePage/>);await screen.findByRole('option',{name:'Desk'})
  fireEvent.click(screen.getByRole('button',{name:'Start Camera'}));view.unmount()
  await act(async()=>resolve({getTracks:()=>[{stop:stopTrack}]} as unknown as MediaStream))
  expect(stopTrack).toHaveBeenCalledTimes(1)
})

test('frame uploads do not overlap and unmount stops the session',async()=>{
  let resolve!:()=>void
  vi.mocked(sendFrame).mockImplementation(()=>new Promise(r=>{resolve=()=>r(session.latest_snapshot as never)}))
  Object.defineProperties(HTMLMediaElement.prototype,{readyState:{configurable:true,get:()=>4}})
  Object.defineProperties(HTMLVideoElement.prototype,{videoWidth:{configurable:true,get:()=>640},videoHeight:{configurable:true,get:()=>360}})
  vi.spyOn(HTMLCanvasElement.prototype,'getContext').mockReturnValue({drawImage:vi.fn()} as never)
  vi.spyOn(HTMLCanvasElement.prototype,'toBlob').mockImplementation(callback=>callback(new Blob(['frame'],{type:'image/jpeg'})))
  const view=render(<LivePage/>);await screen.findByRole('option',{name:'Desk'})
  fireEvent.click(screen.getByRole('button',{name:'Start Camera'}));await screen.findByText(/Camera active/)
  fireEvent.click(screen.getByRole('button',{name:'Start Monitoring'}))
  await waitFor(()=>expect(sendFrame).toHaveBeenCalledTimes(1))
  await act(async()=>{await new Promise(r=>setTimeout(r,400))})
  expect(sendFrame).toHaveBeenCalledTimes(1)
  await act(async()=>resolve())
  view.unmount()
  expect(stopTrack).toHaveBeenCalledTimes(1)
  expect(liveApi).toHaveBeenCalledWith('/live/sessions/session/stop','POST')
})
