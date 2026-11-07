import sys
import os

# Add root directory to sys.path so modules like web, services, config can be imported
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

try:
    from web.server import app as fastapi_app

    class VercelPathMiddleware:
        def __init__(self, inner_app):
            self.inner_app = inner_app

        async def __call__(self, scope, receive, send):
            if scope["type"] == "http":
                raw_headers = dict(scope.get("headers", []))
                headers_str = {k.decode("latin1"): v.decode("latin1") for k, v in raw_headers.items()}
                
                # Check for debug endpoint
                path = scope.get("path", "")
                if "/debug" in path or "/debug" in headers_str.get("x-matched-path", "") or "/debug" in headers_str.get("x-forwarded-uri", ""):
                    response_body = str({
                        "scope_path": scope.get("path"),
                        "headers": headers_str
                    }).encode("utf-8")
                    await send({
                        "type": "http.response.start",
                        "status": 200,
                        "headers": [
                            [b"content-type", b"application/json"],
                            [b"content-length", str(len(response_body)).encode("utf-8")]
                        ]
                    })
                    await send({
                        "type": "http.response.body",
                        "body": response_body
                    })
                    return

                # Normal resolution: check headers that actually contain the requested route
                real_path = (
                    headers_str.get("x-invoke-path") or
                    headers_str.get("x-forwarded-uri") or
                    headers_str.get("x-original-url") or
                    headers_str.get("x-rewrite-url")
                )
                if real_path and real_path.startswith("/"):
                    scope["path"] = real_path.split("?")[0]
                elif path.startswith("/api/index.py"):
                    trimmed = path[len("/api/index.py"):]
                    scope["path"] = trimmed if trimmed else "/"

            await self.inner_app(scope, receive, send)

    app = VercelPathMiddleware(fastapi_app)
except Exception as e:
    import traceback
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse

    app = FastAPI(title="Vercel Error Fallback")
    err_tb = traceback.format_exc()

    @app.api_route("/", methods=["GET", "POST", "HEAD", "OPTIONS"])
    @app.api_route("/{full_path:path}", methods=["GET", "POST", "HEAD", "OPTIONS"])
    async def catch_all(full_path: str = ""):
        return HTMLResponse(
            f"<html><body style='font-family:sans-serif;padding:20px;background:#1e1e2e;color:#f38ba8;'>"
            f"<h2>Vercel Python Lambda Error:</h2>"
            f"<pre style='background:#11111b;padding:15px;border-radius:8px;color:#cdd6f4;overflow:auto;'>{err_tb}</pre>"
            f"</body></html>",
            status_code=500
        )
