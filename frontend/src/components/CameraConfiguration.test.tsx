import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { vi } from 'vitest'
import { CameraConfiguration } from './CameraConfiguration'
import { liveApi } from '../services/live'

vi.mock('../services/live',()=>({liveApi:vi.fn()}))

test('saves normalized camera zones and sustained zone rules',async()=>{
  const points=[{x:0,y:0},{x:1,y:0},{x:1,y:1}]
  const onZones=vi.fn(),clear=vi.fn()
  vi.mocked(liveApi).mockImplementation(async(path,method)=>!method&&path.endsWith('/zones')?[{id:'z',name:'Entry',polygon:points,active:true}]:[])
  render(<CameraConfiguration cameraId="c" points={points} clear={clear} onZones={onZones}/> )
  await screen.findByRole('button',{name:'Disable zone Entry'})
  fireEvent.change(screen.getByLabelText('Zone name'),{target:{value:'New zone'}})
  fireEvent.click(screen.getByRole('button',{name:'Save drawn zone'}))
  await waitFor(()=>expect(clear).toHaveBeenCalled())
  expect(liveApi).toHaveBeenCalledWith('/cameras/c/zones','POST',{name:'New zone',polygon:points,active:true})
  fireEvent.change(screen.getByLabelText('Rule name'),{target:{value:'Presence'}})
  fireEvent.change(screen.getByLabelText('Rule type'),{target:{value:'ZONE_PRESENCE'}})
  fireEvent.change(screen.getByLabelText('Rule zone'),{target:{value:'z'}})
  fireEvent.change(screen.getByLabelText('Sustained duration (seconds)'),{target:{value:'2'}})
  expect(screen.getByText(/zone count is at least 1/)).toHaveTextContent('for 2 seconds')
  fireEvent.click(screen.getByRole('button',{name:'Create live rule'}))
  await waitFor(()=>expect(liveApi).toHaveBeenCalledWith('/cameras/c/alert-rules','POST',expect.objectContaining({scope:'ZONE',zone_id:'z',configuration:{minimum_presence_count:1,minimum_duration_seconds:2,maximum_gap_seconds:2}})))
})

test('surfaces configuration API failure',async()=>{
  vi.mocked(liveApi).mockRejectedValue(new Error('Unavailable'))
  render(<CameraConfiguration cameraId="c" points={[]} clear={vi.fn()} onZones={vi.fn()}/> )
  expect(await screen.findByRole('alert')).toHaveTextContent('Unable to load camera configuration')
})
