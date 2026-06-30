import json
import logging
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.datastructures import Headers

logger = logging.getLogger(__name__)

class PayloadTooLargeError(Exception):
    pass


class ContentSizeLimitMiddleware:
    """
    ASGI middleware that rejects request payloads larger than the configured max_content_size.
    Performs early rejection via Content-Length header, and dynamically handles streaming/chunked requests.
    """
    def __init__(self, app: ASGIApp, max_content_size: int):
        self.app = app
        self.max_content_size = max_content_size

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        content_length_str = headers.get("content-length")
        
        # 1. Early rejection based on Content-Length header
        if content_length_str:
            try:
                content_length = int(content_length_str)
                if content_length > self.max_content_size:
                    logger.warning(
                        f"Rejecting request early: Content-Length {content_length} "
                        f"exceeds limit {self.max_content_size}"
                    )
                    await self._send_error_response(send, scope["path"])
                    return
            except ValueError:
                pass

        # 2. Wrapping receive channel to protect against chunked/streaming size bypasses
        total_size = 0
        
        async def custom_receive() -> dict:
            nonlocal total_size
            message = await receive()
            if message["type"] == "http.request":
                body_length = len(message.get("body", b""))
                total_size += body_length
                if total_size > self.max_content_size:
                    logger.warning(
                        f"Rejecting request dynamically: cumulative size {total_size} "
                        f"exceeds limit {self.max_content_size}"
                    )
                    raise PayloadTooLargeError()
            return message

        try:
            await self.app(scope, custom_receive, send)
        except PayloadTooLargeError:
            await self._send_error_response(send, scope["path"])

    async def _send_error_response(self, send: Send, path: str) -> None:
        # Construct RFC 7807 payload
        response_body = {
            "type": "https://talkfiesta.com/errors/payload-too-large",
            "title": "Request Entity Too Large",
            "status": 413,
            "detail": f"Request payload exceeds the maximum limit of {self.max_content_size / (1024 * 1024):.1f} MB.",
            "instance": path,
        }
        body_bytes = json.dumps(response_body).encode("utf-8")
        
        await send({
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body_bytes)).encode("ascii"))
            ]
        })
        await send({
            "type": "http.response.body",
            "body": body_bytes,
            "more_body": False
        })


class SecurityHeadersMiddleware:
    """
    ASGI middleware that injects recommended OWASP security headers into all HTTP responses.
    """
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                
                # Standard security headers to inject
                security_headers = [
                    (b"x-frame-options", b"DENY"),
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-xss-protection", b"1; mode=block"),
                    (b"strict-transport-security", b"max-age=63072000; includeSubDomains; preload"),
                    (b"referrer-policy", b"strict-origin-when-cross-origin"),
                    (b"content-security-policy", b"default-src 'self'; frame-ancestors 'none'; form-action 'self'; object-src 'none';"),
                ]
                
                # Check for duplicates to prevent double-header errors
                existing_keys = {h[0].lower() for h in headers}
                for key, val in security_headers:
                    if key not in existing_keys:
                        headers.append((key, val))
                        
                message["headers"] = headers

            await send(message)

        await self.app(scope, receive, send_with_headers)
