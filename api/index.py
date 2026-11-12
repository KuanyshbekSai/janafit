import sys
import os

# Add root directory to sys.path so modules like web, services, config can be imported
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

try:
    from web.server import app
except Exception as e:
    import traceback
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse

    app = FastAPI(title="Vercel Error Fallback")
    err_tb = traceback.format_exc()
    print(err_tb)
    if os.getenv("DEBUG", "0").strip() != "1":
        err_tb = "Сервис временно недоступен. Подробности — в логах Vercel."

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
