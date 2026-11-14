"""评论原文分层抽样：每款游戏最多保留 k 条原文，写入 steam_ods.ods_review_text_sample。

用法（在仓库根目录；通常由 scripts/load_data.py 在导入每个分片时顺带调用）：
    python -m crawler.kaggle_review_text --shard 0 --k 30

为什么要抽样：1.21 亿条原文太大且不必全存；关键词分析和情感模型只需要每款游戏有代表性的几十条。
为什么"每款游戏抽 k 条"而不是整体随机：评论高度集中在少数爆款上，整体随机抽样几乎只会抽到热门游戏，
按游戏分层才能覆盖到大部分游戏。

怎么做到跨分片可合并、可重跑：
- 每条评论的 sample_key = review_id 的确定性哈希（splitmix64），相当于一个固定的随机数；
- 每款游戏保留 sample_key 最小的 k 条 —— 这等价于在该游戏全部评论中均匀随机抽 k 条；
- 每处理完一个分片，就把表裁剪回"每款游戏 k 条"。最终结果只取决于导入了哪些分片，与顺序、重跑次数无关。
导入时 k 取得偏大（默认 30），最终用多少条由分析阶段按需要再裁剪。
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from .common import settings
from .common.db import connect_etl
from .common.runlog import run_log

DEFAULT_K = 30
INSERT_BATCH = 500


def sample_key(review_ids: np.ndarray) -> np.ndarray:
    """splitmix64：把 review_id 打散成均匀分布的 64 位无符号整数（确定性，不依赖随机种子）。"""
    z = review_ids.astype(np.uint64) + np.uint64(0x9E3779B97F4A7C15)
    z = (z ^ (z >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
    z = (z ^ (z >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
    return z ^ (z >> np.uint64(31))


def select_ids(pf: pq.ParquetFile, k: int) -> pd.DataFrame:
    """第一遍：只读 review_id、game_id，选出本分片内每款游戏 sample_key 最小的 k 条。"""
    t = pf.read(columns=["review_id", "game_id"])
    df = pd.DataFrame({"review_id": t["review_id"].to_numpy(), "game_id": t["game_id"].to_numpy()})
    df["sample_key"] = sample_key(df["review_id"].to_numpy())
    df = df.sort_values(["game_id", "sample_key"]).groupby("game_id", sort=False).head(k)
    return df


def fetch_texts(pf: pq.ParquetFile, chosen: pd.DataFrame) -> pd.DataFrame:
    """第二遍：分批读原文，只保留第一遍选中的 review_id。"""
    wanted = pa.array(chosen["review_id"].to_numpy())
    parts = []
    for batch in pf.iter_batches(batch_size=1_000_000, columns=["review_id", "language", "is_positive", "review"]):
        mask = pc.is_in(batch.column("review_id"), value_set=wanted)
        parts.append(batch.filter(mask).to_pandas())
    texts = pd.concat(parts, ignore_index=True)
    return chosen.merge(texts, on="review_id", how="inner")


def trim(cur, k: int) -> int:
    """把整张表裁剪回每款游戏最多 k 条（保留 sample_key 最小的）。"""
    cur.execute(
        "DELETE t FROM ods_review_text_sample t JOIN ("
        "  SELECT review_id FROM ("
        "    SELECT review_id, ROW_NUMBER() OVER (PARTITION BY game_id ORDER BY sample_key) AS rn"
        "    FROM ods_review_text_sample) x WHERE x.rn > %s"
        ") d ON d.review_id = t.review_id", (k,))
    return cur.rowcount


def sample_shard(n: int, path: Path, k: int = DEFAULT_K) -> dict:
    t0 = time.perf_counter()
    pf = pq.ParquetFile(path)
    chosen = select_ids(pf, k)
    rows = fetch_texts(pf, chosen)
    rows["is_positive"] = rows["is_positive"].astype("boolean").astype("Int8")
    rows["src_shard"] = n
    cols = ["review_id", "game_id", "language", "is_positive", "sample_key", "review", "src_shard"]
    data = rows[cols].astype(object).where(rows[cols].notna(), None).values.tolist()
    # numpy 的 uint64 转成 Python int，PyMySQL 才能正确写入 BIGINT UNSIGNED
    data = [[int(r[0]), int(r[1]), r[2], r[3], int(r[4]), r[5], int(r[6])] for r in data]

    conn = connect_etl(settings.DB_ODS_NAME)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM ods_review_text_sample WHERE src_shard = %s", (n,))
            sql = (f"INSERT INTO ods_review_text_sample ({', '.join(cols)}) "
                   f"VALUES ({', '.join(['%s'] * len(cols))})")
            for i in range(0, len(data), INSERT_BATCH):
                cur.executemany(sql, data[i:i + INSERT_BATCH])
            trimmed = trim(cur, k)
            conn.commit()
            cur.execute("SELECT COUNT(*), COUNT(DISTINCT game_id) FROM ods_review_text_sample")
            total, games = cur.fetchone()
    finally:
        conn.close()
    return {"shard": n, "k": k, "candidates": len(data), "trimmed": trimmed,
            "sample_rows_total": total, "sample_games_total": games,
            "rows_loaded": len(data), "text_sec": round(time.perf_counter() - t0, 1)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--shard", type=int, required=True)
    ap.add_argument("--k", type=int, default=DEFAULT_K)
    args = ap.parse_args()
    path = settings.DATA_DIR / "reviews" / f"reviews-{args.shard:03d}.parquet"
    with run_log("kaggle_review_text", shard=args.shard) as log:
        log.update(sample_shard(args.shard, path, args.k))


if __name__ == "__main__":
    main()
