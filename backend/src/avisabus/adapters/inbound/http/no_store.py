"""`Cache-Control: no-store` on every response under a path (alert_create AC-14).

A middleware, not the route handlers, so the answers built by the exception handlers (`400` of
the device header, validation `422`) carry it too.
"""

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from avisabus.adapters.inbound.http.errors import NO_STORE


class NoStoreMiddleware:
    def __init__(self, app: ASGIApp, path: str) -> None:
        self.app = app
        self.path = path

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "") if scope["type"] == "http" else None
        if path is None or not (path == self.path or path.startswith(self.path + "/")):
            await self.app(scope, receive, send)
            return

        async def send_no_store(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)["Cache-Control"] = NO_STORE
            await send(message)

        await self.app(scope, receive, send_no_store)
