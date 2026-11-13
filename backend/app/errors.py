"""统一返回信封与错误码（docs/api.md "返回信封"）。

所有响应都是 {code, msg, data}。出错时 HTTP 状态码也随之设置（400 / 404 / 500），
前端 axios 拦截器统一读 body 里的 code 和 msg。
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("backend")

OK = 0
BAD_PARAM = 40001
NOT_FOUND = 40401
DB_ERROR = 50001

_HTTP_STATUS = {BAD_PARAM: 400, NOT_FOUND: 404, DB_ERROR: 500}


def ok(data):
    return {"code": OK, "msg": "ok", "data": data}


class ApiError(Exception):
    """业务错误：在 service 里抛出，由全局处理器转成信封。"""

    def __init__(self, code: int, msg: str):
        super().__init__(msg)
        self.code = code
        self.msg = msg


def bad_param(msg: str) -> ApiError:
    return ApiError(BAD_PARAM, msg)


def not_found(msg: str) -> ApiError:
    return ApiError(NOT_FOUND, msg)


def _envelope(code: int, msg: str) -> JSONResponse:
    return JSONResponse(status_code=_HTTP_STATUS.get(code, 500), content={"code": code, "msg": msg, "data": None})


def _describe_validation(exc: RequestValidationError) -> str:
    """把 FastAPI 的校验错误压成一句话，例如 "limit: 应 ≤ 50"。"""
    parts = []
    for err in exc.errors():
        loc = [str(x) for x in err.get("loc", ()) if x not in ("query", "path", "body")]
        name = ".".join(loc) or "参数"
        ctx = err.get("ctx") or {}
        if "le" in ctx:
            reason = f"应 ≤ {ctx['le']}"
        elif "ge" in ctx:
            reason = f"应 ≥ {ctx['ge']}"
        elif err.get("type", "").startswith("int"):
            reason = "应为整数"
        else:
            reason = err.get("msg", "取值非法")
        parts.append(f"{name}: {reason}")
    return "参数错误：" + "；".join(parts)


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError):
        return _envelope(exc.code, exc.msg)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        return _envelope(BAD_PARAM, _describe_validation(exc))

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        if exc.status_code == 404:
            return _envelope(NOT_FOUND, "接口不存在")
        if exc.status_code == 405:
            return JSONResponse(status_code=405, content={"code": BAD_PARAM, "msg": "不支持的请求方法", "data": None})
        return JSONResponse(status_code=exc.status_code, content={"code": exc.status_code, "msg": str(exc.detail), "data": None})

    @app.exception_handler(SQLAlchemyError)
    async def _db(request: Request, exc: SQLAlchemyError):
        # 日志里只记异常类型和请求路径；SQLAlchemy 的异常文本可能带连接串主机名，但不含密码
        log.exception("数据库异常：%s %s", request.method, request.url.path)
        return _envelope(DB_ERROR, "数据库异常，请稍后重试")

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception):
        log.exception("未处理的异常：%s %s", request.method, request.url.path)
        return _envelope(DB_ERROR, "服务内部错误，请稍后重试")
