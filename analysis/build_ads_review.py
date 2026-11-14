"""评论侧 ads 聚合：steam.dwd_review（1.21 亿行）→ 依赖评论表的 ads 表。

用法（在仓库根目录）：
    python -m analysis.build_ads_review                # 全量：先按游戏汇总，再生成 ads
    python -m analysis.build_ads_review --reuse-stage  # 跳过第一步，直接用已有的中间表重算 ads

做什么（字段口径见 docs/schema.md）：
- ads_review_lang        年 × 类型 × 价格区间 × 语言 → 评论数、好评数
- ads_playtime_dist      年 × 类型 × 价格区间 × 写评论时的游玩时长分箱 → 评论数
- ads_review_heatmap     年 × 类型 × 价格区间 × 星期 × 小时（UTC）→ 评论数
- ads_game_review_trend  游戏 × 月 → 评论数、好评数
- ads_kpi_overview       只更新 review_cnt 一列
- ads_meta               数据更新时间，以及本脚本读、写的各表行数

为什么分两步：
1. **按游戏汇总**（慢，约二十分钟）：把 dwd_review 按 appid 区间分块，每块在库内
   GROUP BY 成四张"游戏 × 某个维度"的中间表 steam_ods.stg_review_*。
   一款游戏可以属于多个类型，如果直接拿 1.21 亿行评论去关联 dwd_game_genre，
   行数会膨胀到约三倍；先压到游戏粒度（几百万行），再关联类型就便宜了。
   中间表不做任何过滤（包括不在 dwd_game 里的游戏），所以它们的合计必须等于 dwd_review 的行数，
   这一点在第二步核对。中间表保留下来，供数据质量报告和 --reuse-stage 复用，不必再扫一遍评论表。
2. **生成 ads**（快，几十秒）：中间表关联 dwd_game（只要有发行年份的游戏）和 dwd_game_genre，
   写入 ads；和游戏侧一样，每张聚合表另算一组 genre = '__ALL__' 的行，每条评论只计一次。

为什么分块、为什么用 READ COMMITTED：
- 在默认的 REPEATABLE READ 下，INSERT … SELECT 会给读到的每一行源数据加共享锁，
  1.21 亿行会把锁表撑爆；READ COMMITTED 下读源表是一致性读，不加锁。
- 分块后每块只有几百万行，四次 GROUP BY 读同一块时数据都还在 buffer pool 里，
  第二到第四次几乎不再读盘；每块单独提交，中途失败只需重跑。

可重跑：第一步开始前清空中间表；第二步在一个事务里先清空本脚本负责的 ads 表再写入，
提交前核对总数（见 CHECKS），对不上就回滚，ads 保持上一次的内容。
ads_kpi_overview 和 ads_meta 与其他脚本共用，本脚本只更新自己负责的列和键。
"""
from __future__ import annotations

import argparse
import time

from crawler.common import settings
from crawler.common.db import connect_etl
from crawler.common.runlog import run_log

ALL = "__ALL__"                              # 类型维度的汇总行，见 docs/schema.md "筛选维度约定"
ODS = settings.DB_ODS_NAME
RELEASED = "d.release_year IS NOT NULL"      # 进入 ads 的游戏：有发行年份
CHUNK_REVIEWS = 6_000_000                    # 每块大约多少条评论（按游戏集的 Steam 评论计数估算）
PLAYTIME_MISSING = 255                       # 中间表里"写评论时的游玩时长缺失"的分箱编号，不进 ads

# 写评论时的游玩时长分箱（分钟，左闭右开），与 docs/schema.md 的分箱表一一对应
PLAYTIME_BOUNDS = [60, 120, 300, 600, 1200, 3000, 6000, 12000, 30000, 60000]
PLAYTIME_BIN = (
    f"CASE WHEN r.playtime_at_review_min IS NULL THEN {PLAYTIME_MISSING} "
    + " ".join(f"WHEN r.playtime_at_review_min < {b} THEN {i}" for i, b in enumerate(PLAYTIME_BOUNDS))
    + f" ELSE {len(PLAYTIME_BOUNDS)} END"
)

