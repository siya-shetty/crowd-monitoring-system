"""Tickets travel in the first message, never URLs or access logs."""
import asyncio
import secrets
import time
from threading import Lock
from uuid import UUID
from fastapi import APIRouter, HTTPException, Response, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool
from app.api.v1.dependencies import DatabaseSession
from app.api.v1.videos import CurrentUser
from app.api.v1.live import session_for
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.user import User
from app.websocket.manager import manager
from app.websocket.events import publish

router = APIRouter()
tickets = {}
ticket_lock = Lock()


@router.post('/live/sessions/{session_id}/ws-ticket')
def ticket(session_id: UUID, db: DatabaseSession, user: CurrentUser, response: Response):
    session_for(db, user, session_id)
    with ticket_lock:
        for key, value in list(tickets.items()):
            if value[2] <= time.monotonic():
                del tickets[key]
        if len(tickets) >= 256:
            raise HTTPException(429, 'Ticket capacity reached')
        if sum(item[0] == user.id for item in tickets.values()) >= 8:
            raise HTTPException(429, 'Outstanding ticket limit reached')
        value = secrets.token_urlsafe(32)
        tickets[value] = (user.id, session_id, time.monotonic()+30)
    response.headers['Cache-Control'] = 'no-store'
    return {'ticket': value, 'expires_in': 30}


def consume(value, session_id):
    with ticket_lock:
        item = tickets.pop(value, None)
    if not item or item[1] != session_id or item[2] <= time.monotonic():
        raise ValueError('Invalid ticket')
    return item[0]


def refresh(user_id, session_id):
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if not user or not user.is_active:
            raise ValueError('Invalid user')
        from app.services.live import runtime
        state = runtime.get(session_id)
        if state:
            state.lock.acquire()
        try:
            session = session_for(db, user, session_id)
            publish(db, session)
        finally:
            if state:
                state.lock.release()


@router.websocket('/live/sessions/{session_id}/ws')
async def socket(ws: WebSocket, session_id: UUID):
    if ws.headers.get('origin') not in get_settings().cors_origin_list:
        await ws.close(code=1008)
        return
    await ws.accept()
    subscriber = None
    receiver = None
    async def read_text():
        message = await ws.receive()
        if message['type'] == 'websocket.disconnect':
            raise WebSocketDisconnect(message.get('code', 1000))
        text = message.get('text')
        if not isinstance(text, str) or len(text) > 1024:
            raise ValueError('Unexpected client message')
        return text
    try:
        raw = await asyncio.wait_for(read_text(), 5)
        if len(raw) > 128:
            raise ValueError('Oversized credential')
        user_id = consume(raw, session_id)
        subscriber = manager.connect(session_id, get_settings().live_ws_subscriber_cap)
        await run_in_threadpool(refresh, user_id, session_id)
        last_pong = time.monotonic()

        async def receive():
            nonlocal last_pong
            while True:
                if await read_text() != 'pong':
                    raise ValueError('Unexpected client message')
                last_pong = time.monotonic()
                await asyncio.sleep(.1)

        receiver = asyncio.create_task(receive())
        heartbeat = time.monotonic()
        while True:
            if receiver.done():
                receiver.result()
            for event in manager.take(subscriber):
                await asyncio.wait_for(ws.send_text(event.model_dump_json()), 2)
                if event.event in ('session.stopped', 'session.failed'):
                    await ws.close(code=1000)
                    return
            if time.monotonic()-heartbeat >= 5:
                if time.monotonic()-last_pong > 15:
                    raise TimeoutError()
                await asyncio.wait_for(ws.send_text('{"version":1,"event":"heartbeat"}'), 2)
                await run_in_threadpool(refresh, user_id, session_id)
                heartbeat = time.monotonic()
            await asyncio.sleep(.05)
    except (ValueError, HTTPException, TimeoutError):
        await ws.close(code=1008)
    except WebSocketDisconnect:
        pass
    finally:
        if receiver:
            receiver.cancel()
            await asyncio.gather(receiver, return_exceptions=True)
        if subscriber:
            manager.disconnect(session_id, subscriber)
