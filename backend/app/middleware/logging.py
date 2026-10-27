"""Access logging with timing, and log records tagged with the request ID.

Logs method, path, status and duration only: never headers, query strings or bodies, which can
carry tokens or personal data.
"""
import logging
import time

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .request_id import request_id_var

log = logging.getLogger("ledgerly.access")

LOG_FORMAT = "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"


class RequestIdLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format=LOG_FORMAT)
    for handler in logging.getLogger().handlers:
        if not any(isinstance(f, RequestIdLogFilter) for f in handler.filters):
            handler.addFilter(RequestIdLogFilter())


class AccessLogMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started = time.perf_counter()
        status = 500  # if the app raises before responding

        async def send_and_capture(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_and_capture)
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000
            log.info("%s %s %s %.1fms", scope["method"], scope["path"], status, elapsed_ms)
