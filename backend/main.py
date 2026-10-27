from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="AI Engineering Tracker",
    version="0.1.0"
)

@app.get("/api")
def home():
    return {
        "message": "AI Engineering Tracker API is running"
    }

@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


from auth import router as auth_router
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

app.include_router(auth_router)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # FastAPI's default validation errors echo input, including invalid passwords.
    errors = [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})


from tracker import router as tracker_router
app.include_router(tracker_router)
from github_imports import router as github_router
app.include_router(github_router)
from file_imports import router as file_router
app.include_router(file_router)
FRONTEND = Path(__file__).resolve().parent.parent / "frontend" / "dist"
app.mount("/assets", StaticFiles(directory=FRONTEND / "assets", check_dir=False), name="assets")


@app.get("/", include_in_schema=False)
def website():
    if not (FRONTEND / "index.html").is_file():
        return JSONResponse(status_code=503, content={"detail": "Frontend build missing. Run npm ci and npm run build in frontend, then restart the server."})
    return FileResponse(FRONTEND / "index.html")


@app.middleware("http")
async def response_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Cache-Control"] = "no-store"
    if request.url.path == "/":
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' https://challenges.cloudflare.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; "
            "connect-src 'self' https://challenges.cloudflare.com; frame-src https://challenges.cloudflare.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
    return response
