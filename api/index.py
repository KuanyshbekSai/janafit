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
                headers = dict(scope.get("headers", []))
                x_matched = headers.get(b"x-matched-path", b"").decode("utf-8")
                path = scope.get("path", "")

                if x_matched and x_matched != "/api/index.py":
                    scope["path"] = x_matched
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
