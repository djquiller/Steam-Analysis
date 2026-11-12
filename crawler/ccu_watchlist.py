"""生成在线人数的采集名单，写入 steam.dwd_ccu_watchlist。

名单 = dwd_game 里 peak_ccu 最高的 500 款 ∪ owners_mid 最高的 500 款（见 crawler/CLAUDE.md）。

为什么要规定次级排序：owners_mid 是 SteamSpy 的区间中值，只有十几个档位，并列极多
（第 500 名落在 350 万这一档，这一档有 405 款）。不规定并列时的次序，每次取到的 500 款
就可能不同，名单会来回抖动，快照序列也就断断续续。所以两个榜都用完全确定的排序键：

    peak_ccu 榜：  peak_ccu 降序 → appid 升序
    owners 榜：    owners_mid 降序 → peak_ccu 降序 → appid 升序

owners 档内按 peak_ccu 排，是因为同一档里历史峰值高的更可能现在还有人在线；
最后用 appid 兜底，它是主键，所以次序唯一。

名单保存在表里而不是文件里：采集进程和手动运行读到的是同一份，后端以后也能查
"哪些游戏有在线人数序列"。刷新是在一个事务里整表替换，读的一方不会看到半份名单。

手动刷新：python -m crawler.ccu_watchlist
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, NamedTuple

from .common import settings
from .common.db import connect_etl
from .common.runlog import run_log

TOP_N = 500
MAX_AGE = timedelta(hours=24)


class WatchItem(NamedTuple):
    appid: int
    peak_ccu_rank: int | None
    owners_rank: int | None


def select_watchlist(games: Iterable[tuple[int, int | None, int | None]],
                     top_n: int = TOP_N) -> list[WatchItem]:
    """从 (appid, peak_ccu, owners_mid) 里选出名单。纯函数，结果与输入顺序无关。

    返回值按 appid 升序。NULL 当作 0 处理。
    """
    rows = [(int(a), int(p or 0), int(o or 0)) for a, p, o in games]
    by_peak = sorted(rows, key=lambda r: (-r[1], r[0]))[:top_n]
    by_owners = sorted(rows, key=lambda r: (-r[2], -r[1], r[0]))[:top_n]
    peak_rank = {r[0]: i for i, r in enumerate(by_peak, start=1)}
    owners_rank = {r[0]: i for i, r in enumerate(by_owners, start=1)}
    return [WatchItem(a, peak_rank.get(a), owners_rank.get(a))
            for a in sorted(peak_rank.keys() | owners_rank.keys())]


def utcnow() -> datetime:
    """当前 UTC 时间（不带时区信息，和库里的 DATETIME 一致）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def refresh_watchlist() -> int:
    """从 dwd_game 重新生成名单并整表替换，返回名单款数。只读 dwd_game，不改它。"""
    with run_log("ccu_watchlist") as rec:
        conn = connect_etl(settings.DB_NAME)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT appid, peak_ccu, owners_mid FROM dwd_game")
                items = select_watchlist(cur.fetchall())
                now = utcnow()
                cur.execute("DELETE FROM dwd_ccu_watchlist")
                cur.executemany(
                    "INSERT INTO dwd_ccu_watchlist (appid, peak_ccu_rank, owners_rank, refreshed_at) "
                    "VALUES (%s, %s, %s, %s)",
                    [(it.appid, it.peak_ccu_rank, it.owners_rank, now) for it in items],
                )
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()
        rec["rows_loaded"] = len(items)
        rec["in_peak_top"] = sum(it.peak_ccu_rank is not None for it in items)
        rec["in_owners_top"] = sum(it.owners_rank is not None for it in items)
        rec["in_both"] = sum(it.peak_ccu_rank is not None and it.owners_rank is not None for it in items)
        return len(items)


def load_watchlist(*, refresh_if_stale: bool = True) -> list[int]:
    """读出名单的 appid（升序）。名单为空或超过 24 小时没刷新时先重建。

    定时进程每天会主动刷新一次；这里的检查是给手动运行和"定时进程停过一阵"兜底。
    """
    def read() -> tuple[list[int], datetime | None]:
        conn = connect_etl(settings.DB_NAME)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT appid, refreshed_at FROM dwd_ccu_watchlist ORDER BY appid")
                rows = cur.fetchall()
        finally:
            conn.close()
        return [r[0] for r in rows], (min(r[1] for r in rows) if rows else None)

    appids, refreshed_at = read()
    if refresh_if_stale and (refreshed_at is None or utcnow() - refreshed_at > MAX_AGE):
        refresh_watchlist()
        appids, _ = read()
    return appids


if __name__ == "__main__":
    print(f"名单已刷新：{refresh_watchlist()} 款")
