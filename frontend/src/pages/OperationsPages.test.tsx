import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'
import { IncidentsPage } from './IncidentsPage'
import { AlertEvents } from '../components/AlertResults'
import type { AlertEvent } from '../services/alerts'
import { operationsApi, downloadReport, blankIncident, type Incident } from '../services/operations'
vi.mock('../services/operations',async original=>({...await original<typeof import('../services/operations')>(),operationsApi:vi.fn(),downloadReport:vi.fn()}))
const time='2026-09-26T10:00:00Z'
const incident:Incident={...blankIncident(),id:'incident1',title:'Queue review',description:'Operator note',occurred_at:time,context:{},created_at:time,updated_at:time}
let incidentRows:Incident[]
beforeEach(()=>{
  vi.clearAllMocks();incidentRows=[incident]
  vi.mocked(operationsApi).mockImplementation(async(path,method='GET',body)=>{
    if(path==='/incidents/options')return {cameras:[{id:'c1',label:'Entrance'}],videos:[],sessions:[]}
    if(path.startsWith('/incidents/alert-context'))return {title:'Review: Queue threshold',severity:'WARNING',description:'Review source alert',occurred_at:null,alert_event_id:'alert1',video_id:'v1',context:{label:'Queue threshold',rule_type:'CROWD_COUNT_ABOVE',recorded_at:time,video_offset_seconds:3}}
    if(path==='/incidents/incident1'){
      if(method==='PUT'){incidentRows=[{...incident,...body as object}];return incidentRows[0]}
      return incidentRows[0]
    }
    if(path==='/incidents'&&method==='POST'){const created={...incident,...body as object};incidentRows=[created];return created}
    if(path.startsWith('/incidents'))return incidentRows
    throw new Error('Unexpected path '+path)
  })
})
function incidents(url='/incidents'){return render(<MemoryRouter initialEntries={[url]}><IncidentsPage/></MemoryRouter>)}
test('incident create, edit, detail and resolve workflow',async()=>{
  incidents();await screen.findByText('Queue review')
  expect(screen.queryByLabelText('Filter event')).not.toBeInTheDocument()
  expect(operationsApi).not.toHaveBeenCalledWith('/events')
  fireEvent.click(screen.getByRole('button',{name:'Create incident'}))
  expect(screen.queryByLabelText('Event',{exact:true})).not.toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Title'),{target:{value:'Gate review'}})
  fireEvent.click(screen.getByRole('button',{name:'Save incident'}))
  await screen.findByLabelText('Incident detail')
  expect(operationsApi).toHaveBeenCalledWith('/incidents','POST',expect.objectContaining({title:'Gate review'}))
  fireEvent.click(await screen.findByRole('button',{name:'Edit Gate review'}))
  fireEvent.change(screen.getByLabelText('Description'),{target:{value:'Reviewed by operator'}})
  fireEvent.click(screen.getByRole('button',{name:'Save incident'}))
  await waitFor(()=>expect(within(screen.getByLabelText('Incident detail')).getByText('Reviewed by operator')).toBeInTheDocument())
  fireEvent.click(screen.getByRole('button',{name:'Resolve Gate review'}))
  await waitFor(()=>expect(operationsApi).toHaveBeenCalledWith('/incidents/incident1','PUT',expect.objectContaining({status:'RESOLVED'})))
})
test('incident filters and CSV use same query',async()=>{
  incidents();await screen.findByText('Queue review')
  fireEvent.change(screen.getByLabelText('Filter status'),{target:{value:'OPEN'}})
  fireEvent.change(screen.getByLabelText('Filter severity'),{target:{value:'WARNING'}})
  await waitFor(()=>expect(operationsApi).toHaveBeenCalledWith('/incidents?status=OPEN&severity=WARNING'))
  fireEvent.click(screen.getByRole('button',{name:'Download CSV'}))
  await waitFor(()=>expect(downloadReport).toHaveBeenCalledWith('?status=OPEN&severity=WARNING'))
})
test('alert draft is reviewed before explicit incident creation',async()=>{
  incidents('/incidents?source=video&alert_id=alert1')
  expect(await screen.findByDisplayValue('Review: Queue threshold')).toBeInTheDocument()
  expect(screen.getByText(/Video capture time is unknown/)).toBeInTheDocument()
  expect(operationsApi).not.toHaveBeenCalledWith('/incidents','POST',expect.anything())
  fireEvent.click(screen.getByRole('button',{name:'Save incident'}))
  await waitFor(()=>expect(operationsApi).toHaveBeenCalledWith('/incidents','POST',expect.objectContaining({alert_event_id:'alert1',video_id:'v1'})))
})
test('incident empty state',async()=>{incidentRows=[];incidents();expect(await screen.findByText('No incidents match')).toBeInTheDocument()})
test('incident and export errors remain visible',async()=>{
  vi.mocked(downloadReport).mockRejectedValue(new Error('Report unavailable'))
  incidents();await screen.findByText('Queue review');fireEvent.click(screen.getByRole('button',{name:'Download CSV'}))
  expect(await screen.findByRole('alert')).toHaveTextContent('Report unavailable')
})
test('incident load failure',async()=>{vi.mocked(operationsApi).mockRejectedValue(new Error('offline'));incidents();await waitFor(()=>expect(screen.getAllByRole('alert').map(e=>e.textContent).join(' ')).toContain('Unable to load incidents'))})
test('existing alert history links to reviewed incident workflow',()=>{
  const alert={id:'alert1',video_id:'v',rule_id:null,rule_name:'Count',rule_type:'CROWD_COUNT_ABOVE',severity:'INFO',condition_start_seconds:0,trigger_seconds:1,end_seconds:2,state:'HISTORICAL',evidence:{minimum_duration_seconds:0,observed_duration_seconds:1,maximum_gap_seconds:1,baseline_seconds:null}} as AlertEvent
  render(<AlertEvents events={[alert]}/>);expect(screen.getByRole('link',{name:'Create incident'})).toHaveAttribute('href','/incidents?source=video&alert_id=alert1')
})
