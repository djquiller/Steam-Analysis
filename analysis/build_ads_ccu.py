"""在线人数侧 ads 聚合：steam.dwd_ccu_snapshot → 大屏上和在线人数有关的三处。

用法（在仓库根目录）：
    python -m analysis.build_ads_ccu

定时进程（crawler/scheduler.py）每采完一轮在线人数就调用一次 build()，启动时也先跑一次，
所以大屏上的在线数据每小时跟着刷新。

写哪些表（字段口径见 docs/schema.md）：
- ads_ccu_latest       整表重写：最新一轮在线人数最高的 100 款，带上一轮的人数用于显示升降
- ads_top_sellers      只更新 ccu_latest / ccu_at 两列：最新一轮里采到的游戏填人数，其余置 NULL
- ads_kpi_overview     只更新 online_peak_24h / online_peak_at（和 updated_at）
- ads_meta             ccu_updated_at，以及 rows.ads_ccu_latest、rows.dwd_ccu_snapshot

几条口径：
- "最新一轮"取最近一个**完整**的采集时刻：该时刻的快照行数不少于当前采集名单的 COMPLETE_RATIO。
  这样即使手动运行时正赶上一轮采到一半，也不会拿半截数据去排榜。
- 24 小时峰值的窗口以最新一轮为终点往前 24 小时，而不是以"现在"为终点：采集停了的时候，
  大屏仍显示最后一天的峰值，而不是突然变成空。窗口内同样只算完整的轮次。
- 峰值是"采集名单内游戏在线人数之和"的最大值，只覆盖名单内约 700 款，不是全 Steam 在线人数。

可重跑：所有写入在一个事务里，提交前核对行数，对不上就回滚，表保持上一次的内容。
还没有任何完整轮次时什么都不改，只打印提示。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from crawler.common import settings
from crawler.common.db import connect_etl
from crawler.common.runlog import run_log

TOP_N = 100
COMPLETE_RATIO = 0.9
PEAK_WINDOW = timedelta(hours=24)

UPSERT_META = """
    INSERT INTO ads_meta (meta_key, meta_value, updated_at) VALUES (%s, %s, %s) AS new
    ON DUPLICATE KEY UPDATE meta_value = new.meta_value, updated_at = new.updated_at
