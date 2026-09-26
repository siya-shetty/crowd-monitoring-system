# Live WebSocket transport

See [the permanent transport documentation](../../../docs/realtime-websockets.md).
`routes.py` handles tickets and socket lifecycle, `events.py` defines aggregate
contracts, and `manager.py` owns bounded thread-safe latest-state mailboxes.
