from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.api.routes.chunks import router as chunks_router
from app.api.routes.build_tasks import router as build_tasks_router
from app.api.routes.chat import router as chat_router
from app.api.routes.health import router as health_router
from app.api.routes.knowledge_bases import router as knowledge_bases_router
from app.api.routes.sessions import router as sessions_router
from app.core.config import get_settings
from app.db import init_mysql
from app.schemas.common import ApiResponse

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_mysql()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    # Keep response shape stable for frontend integration.
    return JSONResponse(
        status_code=500,
        content=ApiResponse(code=5000, message=f"internal error: {exc}", data={}).model_dump(),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and {"code", "message", "data"} <= set(exc.detail.keys()):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=ApiResponse(code=exc.status_code, message=str(exc.detail), data={}).model_dump(),
    )


@app.exception_handler(KeyError)
async def key_error_handler(_: Request, exc: KeyError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=ApiResponse(code=1002, message=str(exc), data={}).model_dump(),
    )


@app.get("/", response_model=ApiResponse[dict[str, str]])
def root() -> ApiResponse[dict[str, str]]:
    return ApiResponse(data={"service": settings.app_name, "status": "running"})


app.include_router(health_router, prefix=settings.api_prefix)
app.include_router(sessions_router, prefix=settings.api_prefix)
app.include_router(knowledge_bases_router, prefix=settings.api_prefix)
app.include_router(build_tasks_router, prefix=settings.api_prefix)
app.include_router(chunks_router, prefix=settings.api_prefix)
app.include_router(chat_router, prefix=settings.api_prefix)