"""


# ------------------------------------------------------------------ 纯函数（便于单元测试）

def pick_latest_complete(rounds: list[tuple[datetime, int]], watchlist_size: int) -> datetime | None:
    """rounds: [(snapshot_at, 行数)]。返回最近一个行数达到名单 COMPLETE_RATIO 的时刻；没有返回 None。"""
    need = max(1, int(watchlist_size * COMPLETE_RATIO))
    complete = [at for at, n in rounds if n >= need]
    return max(complete) if complete else None


def pick_peak(totals: list[tuple[datetime, int]], latest: datetime) -> tuple[datetime, int] | None:
    """totals: [(snapshot_at, 名单内在线人数之和)]，只含完整轮次。
    取 (latest - 24h, latest] 窗口内人数之和最大的一轮；并列时取较晚的那一轮。"""
    window = [(at, n) for at, n in totals if latest - PEAK_WINDOW < at <= latest]
    if not window:
        return None
    return max(window, key=lambda x: (x[1], x[0]))


# ------------------------------------------------------------------ 聚合

def _scalar(cur, sql: str, args: tuple = ()):
    cur.execute(sql, args)
    row = cur.fetchone()
    return row[0] if row else None


def build() -> dict:
    """聚合一次并提交，返回本次的统计数字（也写进运行记录）。"""
    with run_log("build_ads_ccu") as stats:
        conn = connect_etl(settings.DB_NAME)
        try:
            with conn.cursor() as cur:
                now = _scalar(cur, "SELECT UTC_TIMESTAMP()")
                watchlist_size = int(_scalar(cur, "SELECT COUNT(*) FROM dwd_ccu_watchlist") or 0)
                # 只看最近两天的轮次就够了（24 小时窗口 + 上一轮），走 snapshot_at 索引
                cur.execute(
                    """SELECT snapshot_at, COUNT(*), SUM(player_count) FROM dwd_ccu_snapshot
                       WHERE snapshot_at >= (SELECT MAX(snapshot_at) FROM dwd_ccu_snapshot) - INTERVAL 2 DAY
                       GROUP BY snapshot_at"""
                )
                rounds = [(at, int(n), int(total)) for at, n, total in cur.fetchall()]
                latest = pick_latest_complete([(at, n) for at, n, _ in rounds], watchlist_size)
                stats["watchlist"] = watchlist_size
                if latest is None:
                    stats["skipped"] = "还没有完整的采集轮次"
                    print("  还没有完整的采集轮次，什么都不改")
                    conn.rollback()
                    return stats
                prev = max((at for at, _, _ in rounds if at < latest), default=None)
                stats["latest"] = latest.isoformat(sep=" ")
                stats["prev"] = prev.isoformat(sep=" ") if prev else None

                # 1. 实时在线榜：最新一轮 Top N，带上一轮人数
                cur.execute("DELETE FROM ads_ccu_latest")
                cur.execute(
                    """INSERT INTO ads_ccu_latest (appid, name, player_count, player_count_prev, snapshot_at)
                       SELECT s.appid, g.name, s.player_count, p.player_count, s.snapshot_at
                       FROM dwd_ccu_snapshot s
                       JOIN dwd_game g ON g.appid = s.appid
                       LEFT JOIN dwd_ccu_snapshot p ON p.appid = s.appid AND p.snapshot_at = %s
                       WHERE s.snapshot_at = %s
                       ORDER BY s.player_count DESC, s.appid
                       LIMIT %s""",
                    (prev, latest, TOP_N),
                )
                stats["rows_ads_ccu_latest"] = cur.rowcount

                # 2. 热销榜的"在线人数"口径：先全部清空再按最新一轮填，没采到的保持 NULL
                cur.execute("UPDATE ads_top_sellers SET ccu_latest = NULL, ccu_at = NULL "
                            "WHERE ccu_latest IS NOT NULL OR ccu_at IS NOT NULL")
                cur.execute(
                    """UPDATE ads_top_sellers t
                       JOIN dwd_ccu_snapshot s ON s.appid = t.appid AND s.snapshot_at = %s
                       SET t.ccu_latest = s.player_count, t.ccu_at = s.snapshot_at""",
                    (latest,),
                )
                stats["rows_top_sellers_ccu"] = cur.rowcount

                # 3. KPI：近 24 小时（以最新一轮为终点）名单内在线人数之和的最大值
                need = max(1, int(watchlist_size * COMPLETE_RATIO))
                peak = pick_peak([(at, total) for at, n, total in rounds if n >= need], latest)
                if peak:
                    peak_at, peak_total = peak
                    cur.execute(
                        "UPDATE ads_kpi_overview SET online_peak_24h = %s, online_peak_at = %s, updated_at = %s "
                        "WHERE id = 1",
                        (peak_total, peak_at, now),
                    )
                    if cur.rowcount == 0:
                        print("  ads_kpi_overview 还没有 id = 1 这一行（先跑 analysis.build_ads_game），跳过 KPI")
                    stats["online_peak_24h"] = peak_total
                    stats["online_peak_at"] = peak_at.isoformat(sep=" ")

                # 提交前核对：榜单行数 = min(TOP_N, 最新一轮行数)；热销榜填上的游戏数 = 最新一轮里在热销榜中的游戏数
                latest_rows = int(_scalar(cur, "SELECT COUNT(*) FROM dwd_ccu_snapshot WHERE snapshot_at = %s", (latest,)))
                want_board = min(TOP_N, int(_scalar(
                    cur, "SELECT COUNT(*) FROM dwd_ccu_snapshot s JOIN dwd_game g ON g.appid = s.appid "
                         "WHERE s.snapshot_at = %s", (latest,))))
                got_board = int(_scalar(cur, "SELECT COUNT(*) FROM ads_ccu_latest"))
                want_top = int(_scalar(
                    cur, "SELECT COUNT(*) FROM dwd_ccu_snapshot s JOIN ads_top_sellers t ON t.appid = s.appid "
                         "WHERE s.snapshot_at = %s", (latest,)))
                got_top = int(_scalar(cur, "SELECT COUNT(*) FROM ads_top_sellers WHERE ccu_latest IS NOT NULL"))
                if (want_board, want_top) != (got_board, got_top):
                    raise RuntimeError(
                        f"核对失败：在线榜 {got_board}/{want_board} 行，热销榜在线人数 {got_top}/{want_top} 款")

                for key, value in [
                    ("ccu_updated_at", now.strftime("%Y-%m-%d %H:%M:%S")),
                    ("rows.ads_ccu_latest", str(got_board)),
                    ("rows.dwd_ccu_snapshot", str(_scalar(cur, "SELECT COUNT(*) FROM dwd_ccu_snapshot"))),
                ]:
                    cur.execute(UPSERT_META, (key, value, now))

            conn.commit()
            stats["rows_loaded"] = got_board + got_top
            print(f"  最新一轮 {latest}（{latest_rows} 款），在线榜 {got_board} 行，"
                  f"热销榜填入在线人数 {got_top} 款，24 小时峰值 {stats.get('online_peak_24h')}")
            return stats
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()


def main() -> None:
    build()


if __name__ == "__main__":
    main()
