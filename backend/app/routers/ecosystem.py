from fastapi import APIRouter, Depends, Query
from sqlalchemy import Connection

from ..db import get_conn
from ..errors import bad_param, ok
from ..schemas.common import Envelope
from ..schemas.models import ActivityHeatmap, PlaytimeDist, RatingDist, ReviewLanguages
from ..services import ecosystem as svc
from ..services.filters import Filters, get_filters

router = APIRouter(prefix="/ecosystem", tags=["ecosystem"])


@router.get("/rating-dist", response_model=Envelope[RatingDist], summary="好评率分布（可筛选）")
def ecosystem_rating_dist(
    bin_width: int = Query(5, description="分箱宽度（%）：1 / 5 / 10"),
    f: Filters = Depends(get_filters),
    conn: Connection = Depends(get_conn),
):
    if bin_width not in svc.RATING_BIN_WIDTHS:
        raise bad_param("bin_width 只能取 1、5、10")
    return ok(svc.rating_dist(conn, f, bin_width))


@router.get("/review-languages", response_model=Envelope[ReviewLanguages], summary="评论语言分布（可筛选）")
def ecosystem_review_languages(
    limit: int = Query(10, ge=1, le=30, description="单独列出的语言数，其余合并为 other"),
    f: Filters = Depends(get_filters),
    conn: Connection = Depends(get_conn),
):
    return ok(svc.review_languages(conn, f, limit))


@router.get("/playtime-dist", response_model=Envelope[PlaytimeDist], summary="游玩时长分布（可筛选）")
def ecosystem_playtime_dist(f: Filters = Depends(get_filters), conn: Connection = Depends(get_conn)):
    """写评论时的累计游玩时长，11 个近似对数的固定分箱。"""
    return ok(svc.playtime_dist(conn, f))


@router.get("/activity-heatmap", response_model=Envelope[ActivityHeatmap], summary="星期 × 小时评论活跃度（可筛选）")
def ecosystem_activity_heatmap(f: Filters = Depends(get_filters), conn: Connection = Depends(get_conn)):
    """时间一律 UTC；cells 固定 168 项。"""
    return ok(svc.activity_heatmap(conn, f))
