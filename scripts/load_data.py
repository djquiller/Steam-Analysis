"""一键导入流水线：游戏集 + 评论集 13 个分片，可中断、可重跑。

用法（在仓库根目录）：
    python scripts/load_data.py                    # 全部：游戏集 + 评论分片 0-12
    python scripts/load_data.py --reviews 1-12     # 只处理指定分片
    python scripts/load_data.py --status           # 只查看进度，不做任何导入
    python scripts/load_data.py --keep-files       # 处理完不删除分片文件

每个分片依次执行三步，每步完成后在 steam_ods.etl_progress 记一行：
    ods_review   下载分片 → 导入 ods_review_kaggle（crawler/kaggle_reviews.py）
    text_sample  每款游戏抽最多 k 条原文 → ods_review_text_sample（crawler/kaggle_review_text.py）
    dwd_review   清洗到 dwd_review（analysis/build_dwd_review.py）
三步都完成后删除分片文件，释放约 2 GB 磁盘。
中断（关掉窗口、断网、重启）后再运行同一条命令即可：已完成的步骤会跳过，
没完成的步骤会先删掉该分片的半成品再重做，不会产生重复数据。
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# 允许直接 `python scripts/load_data.py` 运行：把仓库根目录加入模块搜索路径
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from crawler import kaggle_games, kaggle_review_text, kaggle_reviews  # noqa: E402
from crawler.common import settings  # noqa: E402
from crawler.common.db import connect_etl  # noqa: E402
from crawler.common.runlog import run_log  # noqa: E402
from analysis import build_dwd_game, build_dwd_review  # noqa: E402

SHARD_STEPS = ["ods_review", "text_sample", "dwd_review"]
GAME_STEPS = ["ods_game", "dwd_game"]
NO_SHARD = -1


# ---------------- 进度表 ----------------
def done_steps() -> set[tuple[str, int]]:
    conn = connect_etl(settings.DB_ODS_NAME)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT step, shard FROM etl_progress")
            return {(s, int(n)) for s, n in cur.fetchall()}
    finally:
        conn.close()


def mark_done(step: str, shard: int, rows: int, sec: float) -> None:
    conn = connect_etl(settings.DB_ODS_NAME)
    try:
        with conn.cursor() as cur:
            cur.execute("REPLACE INTO etl_progress (step, shard, rows_done, elapsed_sec) VALUES (%s, %s, %s, %s)",
                        (step, shard, rows, round(sec, 1)))
        conn.commit()
    finally:
        conn.close()


def print_status() -> None:
    conn = connect_etl(settings.DB_ODS_NAME)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT step, shard, rows_done, elapsed_sec, finished_at FROM etl_progress ORDER BY shard, step")
            rows = cur.fetchall()
    finally:
        conn.close()
    print(f"{'步骤':<12}{'分片':>5}{'行数':>14}{'耗时(秒)':>10}  完成时间(本地)")
    for step, shard, n, sec, at in rows:
        print(f"{step:<12}{('-' if shard == NO_SHARD else shard):>5}{(n or 0):>14,}{float(sec or 0):>10.1f}  {at}")
    finished = {s for s in range(13) if all((st, s) in {(r[0], r[1]) for r in rows} for st in SHARD_STEPS)}
    print(f"\n评论分片已完成 {len(finished)}/13：{sorted(finished)}")


# ---------------- 各步骤 ----------------
def run_step(step: str, shard: int, fn) -> None:
    t0 = time.perf_counter()
    print(f"\n=== {step} shard={shard if shard != NO_SHARD else '-'} ===", flush=True)
    rows = fn()
    mark_done(step, shard, rows, time.perf_counter() - t0)


def games(done: set) -> None:
    if ("ods_game", NO_SHARD) not in done:
        def ods_game() -> int:
            with run_log("kaggle_games", dataset=kaggle_games.DATASET) as log:
                path = settings.DATA_DIR / "games" / kaggle_games.FILE
                if not path.exists():
                    path = kaggle_games.download(path.parent)
                    log["requests"] = 1
                df = kaggle_games.normalize(kaggle_games.read_games_csv(path))
                log["rows_in_file"] = len(df)
                log["rows_loaded"] = kaggle_games.load(df)
                return log["rows_loaded"]
        run_step("ods_game", NO_SHARD, ods_game)
    if ("dwd_game", NO_SHARD) not in done:
        def dwd_game() -> int:
            build_dwd_game.main()
            conn = connect_etl(settings.DB_NAME)
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM dwd_game")
                    return cur.fetchone()[0]
            finally:
                conn.close()
        run_step("dwd_game", NO_SHARD, dwd_game)


def review_shard(n: int, done: set, keep_files: bool) -> None:
    todo = [s for s in SHARD_STEPS if (s, n) not in done]
    path = settings.DATA_DIR / "reviews" / kaggle_reviews.shard_file(n)
    if not todo:
        print(f"分片 {n}：已完成，跳过", flush=True)
        if path.exists() and not keep_files:
            os.remove(path)
        return
    needs_file = "ods_review" in todo or "text_sample" in todo
    if needs_file and not path.exists():
        print(f"\n=== 下载分片 {n} ===", flush=True)
        kaggle_reviews.download(n, path.parent)

    if "ods_review" in todo:
        def ods() -> int:
            with run_log("kaggle_reviews", dataset=kaggle_reviews.DATASET, shard=n) as log:
                log.update(kaggle_reviews.load_shard(n, path))
                return log["rows_loaded"]
        run_step("ods_review", n, ods)

    if "text_sample" in todo:
        def text() -> int:
            with run_log("kaggle_review_text", shard=n) as log:
                log.update(kaggle_review_text.sample_shard(n, path))
                return log["rows_loaded"]
        run_step("text_sample", n, text)

    if "dwd_review" in todo:
        def dwd() -> int:
            conn = connect_etl(settings.DB_NAME)
            try:
                with conn.cursor() as cur, run_log("build_dwd_review", shard=n) as log:
                    log.update(build_dwd_review.build_shard(cur, conn, n))
                    log["rows_loaded"] = log.get("rows_in_dwd", 0)
                    return log["rows_loaded"]
            finally:
                conn.close()
        run_step("dwd_review", n, dwd)

    if not keep_files and path.exists():
        os.remove(path)
        print(f"分片 {n}：已删除文件 {path.name}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--reviews", default="0-12", help="要处理的评论分片，如 0-12、3、1,5,7")
    ap.add_argument("--skip-games", action="store_true", help="不处理游戏集")
    ap.add_argument("--keep-files", action="store_true", help="处理完不删除分片文件")
    ap.add_argument("--status", action="store_true", help="只显示进度")
    args = ap.parse_args()

    if args.status:
        print_status()
        return
    t0 = time.perf_counter()
    if not args.skip_games:
        games(done_steps())
    for n in kaggle_reviews.parse_shards(args.reviews):
        review_shard(n, done_steps(), args.keep_files)
    print(f"\n全部完成，用时 {(time.perf_counter() - t0) / 60:.1f} 分钟。")
    print_status()


if __name__ == "__main__":
    main()
