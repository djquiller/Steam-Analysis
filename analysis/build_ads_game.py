"""游戏侧 ads 聚合：steam.dwd_game + dwd_game_genre → 只依赖游戏表的 ads 表。

用法（在仓库根目录）：
    python -m analysis.build_ads_game

做什么：把大屏上只靠游戏表就能算的模块预先聚合好，写进 ads 层（字段口径见 docs/schema.md）：
- ads_yearly_release   历年发行量与价格合计（均价由后端用 price_sum / game_cnt 现算）
- ads_genre_heat       类型热度：游戏数、拥有者合计、评论数、好评数
- ads_rating_dist      好评率 1% 分箱；直方图和"价格 × 好评率"箱线图都由它推出
- ads_top_sellers      热销榜，游戏粒度；本脚本负责"拥有者"口径，在线人数取最新快照（没有就是 NULL）
- ads_kpi_overview     只更新游戏总数、估算玩家总量两列
- ads_meta             数据更新时间，以及本脚本读、写的各表行数

为什么这样做：
- 后端只对 ads 小表做过滤和 SUM … GROUP BY，所以这里把 (年份, 类型, 价格区间) 留作聚合粒度，
  只存计数与合计这类可以相加的量；均价、好评率、分位数不能跨组相加，一律不存。
- 一款游戏可以有多个类型，按类型相加会重复计数。因此带 genre 的表除了各类型的行，
  再单独算一组 genre = '__ALL__' 的行：直接对 dwd_game 聚合，每款游戏只计一次，
  没有任何类型的游戏也算在内。它不是各类型行相加得来的（WITH ROLLUP 在这里会算错）。
- 聚合全部用 INSERT … SELECT … GROUP BY 在数据库里完成，Python 只负责编排和核对。

可重跑：所有写入放在一个事务里，先清空本脚本负责的表再写入；失败则整体回滚，表保持上一次的内容。
ads_kpi_overview 和 ads_meta 是与其他脚本共用的表，本脚本只更新自己负责的列和键，不清空整表。
提交前会核对总数（见 CHECKS），对不上就报错回滚，不写入半成品。

留给后续（这次只建了表，没有数据）：
- 评论侧聚合（需要 dwd_review）：ads_review_lang、ads_playtime_dist、ads_review_heatmap、
  ads_game_review_trend，以及 ads_kpi_overview.review_cnt；
- 定时任务（需要 dwd_ccu_snapshot）：ads_ccu_latest、ads_kpi_overview.online_peak_24h / online_peak_at，
  以及每小时更新 ads_top_sellers.ccu_latest / ccu_at；
- 建模：ads_game_cluster、ads_hot_pred、ads_model_metrics、ads_review_sentiment。
"""
from __future__ import annotations

import time

from crawler.common import settings
from crawler.common.db import connect_etl
from crawler.common.runlog import run_log

ALL = "__ALL__"                                 # 类型维度的汇总行，见 docs/schema.md "筛选维度约定"
RELEASED = "d.release_year IS NOT NULL"         # 进入 ads 的游戏：有发行年份
RATED = "d.positive + d.negative >= 10"         # 参与好评率统计的游戏：评论总数 >= 10
# 好评率分箱：整数运算，避免浮点误差把 29.999…% 归错箱；100% 归入 99
RATING_BIN = "LEAST(d.positive * 100 DIV (d.positive + d.negative), 99)"

