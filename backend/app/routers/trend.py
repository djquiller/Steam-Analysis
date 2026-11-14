from fastapi import APIRouter, Depends
from sqlalchemy import Connection

from ..db import get_conn
from ..errors import ok
from ..schemas.common import Envelope
from ..schemas.models import GenreHeatItem, PriceRatingBox, YearlyItem
from ..services import trend as svc
from ..services.filters import Filters, get_filters

router = APIRouter(prefix="/trend", tags=["trend"])


@router.get("/yearly", response_model=Envelope[list[YearlyItem]], summary="历年发行量与均价（可筛选）")
def trend_yearly(f: Filters = Depends(get_filters), conn: Connection = Depends(get_conn)):
    return ok(svc.yearly(conn, f))


@router.get("/genres", response_model=Envelope[list[GenreHeatItem]], summary="类型热度（可筛选：年份、价格区间）")
def trend_genres(f: Filters = Depends(get_filters), conn: Connection = Depends(get_conn)):
    """不响应 genre：树图始终展示全部类型，选中的类型由前端高亮。"""
    return ok(svc.genres(conn, f))


@router.get("/price-rating", response_model=Envelope[list[PriceRatingBox]], summary="价格区间 × 好评率箱线（可筛选）")
def trend_price_rating(f: Filters = Depends(get_filters), conn: Connection = Depends(get_conn)):
    """五数由 1% 分箱推算，单位 %，值为分箱下界；只统计评论数 ≥ 10 的游戏。"""
    return ok(svc.price_rating(conn, f))
