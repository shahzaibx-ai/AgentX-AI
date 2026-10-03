"""Reject oversized request bodies before they are read into memory.

Photos make chat requests large, and FastAPI parses the whole JSON body before
any route check runs, so the size is enforced here while the body streams in.
"""

from starlette.types import ASGIApp, Message, Receive, Scope, Send

TOO_LARGE = b'{"detail":"Request is too large. Send fewer or smaller photos."}'


class BodySizeLimit:
    def __init__(self, app: ASGIApp, max_bytes: int, paths: tuple[str, ...]) -> None:
        self.app = app
        self.max_bytes = max_bytes
        self.paths = paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith(self.paths):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        length = headers.get(b"content-length")
        if length is not None and length.isdigit() and int(length) > self.max_bytes:
            await self._reject(send)
            return

        received = 0
        responded = False  # the app has started its own response
        rejected = False  # we answered 413; ignore whatever the app sends after

        async def limited_receive() -> Message:
            nonlocal received, rejected
            if rejected:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes and not responded:
                    rejected = True
                    await self._reject(send)
                    # Stop the app from reading further; it sees a client disconnect.
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message: Message) -> None:
            nonlocal responded
            if rejected:
                return
            if message["type"] == "http.response.start":
                responded = True
            await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except Exception:
            if not rejected:
                raise

    @staticmethod
    async def _reject(send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(TOO_LARGE)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": TOO_LARGE})
