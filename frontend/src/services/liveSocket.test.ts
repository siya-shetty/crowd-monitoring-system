import { vi, expect, test, beforeEach, afterEach } from 'vitest'
import { connectLive, parseEvent } from './liveSocket'
import { liveApi } from './live'
vi.mock('./live',()=>({liveApi:vi.fn()}))
class Socket {
  static all:Socket[]=[]
  onopen=()=>{}; onclose=()=>{}; onerror=()=>{}; onmessage=(_e:{data:string})=>{}
  send=vi.fn();close=vi.fn(()=>this.onclose())
  constructor(){Socket.all.push(this)}
}
const event=(sequence=1,status='RUNNING')=>({version:1,event:'session.snapshot',session_id:'s',sequence,emitted_at:new Date().toISOString(),data:{id:'s',status,processed_frame_count:1,dropped_frame_count:0,is_stale:false,error_summary:null,latest_snapshot:null,alerts:[]}})
beforeEach(()=>{vi.useFakeTimers();Socket.all=[];vi.stubGlobal('WebSocket',Socket);vi.mocked(liveApi).mockResolvedValue({ticket:'short-ticket'})})
afterEach(()=>{vi.useRealTimers();vi.unstubAllGlobals();vi.clearAllMocks()})
test('validates envelopes and rejects malformed state',()=>{
  expect(parseEvent(JSON.stringify(event()),'s')).not.toBeNull()
  expect(parseEvent('{broken','s')).toBeNull()
  expect(parseEvent(JSON.stringify(event()),'foreign')).toBeNull()
  expect(parseEvent(JSON.stringify({...event(),data:{...event().data,latest_snapshot:{}}}),'s')).toBeNull()
})
test('authenticates, rejects old events, gets fresh ticket on reconnect and stops intentionally',async()=>{
  const state=vi.fn(),health=vi.fn(),stop=connectLive('s',state,health)
  await vi.advanceTimersByTimeAsync(0)
  const a=Socket.all[0];a.onopen();expect(a.send).toHaveBeenCalledWith('short-ticket')
  a.onmessage({data:JSON.stringify(event(2))});a.onmessage({data:JSON.stringify(event(1))});a.onmessage({data:'bad'})
  expect(state).toHaveBeenCalledTimes(1)
  a.onclose();await vi.advanceTimersByTimeAsync(1000)
  expect(liveApi).toHaveBeenCalledTimes(2)
  stop();await vi.advanceTimersByTimeAsync(20000)
  expect(Socket.all).toHaveLength(2)
})
test('terminal state never reconnects and heartbeat responds',async()=>{
  const stop=connectLive('s',vi.fn(),vi.fn());await vi.advanceTimersByTimeAsync(0)
  const socket=Socket.all[0]
  socket.onmessage({data:'{"version":1,"event":"heartbeat"}'})
  expect(socket.send).toHaveBeenCalledWith('pong')
  socket.onmessage({data:JSON.stringify(event(1,'STOPPED'))})
  await vi.advanceTimersByTimeAsync(30000)
  expect(Socket.all).toHaveLength(1);stop()
})
