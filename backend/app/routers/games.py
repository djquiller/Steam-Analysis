from fastapi import APIRouter, Depends, Path
from sqlalchemy import Connection

from ..db import get_conn
from ..errors import ok
from ..schemas.common import Envelope
from ..schemas.models import GameDetail, PricePoint, ReviewTrendItem
from ..services import games as svc

router = APIRouter(prefix="/games", tags=["games"])

AppId = Path(..., ge=1, le=4294967295, description="Steam appid")


@router.get("/{appid}", response_model=Envelope[GameDetail], summary="单款游戏详情")
def game_detail(appid: int = AppId, conn: Connection = Depends(get_conn)):
    """appid 不存在返回 40401。cluster / hot_pred / sentiment / peers 在模型结果表里没有这款游戏时为 null。"""
    return ok(svc.detail(conn, appid))


@router.get("/{appid}/reviews-trend", response_model=Envelope[list[ReviewTrendItem]], summary="评论量与好评率月度走势")
def game_reviews_trend(appid: int = AppId, conn: Connection = Depends(get_conn)):
    return ok(svc.reviews_trend(conn, appid))


@router.get("/{appid}/price-history", response_model=Envelope[list[PricePoint]], summary="价格历史")
def game_price_history(appid: int = AppId, conn: Connection = Depends(get_conn)):
    return ok(svc.price_history(conn, appid))
