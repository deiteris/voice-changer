import asyncio
import logging
import os
import secrets

from starlette.requests import Request
from starlette.responses import Response


logger = logging.getLogger(__name__)
STARTUP_TIMEOUT_SECONDS = 120
RECONNECT_SECONDS = 5


class DesktopSession:
    """Keep the Windows desktop server alive while a launcher tab is connected."""

    def __init__(self):
        self.token = secrets.token_urlsafe()
        self.connections = 0
        self.exit_at: float | None = None
        self.closing = False

    async def watch(self, server, url: str):
        loop = asyncio.get_running_loop()
        self.exit_at = loop.time() + STARTUP_TIMEOUT_SECONDS
        try:
            try:
                os.startfile(f"{url}#desktop={self.token}")
            except OSError:
                logger.exception("Could not open the Voice Changer browser tab. Shutting down.")
                server.should_exit = True
                return

            while not server.should_exit:
                if self.closing:
                    server.should_exit = True
                    break
                if self.exit_at is not None and loop.time() >= self.exit_at:
                    logger.info("Voice Changer browser session ended. Shutting down.")
                    server.should_exit = True
                    break
                await asyncio.sleep(0.25)
        finally:
            self.closing = True

    async def __call__(self, scope, receive, send):
        request = Request(scope)
        if request.method == "POST":
            token = request.headers.get("x-voice-changer-session", "").encode()
            if not secrets.compare_digest(token, self.token.encode()):
                await Response(status_code=403)(scope, receive, send)
                return
            self.closing = True
            await Response(status_code=204)(scope, receive, send)
            return

        token = request.query_params.get("token", "").encode()
        if self.closing or not secrets.compare_digest(token, self.token.encode()):
            await Response(status_code=204)(scope, receive, send)
            return

        self.connections += 1
        self.exit_at = None
        try:
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/event-stream"), (b"cache-control", b"no-store")],
            })
            await send({"type": "http.response.body", "body": b"retry: 1000\n: connected\n\n", "more_body": True})
            while not self.closing:
                try:
                    message = await asyncio.wait_for(receive(), timeout=1)
                except TimeoutError:
                    continue
                if message["type"] == "http.disconnect":
                    return
            await send({"type": "http.response.body", "body": b"event: quit\ndata: closed\n\n"})
        except OSError:
            # The browser can disconnect between receiving a request and sending a response.
            pass
        finally:
            self.connections -= 1
            if not self.connections:
                self.exit_at = asyncio.get_running_loop().time() + RECONNECT_SECONDS