# ---------- 第一步：按游戏汇总到中间表 ----------

STAGE_DDL = [
    f"""CREATE TABLE IF NOT EXISTS {ODS}.stg_review_lang (
          appid         INT UNSIGNED    NOT NULL,
          language      VARCHAR(32)     NOT NULL,
          review_cnt    INT UNSIGNED    NOT NULL,
          positive_cnt  INT UNSIGNED    NOT NULL,
          PRIMARY KEY (appid, language)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
          COMMENT='中间表：游戏 × 评论语言，由 analysis/build_ads_review.py 重建'""",
    f"""CREATE TABLE IF NOT EXISTS {ODS}.stg_review_playtime (
          appid         INT UNSIGNED      NOT NULL,
          playtime_bin  TINYINT UNSIGNED  NOT NULL COMMENT '0–10 同 ads_playtime_dist；255 = 时长缺失',
          review_cnt    INT UNSIGNED      NOT NULL,
          PRIMARY KEY (appid, playtime_bin)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
          COMMENT='中间表：游戏 × 写评论时的游玩时长分箱，由 analysis/build_ads_review.py 重建'""",
    f"""CREATE TABLE IF NOT EXISTS {ODS}.stg_review_hour (
          appid       INT UNSIGNED      NOT NULL,
          weekday     TINYINT UNSIGNED  NOT NULL COMMENT '0 = 周一，UTC',
          hour        TINYINT UNSIGNED  NOT NULL COMMENT 'UTC',
          review_cnt  INT UNSIGNED      NOT NULL,
          PRIMARY KEY (appid, weekday, hour)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
          COMMENT='中间表：游戏 × 星期 × 小时，由 analysis/build_ads_review.py 重建'""",
    f"""CREATE TABLE IF NOT EXISTS {ODS}.stg_review_month (
          appid         INT UNSIGNED  NOT NULL,
          month_start   DATE          NOT NULL COMMENT 'UTC',
          review_cnt    INT UNSIGNED  NOT NULL,
          positive_cnt  INT UNSIGNED  NOT NULL,
          PRIMARY KEY (appid, month_start)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
          COMMENT='中间表：游戏 × 月，由 analysis/build_ads_review.py 重建'""",
]
STAGE_TABLES = ["stg_review_lang", "stg_review_playtime", "stg_review_hour", "stg_review_month"]

# 每块执行的四条汇总；%s, %s 是 appid 区间 [lo, hi)，走 dwd_review 的聚簇主键 (appid, review_id)
RANGE = "r.appid >= %s AND r.appid < %s"
STAGE_SQL = [
    ("stg_review_lang", f"""
        INSERT INTO {ODS}.stg_review_lang (appid, language, review_cnt, positive_cnt)
        SELECT r.appid, r.language, COUNT(*), SUM(r.voted_up)
        FROM dwd_review r WHERE {RANGE}
        GROUP BY r.appid, r.language"""),
    ("stg_review_playtime", f"""
        INSERT INTO {ODS}.stg_review_playtime (appid, playtime_bin, review_cnt)
        SELECT r.appid, {PLAYTIME_BIN} AS b, COUNT(*)
        FROM dwd_review r WHERE {RANGE}
        GROUP BY r.appid, b"""),
    ("stg_review_hour", f"""
        INSERT INTO {ODS}.stg_review_hour (appid, weekday, hour, review_cnt)
        SELECT r.appid, WEEKDAY(r.timestamp_created) AS wd, HOUR(r.timestamp_created) AS hr, COUNT(*)
        FROM dwd_review r WHERE {RANGE}
        GROUP BY r.appid, wd, hr"""),
    ("stg_review_month", f"""
        INSERT INTO {ODS}.stg_review_month (appid, month_start, review_cnt, positive_cnt)
        SELECT r.appid, DATE_FORMAT(r.timestamp_created, '%%Y-%%m-01') AS m, COUNT(*), SUM(r.voted_up)
        FROM dwd_review r WHERE {RANGE}
        GROUP BY r.appid, m"""),
]


