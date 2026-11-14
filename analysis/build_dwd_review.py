"""评论清洗：steam_ods.ods_review_kaggle → steam.dwd_review（按分片执行）。

用法（在仓库根目录）：
    python -m analysis.build_dwd_review --shards 0
    python -m analysis.build_dwd_review --shards 0-12

为什么用 SQL 而不是 pandas：1.21 亿行全在库里，INSERT … SELECT 在服务器内部完成，
不用把数据搬到 Python 再写回去，这也是"用数据库做聚合/加工"的评分点。
按 review_id 区间分块提交，避免单个事务过大（undo 日志膨胀、锁表时间长）。

清洗规则（口径见 docs/schema.md）：
- 缺发表时间、缺"是否推荐"、缺语言的评论丢弃；
- 写评论时的游玩时长为负数视为缺失（NULL）；
- 同一 review_id 只保留一条（主键去重）。
"""
from __future__ import annotations

import argparse
import time

from crawler.common import settings
from crawler.common.db import connect_etl
from crawler.common.runlog import run_log
from crawler.kaggle_reviews import parse_shards

CHUNK = 2_000_000  # 每次提交覆盖的 review_id 区间内大约的行数

INSERT_SQL = f"""
INSERT INTO {settings.DB_NAME}.dwd_review
  (appid, review_id, language, voted_up, playtime_at_review_min, timestamp_created)
SELECT o.game_id, o.review_id, o.language, o.is_positive,
       IF(o.playtime_at_review < 0, NULL, o.playtime_at_review),
       o.reviewed_at
FROM {settings.DB_ODS_NAME}.ods_review_kaggle o
WHERE o.src_shard = %s
  AND o.review_id >= %s AND o.review_id < %s
  AND o.reviewed_at IS NOT NULL
  AND o.is_positive IS NOT NULL
  AND o.language IS NOT NULL AND o.language <> ''
ON DUPLICATE KEY UPDATE
  language = VALUES(language), voted_up = VALUES(voted_up),
  playtime_at_review_min = VALUES(playtime_at_review_min),
  timestamp_created = VALUES(timestamp_created)
"""


def build_shard(cur, conn, n: int) -> dict:
    cur.execute(
        f"SELECT COUNT(*), MIN(review_id), MAX(review_id) FROM {settings.DB_ODS_NAME}.ods_review_kaggle "
        "WHERE src_shard = %s", (n,))
    total, lo, hi = cur.fetchone()
    stats = {"shard": n, "rows_in_ods": total}
    if not total:
        return stats
    # 按 review_id 值域均分成若干块，每块大约 CHUNK 行
    chunks = max(1, -(-total // CHUNK))
    step = -(-(hi - lo + 1) // chunks)
    t0 = time.perf_counter()
    for i in range(chunks):
        a, b = lo + i * step, min(lo + (i + 1) * step, hi + 1)
        cur.execute(INSERT_SQL, (n, a, b))
        conn.commit()
        print(f"  shard {n} chunk {i + 1}/{chunks}: {time.perf_counter() - t0:,.0f}s")
    cur.execute(
        f"SELECT COUNT(*) FROM {settings.DB_NAME}.dwd_review d "
        f"JOIN {settings.DB_ODS_NAME}.ods_review_kaggle o ON o.review_id = d.review_id AND o.game_id = d.appid "
        "WHERE o.src_shard = %s", (n,))
    stats["rows_in_dwd"] = cur.fetchone()[0]
    stats["rows_dropped"] = total - stats["rows_in_dwd"]
    stats["build_sec"] = round(time.perf_counter() - t0, 1)
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--shards", required=True, help="分片编号，如 0、0-12")
    args = ap.parse_args()
    conn = connect_etl(settings.DB_NAME)
    try:
        with conn.cursor() as cur:
            for n in parse_shards(args.shards):
                with run_log("build_dwd_review", shard=n) as log:
                    log.update(build_shard(cur, conn, n))
                    log["rows_loaded"] = log.get("rows_in_dwd", 0)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
