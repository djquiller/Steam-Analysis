"""把 Kaggle 游戏集 games.csv 原样导入 steam_ods.ods_game_kaggle。

用法（在仓库根目录）：
    python -m crawler.kaggle_games                     # 先下载再导入
    python -m crawler.kaggle_games --csv data/raw/games/games.csv   # 用已下载的文件

为什么要修表头：源文件表头把 "Discount" 和 "DLC count" 粘成了一个 "DiscountDLC count"，
表头 39 列、数据 40 列，直接读取会整体错位一列（AppID 变成行索引）。这里拆回两列。
可重跑：按 app_id 主键 INSERT … ON DUPLICATE KEY UPDATE。
"""
from __future__ import annotations

import argparse
import csv
import re
import subprocess
from pathlib import Path

import pandas as pd

from .common import settings
from .common.db import connect_etl
from .common.runlog import run_log

DATASET = "fronkongames/steam-games-dataset"
FILE = "games.csv"
BATCH = 1000

# 表头修正：粘在一起的列名 → 拆开后的列名
MERGED_HEADERS = {"DiscountDLC count": ["Discount", "DLC count"]}
# 和 snake_case 规则不一致的列名
RENAME = {"appid": "app_id"}


def download(dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["kaggle", "datasets", "download", DATASET, "-f", FILE, "-p", str(dest_dir)], check=True)
    return dest_dir / FILE


def to_snake(name: str) -> str:
    s = re.sub(r"[^0-9a-zA-Z]+", "_", name.strip()).strip("_").lower()
    return RENAME.get(s, s)


def read_games_csv(path: Path) -> pd.DataFrame:
    with open(path, encoding="utf-8", newline="") as f:
        header = next(csv.reader(f))
    names: list[str] = []
    for h in header:
        names.extend(MERGED_HEADERS.get(h, [h]))
    df = pd.read_csv(path, encoding="utf-8", header=0, names=names, index_col=False,
                     dtype=str, keep_default_na=False, na_values=[""])
    df.columns = [to_snake(c) for c in df.columns]
    return df


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """只做落库需要的最小类型转换，不做业务清洗（清洗在 analysis/）。"""
    int_cols = ["app_id", "peak_ccu", "required_age", "discount", "dlc_count", "metacritic_score",
                "user_score", "positive", "negative", "achievements", "recommendations",
                "average_playtime_forever", "average_playtime_two_weeks",
                "median_playtime_forever", "median_playtime_two_weeks"]
    for c in int_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce").round().astype("Int64")
    df["price"] = pd.to_numeric(df["price"], errors="coerce").round(2)
    for c in ["windows", "mac", "linux"]:
        df[c] = df[c].map({"True": 1, "False": 0}).astype("Int64")
    return df


def load(df: pd.DataFrame) -> int:
    cols = list(df.columns)
    placeholders = ", ".join(["%s"] * len(cols))
    updates = ", ".join(f"{c} = VALUES({c})" for c in cols if c != "app_id")
    sql = (f"INSERT INTO ods_game_kaggle ({', '.join(cols)}) VALUES ({placeholders}) "
           f"ON DUPLICATE KEY UPDATE {updates}, loaded_at = CURRENT_TIMESTAMP")
    rows = df.astype(object).where(df.notna(), None).values.tolist()
    conn = connect_etl(settings.DB_ODS_NAME)
    try:
        with conn.cursor() as cur:
            for i in range(0, len(rows), BATCH):
                cur.executemany(sql, rows[i:i + BATCH])
            conn.commit()
            cur.execute("SELECT COUNT(*) FROM ods_game_kaggle")
            return cur.fetchone()[0]
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--csv", type=Path, help="已下载的 games.csv；不给则先从 Kaggle 下载")
    args = ap.parse_args()
    with run_log("kaggle_games", dataset=DATASET) as log:
        path = args.csv or download(settings.DATA_DIR / "games")
        log["requests"] = 0 if args.csv else 1
        df = normalize(read_games_csv(path))
        log["rows_in_file"] = len(df)
        log["rows_loaded"] = load(df)


if __name__ == "__main__":
    main()
