from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Connection

from ..db import get_conn
from ..errors import ok
from ..schemas.common import Envelope
from ..schemas.models import OnlineLive, TopSellerItem
from ..services import rank as svc
from ..services.filters import Filters, get_filters

router = APIRouter(prefix="/rank", tags=["rank"])


@router.get("/top-sellers", response_model=Envelope[list[TopSellerItem]], summary="热销 Top N（可筛选）")
def rank_top_sellers(
    metric: Literal["owners", "ccu"] = Query("owners", description="owners：按拥有者；ccu：按最新在线人数"),
    limit: int = Query(10, ge=1, le=50),
    f: Filters = Depends(get_filters),
    conn: Connection = Depends(get_conn),
):
    return ok(svc.top_sellers(conn, f, metric, limit))


@router.get("/online-live", response_model=Envelope[OnlineLive], summary="实时在线榜")
def rank_online_live(limit: int = Query(20, ge=1, le=100), conn: Connection = Depends(get_conn)):
    """前端 60 秒轮询；表为空时返回 {snapshot_at: null, items: []}。"""
    return ok(svc.online_live(conn, limit))
