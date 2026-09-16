import { beforeEach, expect, test, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AlertResults, AlertEvents } from './AlertResults'
import * as api from '../services/alerts'
vi.mock('../services/alerts',async importOriginal=>({...await importOriginal<typeof import('../services/alerts')>(),listRules:vi.fn(),listAlerts:vi.fn(),getAlertSummary:vi.fn(),saveRule:vi.fn(),toggleRule:vi.fn(),deleteRule:vi.fn()}))
vi.mock('../services/apiClient',()=>({listZones:vi.fn().mockResolvedValue([{id:'z',name:'Path',active:true}])}))
const rule:api.Rule={id:'r',video_id:'v',name:'Count',description:null,rule_type:'CROWD_COUNT_ABOVE',scope:'VIDEO',severity:'INFO',enabled:true,zone_id:null,configuration:{threshold:1}}
beforeEach(()=>{vi.clearAllMocks();vi.mocked(api.listRules).mockResolvedValue([]);vi.mocked(api.listAlerts).mockResolvedValue([]);vi.mocked(api.getAlertSummary).mockResolvedValue({total_events:0,maximum_operational_risk:'NORMAL',configured_rules:0,enabled_rules:0,events_by_severity:{INFO:0,WARNING:0,CRITICAL:0},earliest_alert_seconds:null})})
test('empty state, dynamic builder, zone selector and natural-language preview',async()=>{
  const user=userEvent.setup();render(<AlertResults videoId="v"/>);await screen.findByText('Maximum operational risk: NORMAL')
  await user.click(screen.getByText('Create alert rule'));await user.type(screen.getByLabelText('Rule name'),'Path presence')
  await user.selectOptions(screen.getByLabelText('Rule type'),'ZONE_PRESENCE');await user.selectOptions(screen.getByLabelText('Monitoring zone'),'z')
  expect(screen.queryByLabelText('Minimum crowd level')).not.toBeInTheDocument()
  expect(screen.getByText(/Trigger WARNING when at least 1 anonymous tracked persons are observed in Path/)).toBeInTheDocument()
  await user.click(screen.getByText('Save alert rule'));await waitFor(()=>expect(api.saveRule).toHaveBeenCalledWith('v',expect.objectContaining({scope:'ZONE',zone_id:'z',configuration:{minimum_presence_count:1,minimum_duration_seconds:0,maximum_gap_seconds:1}}),undefined))
})
test('edit, toggle and delete rules',async()=>{
  vi.mocked(api.listRules).mockResolvedValue([rule]);const user=userEvent.setup();render(<AlertResults videoId="v"/>);await screen.findByText('Edit Count')
  await user.click(screen.getByText('Disable Count'));await waitFor(()=>expect(api.toggleRule).toHaveBeenCalledWith('v','r',false))
  await user.click(screen.getByText('Edit Count'));await user.clear(screen.getByLabelText('Count threshold'));await user.type(screen.getByLabelText('Count threshold'),'9');await user.click(screen.getByText('Save alert rule'))
  await waitFor(()=>expect(api.saveRule).toHaveBeenCalledWith('v',expect.objectContaining({configuration:expect.objectContaining({threshold:9})}),'r'))
  await user.click(screen.getByText('Delete Count'));await waitFor(()=>expect(api.deleteRule).toHaveBeenCalledWith('v','r'))
})
test('API validation errors stay visible',async()=>{
  vi.mocked(api.saveRule).mockRejectedValue(new Error('Invalid threshold'));const user=userEvent.setup();render(<AlertResults videoId="v"/>);await screen.findByText('Maximum operational risk: NORMAL');await user.click(screen.getByText('Create alert rule'));await user.type(screen.getByLabelText('Rule name'),'Bad');await user.click(screen.getByText('Save alert rule'));expect(await screen.findByRole('alert')).toHaveTextContent('Invalid threshold')
})
test('load failure',async()=>{vi.mocked(api.listRules).mockRejectedValue(new Error('offline'));render(<AlertResults videoId="v"/>);expect(await screen.findByRole('alert')).toHaveTextContent('Unable to load')})
test('history evidence and severity filter',async()=>{
  const event={id:'e',video_id:'v',rule_id:null,zone_id:null,rule_name:'Count',rule_type:'CROWD_COUNT_ABOVE',severity:'INFO',condition_start_seconds:0,trigger_seconds:1,end_seconds:2,state:'HISTORICAL',evidence:{metric:'observed_crowd_count',threshold:1,trigger_value:2,peak_value:3,minimum_duration_seconds:1,observed_duration_seconds:2,maximum_gap_seconds:1,closure:'end_of_analysis',zone_name:null,baseline_seconds:null,baseline_count:null,current_count:null}} as api.AlertEvent
  const user=userEvent.setup();render(<AlertEvents events={[event]} videoNames={{v:'clip.mp4'}}/>);await user.click(screen.getByText('Why this alert fired'));expect(screen.getByText(/2 at trigger, against configured threshold 1/)).toBeVisible();expect(screen.getByText(/Video: clip.mp4/)).toBeInTheDocument();await user.selectOptions(screen.getByLabelText('Filter severity'),'CRITICAL');expect(screen.getByText(/No alert events match/)).toBeInTheDocument()
})
