"""WebSocket streaming controller for realtime events.

Provides WebSocket endpoints for subscribing to realtime event streams.
WebSocket connections use SESSION scope in Dishka, so auth is excluded
and handled separately if needed.
"""
from litestar import Controller, WebSocket, websocket

from sqlstack.lib.realtime import RealtimeChannels
from sqlstack.lib.websockets import stream_pubsub


class RealtimeStreamController(Controller):
    """WebSocket streaming controller for global realtime events.

    This provides a simple WebSocket endpoint that streams events
    from the global channel. Useful for dashboards and monitoring.
    """

    path = "/api/realtime"
    tags = ["Realtime"]

    @websocket(
        path="/global/stream",
        name="realtime:global-stream",
        summary="Stream Global Events",
        opt={"exclude_from_csrf": True, "exclude_from_auth": True},
    )
    async def stream_global_events(self, socket: WebSocket) -> None:
        """Stream global/system events via WebSocket.

        Connect to this endpoint to receive realtime events published
        to the global channel by background jobs and services.

        Example:
            ws://host/api/realtime/global/stream
        """
        await socket.accept()
        await stream_pubsub(socket, [RealtimeChannels.global_channel()], history=10)
