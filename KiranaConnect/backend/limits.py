"""Bound request bodies before multipart spooling, including chunked uploads."""

from starlette.responses import JSONResponse


class RequestLimits:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in ("POST", "PUT", "DELETE"):
            return await self.app(scope, receive, send)
        limit = (
            5 * 1024 * 1024 + 65536
            if scope["path"] in ("/api/uploads", "/api/customer/image")
            or (
                scope["path"].startswith("/api/inbox/")
                and scope["path"].endswith("/image")
            )
            else 512 * 1024
        )
        headers = dict(scope["headers"])
        if headers.get(b"sec-fetch-site") == b"cross-site" and scope["path"].startswith(
            "/api/"
        ):
            return await JSONResponse({"detail": "Cross-site write blocked"}, 403)(
                scope, receive, send
            )
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > limit:
                return await JSONResponse({"detail": "Request too large"}, 413)(
                    scope, receive, send
                )
            if not message.get("more_body"):
                break
        delivered = False

        async def replay():
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, replay, send)
