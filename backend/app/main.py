"""FastAPI 入口：挂路由、CORS、全局异常处理。

启动（在 backend/ 目录下）：python -m uvicorn app.main:app --port 8000
接口文档：http://127.0.0.1:8000/docs
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_settings
from .errors import install_handlers
from .routers import cluster, ecosystem, games, meta, rank, trend

API_PREFIX = "/api/v1"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Steam 玩家生态与热销趋势 API",
        version="0.3.0",
        description="大屏数据接口。返回格式统一为 {code, msg, data}，契约见 docs/api.md。",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origin_list,
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    install_handlers(app)
    for r in (meta, trend, rank, cluster, ecosystem, games):
        app.include_router(r.router, prefix=API_PREFIX)

    @app.get("/health", tags=["meta"], summary="存活检查（不查库）")
    def health():
        return {"code": 0, "msg": "ok", "data": {"status": "up"}}

    return app


app = create_app()
