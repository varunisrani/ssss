import os
import sys
import io
from datetime import datetime
# Ensure stdout and stderr use utf-8 encoding to prevent emoji logs from crashing python server
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()
from routers.websocket_router import *  # DO NOT DELETE THIS LINE, OTHERWISE, WEBSOCKET WILL NOT WORK
from routers import config_router, image_router, root_router, workspace, canvas, ssl_test, chat_router, settings, svg_router, image_to_svg_router
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import argparse 
from contextlib import asynccontextmanager
from starlette.types import Scope
from starlette.responses import Response
import socketio # type: ignore
from services.websocket_state import sio
from services.websocket_service import broadcast_init_done
from services.config_service import config_service  
from services.tool_service import tool_service

async def initialize():
    await config_service.initialize()
    await broadcast_init_done()

root_dir = os.path.dirname(__file__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # onstartup
    # TODO: Check if there will be racing conditions when user send chat request but tools and models are not initialized yet.
    await initialize()
    await tool_service.initialize()
    yield
    # onshutdown

app = FastAPI(lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Include routers
app.include_router(config_router.router)
app.include_router(settings.router)
app.include_router(root_router.router)
app.include_router(canvas.router)
app.include_router(workspace.router)
app.include_router(image_router.router)
app.include_router(ssl_test.router)
app.include_router(chat_router.router)
app.include_router(svg_router.router)
app.include_router(image_to_svg_router.router)

# Add health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "Jaaz AI Design Agent Backend",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }

# Mount the React build directory
react_build_dir = os.environ.get('UI_DIST_DIR', os.path.join(
    os.path.dirname(root_dir), "react", "dist"))


# 无缓存静态文件类
class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


static_site = os.path.join(react_build_dir, "assets")
if os.path.exists(static_site):
    app.mount("/assets", NoCacheStaticFiles(directory=static_site), name="assets")


@app.get("/")
async def serve_react_app():
    index_path = os.path.join(react_build_dir, "index.html")
    
    # Check if frontend files exist, otherwise return API status
    if os.path.exists(index_path):
        response = FileResponse(index_path)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    else:
        # Fallback: Return API status when frontend is not available
        return {
            "message": "Jaaz AI Design Agent Backend API",
            "status": "running",
            "version": "1.0.0",
            "frontend": "not_available",
            "api_docs": "/docs",
            "health": "/health"
        }


socket_app = socketio.ASGIApp(sio, other_asgi_app=app, socketio_path='/socket.io')

if __name__ == "__main__":
    # bypass localhost request for proxy, fix ollama proxy issue
    _bypass = {"127.0.0.1", "localhost", "::1"}
    current = set(os.environ.get("no_proxy", "").split(",")) | set(
        os.environ.get("NO_PROXY", "").split(","))
    os.environ["no_proxy"] = os.environ["NO_PROXY"] = ",".join(
        sorted(_bypass | current - {""}))

    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=57988,
                        help='Port to run the server on')
    args = parser.parse_args()
    import uvicorn
    print("🌟Starting server, UI_DIST_DIR:", os.environ.get('UI_DIST_DIR'))

    uvicorn.run(socket_app, host="127.0.0.1", port=args.port)