def plan_chunks(cur) -> list[tuple[int, int]]:
    """按游戏集里 Steam 的好评 + 差评计数估算每个 appid 的评论量，切成大约 CHUNK_REVIEWS 条一块。

    只是估算（评论集约覆盖 Steam 计数的 81%，另有不在游戏集里的 appid），
    所以第一块从 0 开始、最后一块到 2^32，保证任何 appid 都落在某一块里。
    """
    cur.execute("SELECT appid, positive + negative FROM dwd_game ORDER BY appid")
    bounds, acc = [0], 0
    for appid, n in cur.fetchall():
        acc += n
        if acc >= CHUNK_REVIEWS:
            bounds.append(appid + 1)
            acc = 0
    bounds.append(2 ** 32)
    return list(zip(bounds[:-1], bounds[1:]))


def build_stage(conn, cur, stats: dict) -> None:
    for ddl in STAGE_DDL:
        cur.execute(ddl)
    for t in STAGE_TABLES:
        cur.execute(f"TRUNCATE TABLE {ODS}.{t}")
    chunks = plan_chunks(cur)
    t0 = time.perf_counter()
    for i, (lo, hi) in enumerate(chunks, 1):
        for _, sql in STAGE_SQL:
            cur.execute(sql, (lo, hi))
        conn.commit()
        print(f"  第一步 块 {i}/{len(chunks)}（appid {lo}–{hi - 1}）累计 {time.perf_counter() - t0:,.0f} 秒")
    stats["stage_chunks"] = len(chunks)
    stats["sec_stage"] = round(time.perf_counter() - t0, 1)


# ---------- 第二步：中间表 → ads（一个事务） ----------

def by_dims(stage: str, cols: str, sums: str, where: str = "") -> str:
    """生成 "__ALL__ 行 UNION ALL 各类型行" 的 SELECT。

    中间表在另一个库里，是普通表而不是临时表，所以同一条语句里可以引用两次。
    __ALL__ 行直接关联 dwd_game（每条评论只计一次，没有类型的游戏也算在内），
    各类型行再关联 dwd_game_genre（多类型游戏的评论在每个类型下各计一次）。
    """
    extra = f" AND {where}" if where else ""
    return f"""
        SELECT d.release_year, '{ALL}', d.price_bucket, {cols}, {sums}
        FROM {ODS}.{stage} s JOIN dwd_game d ON d.appid = s.appid
        WHERE {RELEASED}{extra}
        GROUP BY d.release_year, d.price_bucket, {cols}
        UNION ALL
        SELECT d.release_year, g.genre, d.price_bucket, {cols}, {sums}
        FROM {ODS}.{stage} s JOIN dwd_game d ON d.appid = s.appid
        JOIN dwd_game_genre g ON g.appid = s.appid
        WHERE {RELEASED}{extra}
        GROUP BY d.release_year, g.genre, d.price_bucket, {cols}"""


REBUILD: list[tuple[str, str]] = [
    ("ads_review_lang",
     "INSERT INTO ads_review_lang (release_year, genre, price_bucket, language, review_cnt, positive_cnt)"
     + by_dims("stg_review_lang", "s.language", "SUM(s.review_cnt), SUM(s.positive_cnt)")),
    ("ads_playtime_dist",
     "INSERT INTO ads_playtime_dist (release_year, genre, price_bucket, playtime_bin, review_cnt)"
     + by_dims("stg_review_playtime", "s.playtime_bin", "SUM(s.review_cnt)",
               where=f"s.playtime_bin <> {PLAYTIME_MISSING}")),
    ("ads_review_heatmap",
     "INSERT INTO ads_review_heatmap (release_year, genre, price_bucket, weekday, hour, review_cnt)"
     + by_dims("stg_review_hour", "s.weekday, s.hour", "SUM(s.review_cnt)")),
    # 全局表，游戏粒度，不分类型；只收进入 ads 的游戏
    ("ads_game_review_trend", f"""
        INSERT INTO ads_game_review_trend (appid, month_start, review_cnt, positive_cnt)
        SELECT s.appid, s.month_start, s.review_cnt, s.positive_cnt
        FROM {ODS}.stg_review_month s JOIN dwd_game d ON d.appid = s.appid
        WHERE {RELEASED}"""),
]

