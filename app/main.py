from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.core.auth.api.v1.routes_auth import router as auth_router
from app.core.auth.api.v1.routes_me import router as me_router
from app.core.areas.api.v1.routes_areas import router as areas_router
from app.response import StandardResponse, make_error_response
from app.response.response import APIError


app = FastAPI()


@app.exception_handler(APIError)
async def api_error_handler(
    request: Request,
    exc: APIError,
) -> JSONResponse:
    response: StandardResponse = make_error_response(
        code=exc.code,
        http_code=exc.http_code,
        message=exc.message,
        details=exc.details,
        fields=exc.fields,
    )
    return JSONResponse(
        status_code=exc.http_code,
        content=jsonable_encoder(response),
    )


app.include_router(auth_router, prefix="/api/v1")
app.include_router(me_router, prefix="/api/v1")
app.include_router(areas_router, prefix="/api/v1")


__all__ = ["app"]
