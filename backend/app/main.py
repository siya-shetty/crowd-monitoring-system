import logging
from contextlib import asynccontextmanager
from starlette.concurrency import run_in_threadpool
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.services.health import health_payload
configure_logging(); settings = get_settings(); logger = logging.getLogger(__name__)
@asynccontextmanager
async def lifespan(app):
    from app.db.session import SessionLocal
    from app.services.live import reconcile
    def recover():
        with SessionLocal() as database:
            reconcile(database)
    await run_in_threadpool(recover)
    yield
    await run_in_threadpool(recover)

app = FastAPI(title="Crowd Monitoring API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
@app.exception_handler(RequestValidationError)
async def invalid_request(_: Request, exc: RequestValidationError) -> JSONResponse:
    # Do not echo raw inputs: nonfinite JSON values cannot be serialized safely,
    # and authentication/configuration inputs may contain private information.
    return JSONResponse(status_code=422, content={"detail": [
        {"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
        for error in exc.errors()]})
@app.exception_handler(Exception)
async def unhandled_error(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled request error", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail":"Internal server error"})
@app.get("/health", tags=["system"])
def health() -> dict[str, str]: return health_payload()
app.include_router(api_router)