# KPI 的评论总数按契约是 dwd_review 的行数（含不在游戏集里的 appid），等于中间表的合计
KPI_SQL = f"""
    UPDATE ads_kpi_overview
    SET review_cnt = (SELECT SUM(review_cnt) FROM {ODS}.stg_review_lang), updated_at = %s
    WHERE id = 1
"""

META_SQL = """
    INSERT INTO ads_meta (meta_key, meta_value, updated_at) VALUES (%s, %s, %s) AS new
    ON DUPLICATE KEY UPDATE meta_value = new.meta_value, updated_at = new.updated_at
"""
META_TABLES = ["dwd_review"] + [t for t, _ in REBUILD]

# 只有进入 ads 的游戏的评论（中间表一侧的口径）
STG_RELEASED = f"FROM {ODS}.{{t}} s JOIN dwd_game d ON d.appid = s.appid WHERE {RELEASED}"
STG_GENRE = (f"FROM {ODS}.{{t}} s JOIN dwd_game d ON d.appid = s.appid "
             f"JOIN dwd_game_genre g ON g.appid = s.appid WHERE {RELEASED}")


def checks(dwd_total: int, dwd_positive: int, dwd_no_playtime: int) -> list[tuple[str, object, str]]:
    """(名称, 期望值或求期望值的 SQL, ads / 中间表上的 SQL)，两边必须相等。

    前一组把中间表和直接扫 dwd_review 得到的数比（核对第一步没有漏块、没有重复），
    后一组把 ads 和中间表比（核对第二步的关联与 __ALL__ 口径）。
    """
    released = STG_RELEASED.format(t="stg_review_lang")
    return [
        ("stage_lang_total", dwd_total, f"SELECT SUM(review_cnt) FROM {ODS}.stg_review_lang"),
        ("stage_lang_positive", dwd_positive, f"SELECT SUM(positive_cnt) FROM {ODS}.stg_review_lang"),
        ("stage_playtime_total", dwd_total, f"SELECT SUM(review_cnt) FROM {ODS}.stg_review_playtime"),
        ("stage_playtime_missing", dwd_no_playtime,
         f"SELECT COALESCE(SUM(review_cnt), 0) FROM {ODS}.stg_review_playtime "
         f"WHERE playtime_bin = {PLAYTIME_MISSING}"),
        ("stage_hour_total", dwd_total, f"SELECT SUM(review_cnt) FROM {ODS}.stg_review_hour"),
        ("stage_month_total", dwd_total, f"SELECT SUM(review_cnt) FROM {ODS}.stg_review_month"),
        ("stage_month_positive", dwd_positive, f"SELECT SUM(positive_cnt) FROM {ODS}.stg_review_month"),
        # 第二步：__ALL__ 行 = 进入 ads 的游戏的评论，每条只计一次
        ("lang_all", f"SELECT SUM(s.review_cnt) {released}",
         f"SELECT SUM(review_cnt) FROM ads_review_lang WHERE genre = '{ALL}'"),
        ("lang_all_positive", f"SELECT SUM(s.positive_cnt) {released}",
         f"SELECT SUM(positive_cnt) FROM ads_review_lang WHERE genre = '{ALL}'"),
        ("lang_genre", f"SELECT SUM(s.review_cnt) {STG_GENRE.format(t='stg_review_lang')}",
         f"SELECT SUM(review_cnt) FROM ads_review_lang WHERE genre <> '{ALL}'"),
        ("playtime_all",
         f"SELECT SUM(s.review_cnt) {STG_RELEASED.format(t='stg_review_playtime')} "
         f"AND s.playtime_bin <> {PLAYTIME_MISSING}",
         f"SELECT SUM(review_cnt) FROM ads_playtime_dist WHERE genre = '{ALL}'"),
        ("heatmap_all", f"SELECT SUM(s.review_cnt) {released}",
         f"SELECT SUM(review_cnt) FROM ads_review_heatmap WHERE genre = '{ALL}'"),
        ("heatmap_genre", f"SELECT SUM(s.review_cnt) {STG_GENRE.format(t='stg_review_lang')}",
         f"SELECT SUM(review_cnt) FROM ads_review_heatmap WHERE genre <> '{ALL}'"),
        ("trend_total", f"SELECT SUM(s.review_cnt) {released}",
         "SELECT SUM(review_cnt) FROM ads_game_review_trend"),
        ("trend_positive", f"SELECT SUM(s.positive_cnt) {released}",
         "SELECT SUM(positive_cnt) FROM ads_game_review_trend"),
        ("kpi_review_cnt", dwd_total, "SELECT review_cnt FROM ads_kpi_overview WHERE id = 1"),
    ]


