"""把 Kaggle 评论集的 Parquet 分片逐片导入 steam_ods.ods_review_kaggle。

用法（在仓库根目录）：
    python -m crawler.kaggle_reviews --shards 0            # 下载第 0 片并导入
    python -m crawler.kaggle_reviews --shards 1-12 --delete-after   # 逐片下载、导入、删除
    python -m crawler.kaggle_reviews --shards 0 --no-download       # 用已下载的分片

为什么这样做：
- 全量 1.21 亿条、约 23 GB，逐片处理，磁盘上同时只留一个分片。
- 只读需要的列：评论原文（体积大头）和评论者哈希 ID（隐私）不进这张表；
  原文只按"每款游戏最多 k 条"抽样另存（见 crawler/kaggle_review_text.py）。
- 用 LOAD DATA LOCAL INFILE 批量导入，比逐行 INSERT 快一个数量级；
  需要服务器开启 local_infile（见 storage/README.md）。
- 可重跑：导入前先删掉该分片已有的行（按 src_shard），再用 IGNORE 跳过重复主键。
"""
from __future__ import annotations

import argparse
import os
import tempfile
import time
from pathlib import Path

import pyarrow.parquet as pq

from .common import settings
from .common.db import connect_etl
from .common.kaggle_cli import download_file
from .common.runlog import run_log

DATASET = "sergiodelcarpio/steam-reviews"
BATCH_ROWS = 1_000_000

# 源列 → ods 列（顺序即写入临时文件的列顺序）
COLUMNS = [
    "review_id", "game_id", "is_positive", "language", "reviewed_at",
    "playtime_at_review", "playtime_forever", "votes_up",
    "steam_purchase", "received_for_free", "written_during_early_access",
]
BOOL_COLS = {"is_positive", "steam_purchase", "received_for_free", "written_during_early_access"}


def shard_file(n: int) -> str:
    return f"reviews-{n:03d}.parquet"


def parse_shards(spec: str) -> list[int]:
    out: list[int] = []
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-")
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def download(n: int, dest_dir: Path) -> Path:
    return download_file(DATASET, shard_file(n), dest_dir)


def write_batch_tsv(batch, path: Path) -> int:
    """把一批记录写成 MySQL LOAD DATA 认识的 TSV：\\t 分隔，NULL 写作 \\N。"""
    df = batch.to_pandas()
    for c in BOOL_COLS:
        df[c] = df[c].astype("boolean").astype("Int8")
    ts = df["reviewed_at"]
    if getattr(ts.dt, "tz", None) is not None:
        ts = ts.dt.tz_convert("UTC").dt.tz_localize(None)
    df["reviewed_at"] = ts.dt.strftime("%Y-%m-%d %H:%M:%S")
    # 语言是 Steam 的语言代码（english、schinese…），去掉可能破坏 TSV 的控制字符
    df["language"] = df["language"].astype("string").str.replace(r"[\t\r\n\\]", "", regex=True)
    df = df.sort_values("review_id")          # 按主键顺序写入，减少 B+ 树页分裂
    df.to_csv(path, sep="\t", header=False, index=False, na_rep="\\N", lineterminator="\n",
              encoding="utf-8")
    return len(df)


def load_shard(n: int, path: Path) -> dict:
    pf = pq.ParquetFile(path)
    stats = {"shard": n, "rows_in_file": pf.metadata.num_rows, "rows_loaded": 0}
    load_sql = (
        "LOAD DATA LOCAL INFILE %s IGNORE INTO TABLE ods_review_kaggle "
        "CHARACTER SET utf8mb4 FIELDS TERMINATED BY '\\t' ESCAPED BY '\\\\' "
        "LINES TERMINATED BY '\\n' "
        f"({', '.join(COLUMNS)}) SET src_shard = {int(n)}"
    )
    conn = connect_etl(settings.DB_ODS_NAME, local_infile=True)
    t0 = time.perf_counter()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM ods_review_kaggle WHERE src_shard = %s", (n,))
            conn.commit()
            with tempfile.TemporaryDirectory() as tmp:
                tsv = Path(tmp) / "batch.tsv"
                for i, batch in enumerate(pf.iter_batches(batch_size=BATCH_ROWS, columns=COLUMNS)):
                    rows = write_batch_tsv(batch, tsv)
                    cur.execute(load_sql, (tsv.as_posix(),))
                    conn.commit()
                    print(f"  shard {n} batch {i}: {rows:,} rows, {time.perf_counter() - t0:,.0f}s")
            cur.execute("SELECT COUNT(*) FROM ods_review_kaggle WHERE src_shard = %s", (n,))
            stats["rows_loaded"] = cur.fetchone()[0]
    finally:
        conn.close()
    stats["load_sec"] = round(time.perf_counter() - t0, 1)
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--shards", required=True, help="分片编号，如 0、0-12、0,3,5")
    ap.add_argument("--no-download", action="store_true", help="分片已在 data/raw/reviews 下")
    ap.add_argument("--delete-after", action="store_true", help="导入成功后删除分片文件")
    args = ap.parse_args()

    dest = settings.DATA_DIR / "reviews"
    for n in parse_shards(args.shards):
        with run_log("kaggle_reviews", dataset=DATASET, shard=n) as log:
            t0 = time.perf_counter()
            path = dest / shard_file(n) if args.no_download else download(n, dest)
            log["requests"] = 0 if args.no_download else 1
            log["download_sec"] = round(time.perf_counter() - t0, 1)
            stats = load_shard(n, path)
            log.update(stats)
            if args.delete_after:
                os.remove(path)
                log["deleted_file"] = True


if __name__ == "__main__":
    main()
