import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { vi } from 'vitest'
import { AnalyticsPage } from './AnalyticsPage'
import { getAnalytics, getSessionAnalytics, type Analytics, type SessionAnalytics } from '../services/analytics'
vi.mock('../services/analytics',()=>({getAnalytics:vi.fn(),getSessionAnalytics:vi.fn()}))
vi.mock('recharts',async()=>{
  const React=await import('react')
  const box=({children}:{children?:import('react').ReactNode})=>React.createElement('div',null,children)
  return {ResponsiveContainer:box,BarChart:box,LineChart:box,Bar:()=>null,Line:()=>null,CartesianGrid:()=>null,Legend:()=>null,Tooltip:()=>null,XAxis:()=>null,YAxis:()=>null}
})
const metrics={observations:2,average_count:3,peak_count:5,average_image_occupancy:.25,average_image_space_concentration:.4,risk_distribution:{HIGH:1},crowd_levels:{LOW:2},maximum_crowd_levels:{LOW:1}}
const session:SessionAnalytics={id:'session1',camera_name:'Entrance',status:'STOPPED',started_at:'2026-09-25T10:00:00Z',stopped_at:'2026-09-25T10:18:00Z',duration_seconds:1080,processed_frames:2,dropped_frames:1,average_count:3,peak_count:5,maximum_crowd_level:'LOW',maximum_operational_risk:'HIGH',final_operational_risk:'NORMAL',summary:'Monitoring ran for 18.0 minutes. Peak observed crowd count was 5.',zones:[{id:'z',name:'Entry zone',peak_count:2}],alerts:{total:1,by_severity:{WARNING:1},by_type:{ZONE_PRESENCE:1}},alert_history:[{id:'e',created_at:'2026-09-25T10:10:00Z',resolved_at:null,severity:'WARNING',rule_type:'ZONE_PRESENCE',rule_name:'Presence rule',zone_name:'Entry zone'}]}
const fixture:Analytics={range:'30d',total_analyzed_videos:1,total_live_sessions:1,video_statuses:{completed:1},session_statuses:{STOPPED:1},alerts:session.alerts,video:metrics,live:{...metrics,average_image_occupancy:null,average_image_space_concentration:null},history:[],history_total_days:0,peak_periods:{video:null,live:null},sessions:[session],video_zones:[]}
beforeEach(()=>{vi.resetAllMocks();vi.mocked(getAnalytics).mockResolvedValue(fixture);vi.mocked(getSessionAnalytics).mockResolvedValue(session)})
test('loading and populated dashboard metrics and three charts',async()=>{
  render(<AnalyticsPage/>);expect(screen.getByRole('status')).toHaveTextContent('Loading analytics')
  await screen.findByText('Analyzed videos')
  expect(screen.getByText('Analyzed videos').parentElement).toHaveTextContent('1')
  expect(screen.getByText('Average image occupancy').parentElement).toHaveTextContent('25.0%')
  for(const name of ['Crowd history','Alert severity','Operational risk distribution'])expect(screen.getByLabelText(name)).toBeInTheDocument()
  expect(screen.getByText(session.summary!)).toBeInTheDocument()
})
test('time selector requests selected range',async()=>{
  render(<AnalyticsPage/>);await screen.findByText('Analyzed videos')
  fireEvent.change(screen.getByLabelText('Time range'),{target:{value:'7d'}})
  await waitFor(()=>expect(getAnalytics).toHaveBeenLastCalledWith('7d'))
  await screen.findByText('Analyzed videos')
  fireEvent.change(screen.getByLabelText('Time range'),{target:{value:'all'}})
  await waitFor(()=>expect(getAnalytics).toHaveBeenLastCalledWith('all'))
})
test('session drilldown includes metadata, summary, zones and alert history',async()=>{
  render(<AnalyticsPage/>);fireEvent.click(await screen.findByRole('button',{name:'Inspect session session1'}))
  await screen.findByText(/Presence rule.*WARNING/)
  const detail=within(screen.getByLabelText('Session details'))
  expect(detail.getByText(session.summary!)).toBeInTheDocument()
  expect(detail.getByText('Entry zone: 2')).toBeInTheDocument()
  expect(detail.getByText('Processed frames').parentElement).toHaveTextContent('2')
  expect(getSessionAnalytics).toHaveBeenCalledWith('session1')
  fireEvent.click(detail.getByText('Close details'));expect(screen.queryByLabelText('Session details')).not.toBeInTheDocument()
})
test('empty state preserves unavailable measurements',async()=>{
  vi.mocked(getAnalytics).mockResolvedValue({...fixture,total_analyzed_videos:0,total_live_sessions:0,sessions:[],video:{...metrics,average_count:null},live:{...metrics,average_count:null}})
  render(<AnalyticsPage/>);expect(await screen.findByText('No analytics yet')).toBeInTheDocument()
  expect(screen.getByText('No sessions in this range.')).toBeInTheDocument()
  expect(screen.getAllByText('Unavailable').length).toBeGreaterThan(0)
})
test('API error state',async()=>{
  vi.mocked(getAnalytics).mockRejectedValue(new Error('failed'))
  render(<AnalyticsPage/>);expect(await screen.findByRole('alert')).toHaveTextContent('Unable to load analytics')
})
test('session error state',async()=>{
  vi.mocked(getSessionAnalytics).mockRejectedValue(new Error('failed'))
  render(<AnalyticsPage/>);fireEvent.click(await screen.findByRole('button',{name:'Inspect session session1'}))
  expect(await screen.findByRole('alert')).toHaveTextContent('Unable to load session details')
})