def scalar(cur, sql: str, args: tuple | None = None):
    cur.execute(sql, args)
    return cur.fetchone()[0]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--reuse-stage", action="store_true",
                    help="跳过第一步，直接用 steam_ods.stg_review_* 现有内容生成 ads")
    args = ap.parse_args()

    with run_log("build_ads_review", reuse_stage=args.reuse_stage) as stats:
        conn = connect_etl(settings.DB_NAME)
        try:
            with conn.cursor() as cur:
                # 读源表不加锁，见模块说明
                cur.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED")
                if scalar(cur, "SELECT COUNT(*) FROM dwd_game_genre WHERE genre = %s", (ALL,)):
                    raise RuntimeError(f"dwd_game_genre 里出现了保留值 {ALL}，会和汇总行混在一起")
                if not args.reuse_stage:
                    build_stage(conn, cur, stats)

                # 独立于中间表、直接扫一遍明细表得到的基准数，供核对用
                t0 = time.perf_counter()
                cur.execute("SELECT COUNT(*), SUM(voted_up), SUM(playtime_at_review_min IS NULL) "
                            "FROM dwd_review")
                dwd_total, dwd_positive, dwd_no_playtime = (int(x) for x in cur.fetchone())
                stats["sec_dwd_scan"] = round(time.perf_counter() - t0, 1)
                print(f"  dwd_review：{dwd_total:,} 条，好评 {dwd_positive:,}，"
                      f"缺游玩时长 {dwd_no_playtime:,}（{stats['sec_dwd_scan']} 秒）")

                now = scalar(cur, "SELECT UTC_TIMESTAMP()")
                for table, insert_sql in REBUILD:
                    t0 = time.perf_counter()
                    cur.execute(f"DELETE FROM {table}")      # 不用 TRUNCATE：它会隐式提交，破坏事务
                    cur.execute(insert_sql)
                    stats[f"rows_{table}"] = cur.rowcount
                    stats[f"sec_{table}"] = round(time.perf_counter() - t0, 2)
                    print(f"  {table}: {cur.rowcount:,} 行，{stats[f'sec_{table}']} 秒")
                cur.execute(KPI_SQL, (now,))
                if cur.rowcount != 1:
                    raise RuntimeError("ads_kpi_overview 没有 id = 1 的行：先运行 python -m analysis.build_ads_game")

                for name, want, sql_got in checks(dwd_total, dwd_positive, dwd_no_playtime):
                    want = scalar(cur, want) if isinstance(want, str) else want
                    got = scalar(cur, sql_got)
                    stats[f"check_{name}"] = int(want or 0)
                    if want != got:
                        raise RuntimeError(f"核对不一致 {name}：期望 {want}，实际 {got}；已回滚")

                for table in META_TABLES:
                    n = dwd_total if table == "dwd_review" else scalar(cur, f"SELECT COUNT(*) FROM {table}")
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