# 本脚本整表重建的表：(表名, INSERT … SELECT)。每张带 __ALL__ 的表都是
# "直接对 dwd_game 聚合的汇总行" UNION ALL "关联 dwd_game_genre 的各类型行"。
REBUILD: list[tuple[str, str]] = [
    ("ads_yearly_release", f"""
        INSERT INTO ads_yearly_release (release_year, genre, price_bucket, game_cnt, price_sum)
        SELECT d.release_year, '{ALL}', d.price_bucket, COUNT(*), SUM(d.price_usd)
        FROM dwd_game d
        WHERE {RELEASED}
        GROUP BY d.release_year, d.price_bucket
        UNION ALL
        SELECT d.release_year, g.genre, d.price_bucket, COUNT(*), SUM(d.price_usd)
        FROM dwd_game d
        JOIN dwd_game_genre g ON g.appid = d.appid
        WHERE {RELEASED}
        GROUP BY d.release_year, g.genre, d.price_bucket
    """),
    # 本身按类型展示，不设 __ALL__ 行
    ("ads_genre_heat", f"""
        INSERT INTO ads_genre_heat
          (release_year, genre, price_bucket, game_cnt, owners_sum, review_cnt, positive_cnt)
        SELECT d.release_year, g.genre, d.price_bucket, COUNT(*),
               COALESCE(SUM(d.owners_mid), 0), SUM(d.positive + d.negative), SUM(d.positive)
        FROM dwd_game d
        JOIN dwd_game_genre g ON g.appid = d.appid
        WHERE {RELEASED}
        GROUP BY d.release_year, g.genre, d.price_bucket
    """),
    ("ads_rating_dist", f"""
        INSERT INTO ads_rating_dist (release_year, genre, price_bucket, rating_bin, game_cnt)
        SELECT d.release_year, '{ALL}', d.price_bucket, {RATING_BIN}, COUNT(*)
        FROM dwd_game d
        WHERE {RELEASED} AND {RATED}
        GROUP BY d.release_year, d.price_bucket, {RATING_BIN}
        UNION ALL
        SELECT d.release_year, g.genre, d.price_bucket, {RATING_BIN}, COUNT(*)
        FROM dwd_game d
        JOIN dwd_game_genre g ON g.appid = d.appid
        WHERE {RELEASED} AND {RATED}
        GROUP BY d.release_year, g.genre, d.price_bucket, {RATING_BIN}
    """),
    # 游戏粒度，不聚合。在线人数取最新一个采集时刻的快照；dwd_ccu_snapshot 为空时两列都是 NULL。
    # 之后由定时任务每小时更新这两列，这里重建时再从快照表取回，保证重跑不会把它们清掉。
    ("ads_top_sellers", f"""
        INSERT INTO ads_top_sellers
          (appid, name, release_year, price_bucket, price_usd, owners_mid,
           review_cnt, positive_cnt, peak_ccu, ccu_latest, ccu_at)
        SELECT d.appid, d.name, d.release_year, d.price_bucket, d.price_usd, d.owners_mid,
               d.positive + d.negative, d.positive, d.peak_ccu, c.player_count, c.snapshot_at
        FROM dwd_game d
        LEFT JOIN dwd_ccu_snapshot c
          ON c.appid = d.appid
         AND c.snapshot_at = (SELECT MAX(snapshot_at) FROM dwd_ccu_snapshot)
        WHERE {RELEASED}
    """),
]

# 单行 KPI：只写游戏侧的两列。review_cnt 和在线峰值由评论侧聚合、定时任务各自更新，这里不碰。
KPI_SQL = f"""
    INSERT INTO ads_kpi_overview (id, game_cnt, owners_total, updated_at)
    SELECT 1, s.game_cnt, s.owners_total, %s
    FROM (SELECT COUNT(*) AS game_cnt, COALESCE(SUM(d.owners_mid), 0) AS owners_total
          FROM dwd_game d WHERE {RELEASED}) AS s
    ON DUPLICATE KEY UPDATE
      game_cnt = s.game_cnt, owners_total = s.owners_total, updated_at = %s
"""

META_SQL = """
    INSERT INTO ads_meta (meta_key, meta_value, updated_at) VALUES (%s, %s, %s) AS new
    ON DUPLICATE KEY UPDATE meta_value = new.meta_value, updated_at = new.updated_at
"""
# 在 ads_meta 里登记行数的表：读到的两张明细表 + 写入的 ads 表
META_TABLES = ["dwd_game", "dwd_game_genre"] + [t for t, _ in REBUILD] + ["ads_kpi_overview"]

