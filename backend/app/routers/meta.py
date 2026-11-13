from fastapi import APIRouter, Depends
from sqlalchemy import Connection

from ..db import get_conn
from ..errors import ok
from ..schemas.common import Envelope
from ..schemas.models import Kpi, MetaFilters, MetaUpdatedAt
from ..services import meta as svc

router = APIRouter()


@router.get("/meta/filters", tags=["meta"], response_model=Envelope[MetaFilters], summary="筛选项")
def meta_filters(conn: Connection = Depends(get_conn)):
    """年份范围、类型列表（按游戏数降序）、价格区间。全局筛选参数 genre 的合法取值就是这里的 genres[].genre。"""
    return ok(svc.filters(conn))


@router.get("/meta/updated-at", tags=["meta"], response_model=Envelope[MetaUpdatedAt], summary="数据更新时间")
def meta_updated_at(conn: Connection = Depends(get_conn)):
    return ok(svc.updated_at(conn))


@router.get("/overview/kpi", tags=["overview"], response_model=Envelope[Kpi | dict], summary="KPI 概览")
def overview_kpi(conn: Connection = Depends(get_conn)):
    """游戏总数 / 评论总数 / 估算玩家总量 / 实时在线峰值。表里还没有数据时 data 为 {}。"""
    return ok(svc.kpi(conn))
