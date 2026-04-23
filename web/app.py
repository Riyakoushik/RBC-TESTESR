"""
RBC-TESTER Web Dashboard
FastAPI application for monitoring and managing the document conversion pipeline.
"""

import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Ensure project root is on path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from web.api import router as api_router

# Path to the React build output
DIST_DIR = Path(__file__).parent / "static" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    yield


app = FastAPI(
    title="RBC-TESTER Dashboard",
    description="Web dashboard for the RBC-TESTER document conversion pipeline",
    version="1.0.0",
    lifespan=lifespan,
)

# Include API routes first (before catch-all static mount)
app.include_router(api_router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok"}


# Mount React build assets
if DIST_DIR.exists():
    assets_dir = DIST_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve the React SPA — all non-API routes return index.html."""
        file_path = DIST_DIR / full_path
        if full_path and file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(DIST_DIR / "index.html"))
else:
    # Fallback: serve old static files if React build not present
    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/")
    async def fallback_root():
        return {"error": "Frontend not built. Run 'npm run build' in frontend/ directory."}


def main():
    """Run the web dashboard server."""
    import uvicorn
    uvicorn.run(
        "web.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
