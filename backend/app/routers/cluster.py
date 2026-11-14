from fastapi import APIRouter, Depends, Query
from sqlalchemy import Connection

from ..db import get_conn
from ..errors import ok
from ..schemas.common import Envelope
from ..schemas.models import ClusterGames
from ..services import cluster as svc
from ..services.filters import Filters, get_filters

router = APIRouter(prefix="/cluster", tags=["cluster"])


@router.get("/games", response_model=Envelope[ClusterGames], summary="聚类散点（可筛选）")
def cluster_games(
    limit: int = Query(3000, ge=100, le=10000, description="返回的散点上限"),
    f: Filters = Depends(get_filters),
    conn: Connection = Depends(get_conn),
):
    """total 与 clusters 按全部符合筛选的游戏统计；points 是按 sample_key 取的固定子集。"""
    return ok(svc.games(conn, f, limit))