# 提交前的核对：(名称, 明细表上的口径, ads 表上的口径)，两边必须相等。
# 明细一侧不经过 GROUP BY 维度，独立于上面的聚合 SQL。
CHECKS: list[tuple[str, str, str]] = [
    ("games_released",      # __ALL__ 行的游戏数 = 有发行年份的去重游戏数（不是各类型相加）
     f"SELECT COUNT(*) FROM dwd_game d WHERE {RELEASED}",
     f"SELECT SUM(game_cnt) FROM ads_yearly_release WHERE genre = '{ALL}'"),
    ("price_sum",
     f"SELECT SUM(d.price_usd) FROM dwd_game d WHERE {RELEASED}",
     f"SELECT SUM(price_sum) FROM ads_yearly_release WHERE genre = '{ALL}'"),
    ("game_genre_pairs",    # 各类型行相加 = 游戏 × 类型的对数（多类型游戏各计一次）
     f"SELECT COUNT(*) FROM dwd_game d JOIN dwd_game_genre g ON g.appid = d.appid WHERE {RELEASED}",
     f"SELECT SUM(game_cnt) FROM ads_yearly_release WHERE genre <> '{ALL}'"),
    ("genre_heat_pairs",
     f"SELECT COUNT(*) FROM dwd_game d JOIN dwd_game_genre g ON g.appid = d.appid WHERE {RELEASED}",
     "SELECT SUM(game_cnt) FROM ads_genre_heat"),
    ("games_rated",         # 分箱游戏数之和 = 有好评率的游戏数
     f"SELECT COUNT(*) FROM dwd_game d WHERE {RELEASED} AND {RATED}",
     f"SELECT SUM(game_cnt) FROM ads_rating_dist WHERE genre = '{ALL}'"),
    ("top_sellers_rows",
     f"SELECT COUNT(*) FROM dwd_game d WHERE {RELEASED}",
     "SELECT COUNT(*) FROM ads_top_sellers"),
    ("kpi_game_cnt",
     f"SELECT COUNT(*) FROM dwd_game d WHERE {RELEASED}",
     "SELECT game_cnt FROM ads_kpi_overview WHERE id = 1"),
    ("kpi_owners_total",
     f"SELECT COALESCE(SUM(d.owners_mid), 0) FROM dwd_game d WHERE {RELEASED}",
     "SELECT owners_total FROM ads_kpi_overview WHERE id = 1"),
]


def scalar(cur, sql: str, args: tuple | None = None):
    cur.execute(sql, args)
    return cur.fetchone()[0]


def main() -> None:
    with run_log("build_ads_game") as stats:
        conn = connect_etl(settings.DB_NAME)
        try:
            with conn.cursor() as cur:
                now = scalar(cur, "SELECT UTC_TIMESTAMP()")   # 本次运行统一的时间戳
                if scalar(cur, "SELECT COUNT(*) FROM dwd_game_genre WHERE genre = %s", (ALL,)):
                    raise RuntimeError(f"dwd_game_genre 里出现了保留值 {ALL}，会和汇总行混在一起")

                for table, insert_sql in REBUILD:
                    t0 = time.perf_counter()
                    cur.execute(f"DELETE FROM {table}")     # 不用 TRUNCATE：它会隐式提交，破坏事务
                    cur.execute(insert_sql)
                    stats[f"rows_{table}"] = cur.rowcount
                    stats[f"sec_{table}"] = round(time.perf_counter() - t0, 2)
                    print(f"  {table}: {cur.rowcount:,} 行，{stats[f'sec_{table}']} 秒")
                cur.execute(KPI_SQL, (now, now))

                for name, sql_dwd, sql_ads in CHECKS:
                    want, got = scalar(cur, sql_dwd), scalar(cur, sql_ads)
                    stats[f"check_{name}"] = int(want) if want == int(want) else float(want)
                    if want != got:
                        raise RuntimeError(f"核对不一致 {name}：明细表 {want}，ads 表 {got}；已回滚")

                for table in META_TABLES:
                    n = scalar(cur, f"SELECT COUNT(*) FROM {table}")
                    cur.execute(META_SQL, (f"rows.{table}", str(n), now))
                cur.execute(META_SQL, ("data_updated_at", now.strftime("%Y-%m-%d %H:%M:%S"), now))

                conn.commit()
                stats["rows_loaded"] = sum(stats[f"rows_{t}"] for t, _ in REBUILD)
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()


if __name__ == "__main__":
    main()
