"""游戏清洗：steam_ods.ods_game_kaggle → steam.dwd_game + steam.dwd_game_genre。

用法（在仓库根目录）：
    python -m analysis.build_dwd_game

做什么：把原始字符串字段转成统一口径（docs/schema.md "全局口径"），类型拆成多行。
为什么全量重建：游戏表只有十几万行，几秒内能重算完，比增量更新简单、不会留脏数据。
每一步剔除/置空了多少行都写进运行记录，供《数据质量报告》引用。

清洗规则：
- 名称缺失的游戏丢弃；
- 发行日期按 "Aug 1, 2023" 解析；晚于数据集快照日期的视为未发行，release_year 置空（不进 ads）；
- 价格区间：0 → free，(0,10) → lt10，[10,30) → 10_30，[30,60) → 30_60，≥60 → ge60；
- 拥有者 "20000 - 50000" 拆成上下限并取中值；
- Metacritic 分数为 0 表示没有评分，置空；
- 支持语言数由语言列表的长度得出；开发商、发行商取第一个；
- 类型按逗号拆行，去掉首尾空格。
"""
from __future__ import annotations

import ast
from datetime import date

import pandas as pd

from crawler.common import settings
from crawler.common.db import connect_etl
from crawler.common.runlog import run_log

SNAPSHOT_DATE = date(2026, 11, 8)   # 游戏集 games.csv 的版本日期
BATCH = 2000

ODS_COLS = ["app_id", "name", "release_date", "estimated_owners", "peak_ccu", "required_age", "price",
            "dlc_count", "supported_languages", "header_image", "windows", "mac", "linux",
            "metacritic_score", "positive", "negative", "achievements",
            "average_playtime_forever", "median_playtime_forever", "developers", "publishers", "genres"]

DWD_COLS = ["appid", "name", "release_date", "release_year", "price_usd", "price_bucket",
            "owners_low", "owners_high", "owners_mid", "peak_ccu", "positive", "negative",
            "avg_playtime_min", "median_playtime_min", "required_age", "dlc_count", "achievements",
            "num_languages", "on_windows", "on_mac", "on_linux", "metacritic_score",
            "developer", "publisher", "header_image"]


def price_bucket(p: float) -> str:
    if p <= 0:
        return "free"
    if p < 10:
        return "lt10"
    if p < 30:
        return "10_30"
    if p < 60:
        return "30_60"
    return "ge60"


def count_languages(s) -> int | None:
    if not isinstance(s, str) or not s.strip():
        return None
    try:
        return len(ast.literal_eval(s))   # 原始格式是 Python 列表字面量，如 "['English', 'French']"
    except (ValueError, SyntaxError):
        return None


def first_item(s) -> str | None:
    if not isinstance(s, str) or not s.strip():
        return None
    return s.split(",")[0].strip()[:255] or None


def clean(ods: pd.DataFrame, stats: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    stats["rows_in_ods"] = len(ods)
    ods = ods[ods["name"].notna() & (ods["name"].str.strip() != "")].copy()
    stats["dropped_no_name"] = stats["rows_in_ods"] - len(ods)

    d = pd.DataFrame({"appid": ods["app_id"], "name": ods["name"].str.strip()})
    rd = pd.to_datetime(ods["release_date"], format="%b %d, %Y", errors="coerce")
    d["release_date"] = rd.dt.date
    unreleased = rd.dt.date > SNAPSHOT_DATE
    d["release_year"] = rd.dt.year.where(rd.notna() & ~unreleased).astype("Int64")
    stats["release_date_unparsed"] = int(rd.isna().sum())
    stats["unreleased"] = int(unreleased.sum())

    d["price_usd"] = ods["price"].fillna(0).astype(float).round(2)
    d["price_bucket"] = d["price_usd"].map(price_bucket)

    owners = ods["estimated_owners"].str.extract(r"(\d+)\s*-\s*(\d+)").astype("Int64")
    d["owners_low"], d["owners_high"] = owners[0], owners[1]
    d["owners_mid"] = ((owners[0] + owners[1]) // 2).astype("Int64")
    stats["owners_unparsed"] = int(owners[0].isna().sum())

    d["peak_ccu"] = ods["peak_ccu"]
    d["positive"] = ods["positive"].fillna(0)
    d["negative"] = ods["negative"].fillna(0)
    d["avg_playtime_min"] = ods["average_playtime_forever"]
    d["median_playtime_min"] = ods["median_playtime_forever"]
    d["required_age"] = ods["required_age"].clip(lower=0, upper=255)
    d["dlc_count"] = ods["dlc_count"]
    d["achievements"] = ods["achievements"]
    d["num_languages"] = ods["supported_languages"].map(count_languages).astype("Int64")
    d["on_windows"], d["on_mac"], d["on_linux"] = ods["windows"], ods["mac"], ods["linux"]
    d["metacritic_score"] = ods["metacritic_score"].where(ods["metacritic_score"] > 0)
    stats["metacritic_missing"] = int(d["metacritic_score"].isna().sum())
    d["developer"] = ods["developers"].map(first_item)
    d["publisher"] = ods["publishers"].map(first_item)
    d["header_image"] = ods["header_image"]

    g = ods[["app_id", "genres"]].dropna()
    g = g.assign(genre=g["genres"].str.split(",")).explode("genre")
    g["genre"] = g["genre"].str.strip().str[:64]
    g = g[g["genre"] != ""].drop_duplicates(["app_id", "genre"])
    genres = g.rename(columns={"app_id": "appid"})[["appid", "genre"]]
    stats["games_without_genre"] = int(len(d) - genres["appid"].nunique())
    stats["genre_rows"] = len(genres)
    stats["distinct_genres"] = int(genres["genre"].nunique())
    stats["rows_in_dwd"] = len(d)
    return d[DWD_COLS], genres


def to_rows(df: pd.DataFrame) -> list[list]:
    return df.astype(object).where(df.notna(), None).values.tolist()


def main() -> None:
    with run_log("build_dwd_game") as stats:
        conn = connect_etl(settings.DB_NAME)
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT {', '.join(ODS_COLS)} FROM {settings.DB_ODS_NAME}.ods_game_kaggle")
                ods = pd.DataFrame(cur.fetchall(), columns=ODS_COLS)
                for c in ["peak_ccu", "required_age", "dlc_count", "metacritic_score", "positive", "negative",
                          "achievements", "average_playtime_forever", "median_playtime_forever",
                          "windows", "mac", "linux"]:
                    ods[c] = pd.to_numeric(ods[c]).astype("Int64")
                game, genre = clean(ods, stats)

                # 全量重建：先清空再写入，放在一个事务里，失败则整体回滚
                cur.execute("DELETE FROM dwd_game_genre")
                cur.execute("DELETE FROM dwd_game")
                sql = (f"INSERT INTO dwd_game ({', '.join(DWD_COLS)}) "
                       f"VALUES ({', '.join(['%s'] * len(DWD_COLS))})")
                rows = to_rows(game)
                for i in range(0, len(rows), BATCH):
                    cur.executemany(sql, rows[i:i + BATCH])
                rows = to_rows(genre)
                for i in range(0, len(rows), BATCH):
                    cur.executemany("INSERT INTO dwd_game_genre (appid, genre) VALUES (%s, %s)", rows[i:i + BATCH])
                conn.commit()
                stats["rows_loaded"] = len(game)
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()


if __name__ == "__main__":
    main()
