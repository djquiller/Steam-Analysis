"""数值与时间的输出格式（docs/api.md "通用约定"）。"""

from datetime import date, datetime
from decimal import Decimal

# 好评率按游戏统计时，评论数少于这个值不展示（docs/schema.md "全局口径"）
MIN_REVIEWS_FOR_RATE = 10


def iso(dt: datetime | None) -> str | None:
    """库里的 DATETIME 一律是不带时区的 UTC，输出 ISO 8601 并加 Z。"""
    if dt is None:
        return None
    if isinstance(dt, str):  # SQLite 测试库可能直接返回字符串
        dt = datetime.fromisoformat(dt)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_date(d: date | None) -> str | None:
    if d is None:
        return None
    if isinstance(d, str):
        d = date.fromisoformat(d[:10])
    return d.isoformat()


def money(v: Decimal | float | int | None) -> float | None:
    return None if v is None else round(float(v), 2)


def ratio(num: Decimal | float | int | None, den: Decimal | float | int | None) -> float | None:
    """比率保留 4 位；分母为 0 或缺失时返回 None。"""
    if num is None or not den:
        return None
    return round(float(num) / float(den), 4)


def game_rate(positive: int, review_cnt: int) -> float | None:
    """单款游戏的好评率：评论数 < 10 时返回 None。"""
    if review_cnt is None or review_cnt < MIN_REVIEWS_FOR_RATE:
        return None
    return ratio(positive, review_cnt)


def to_int(v) -> int | None:
    return None if v is None else int(v)
