from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.utils.log_utils import log_error

app = FastAPI()

app.include_router(router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    log_error(f"Unhandled exception on {request.method} {request.url.path}", exc)
    return JSONResponse(status_code=500, content={"detail": str(exc)})
