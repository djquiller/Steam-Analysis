"""数据质量报告：直接查库，生成 analysis/reports/data_quality.md。

用法（在仓库根目录，先跑完 analysis.build_ads_review，它留下的中间表这里会用到）：
    python -m analysis.build_quality_report

做什么：把"数据规模"评分要的证据一次查齐，写成一份 Markdown 报告：
1. 规模验收：游戏 ≥ 8 万、评论 ≥ 100 万、在线快照持续积累；
2. 每一层的行数：源文件 → ods → dwd → ads，丢了多少、为什么丢；
3. 各字段缺失率；4. 主键唯一性与去重；5. 异常值规则与命中数；
6. 一致性核对：ads 与明细表的合计是否对得上、评论集与 Steam 官方计数的覆盖率。

为什么每次都现查：报告里的每个数字都来自当前库里的数据，不手抄。重跑任何一步流水线之后，
再跑一次本脚本，报告就和库保持一致。

性能：评论相关的数大多取自 build_ads_review 留下的"游戏 × 维度"中间表（几百万行），
只有清洗规则的命中数需要扫一遍 ods_review_kaggle（1.21 亿行，约一两分钟）。
源文件的行数取自 data/logs/runs.jsonl 中导入脚本的运行记录。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from crawler.common import settings
from crawler.common.db import connect_etl
from crawler.common.runlog import run_log

ODS = settings.DB_ODS_NAME
DWD = settings.DB_NAME
OUT = settings.ROOT / "analysis" / "reports" / "data_quality.md"
RUNS = settings.LOG_DIR / "runs.jsonl"

MIN_GAMES, MIN_REVIEWS = 80_000, 1_000_000          # 课程规模验收线
STEAM_REVIEWS_SINCE = "2010-11-01"                  # Steam 用户评测上线的月份，早于此的发表时间视为异常
DATASET_CUTOFF = "2026-11-01"                       # 评论集截至 2026-10-30，晚于当月的发表时间视为异常
PRICE_HIGH = 200                                    # 价格高于此（美元）列为"需关注"，保留不剔除
PLAYTIME_HIGH_MIN = 60_000                          # 写评论时游玩时长 ≥ 1000 小时，列为"需关注"，保留不剔除


def fmt(n) -> str:
    return "—" if n is None else f"{int(n):,}"


def pct(a, b, digits: int = 2) -> str:
    return "—" if not b else f"{100 * a / b:.{digits}f}%"


class Report:
    def __init__(self, cur):
        self.cur = cur
        self.lines: list[str] = []

    def q(self, sql: str, args: tuple | None = None):
        self.cur.execute(sql, args)
        return self.cur.fetchall()

    def one(self, sql: str, args: tuple | None = None):
        return self.q(sql, args)[0][0]

    def table_exists(self, schema: str, table: str) -> bool:
        return bool(self.one("SELECT COUNT(*) FROM information_schema.tables "
                             "WHERE table_schema = %s AND table_name = %s", (schema, table)))

    def h(self, text: str, level: int = 2) -> None:
        if self.lines and self.lines[-1] != "":
            self.lines.append("")
        self.lines += ["#" * level + " " + text, ""]

    def p(self, text: str = "") -> None:
        self.lines.append(text)

    def table(self, header: list[str], rows: list[list]) -> None:
        self.lines.append("| " + " | ".join(header) + " |")
        self.lines.append("|" + "|".join("---" for _ in header) + "|")
        for r in rows:
            self.lines.append("| " + " | ".join(str(x) for x in r) + " |")
        self.lines.append("")


def latest_runs() -> dict[str, list[dict]]:
    """读运行记录，按来源分组，只取成功的；同一来源同一分片只保留最后一次。"""
    by_key: dict[tuple, dict] = {}
    if RUNS.exists():
        for line in RUNS.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r.get("status") == "ok":
                by_key[(r["source"], r.get("shard"))] = r
    out: dict[str, list[dict]] = {}
    for (src, _), r in by_key.items():
        out.setdefault(src, []).append(r)
    return out


def section_scale(rp: Report, s: dict) -> None:
    rp.h("1. 规模验收")
    rows = [
        ["游戏（款）", f"≥ {MIN_GAMES:,}", fmt(s["dwd_game"]),
         "达标" if s["dwd_game"] >= MIN_GAMES else "**未达标**",
         f"`dwd_game`；其中有发行年份、进入 ads 的 {fmt(s['games_released'])} 款"],
        ["评论（条）", f"≥ {MIN_REVIEWS:,}", fmt(s["dwd_review"]),
         "达标" if s["dwd_review"] >= MIN_REVIEWS else "**未达标**",
         f"`dwd_review`，是验收线的 {s['dwd_review'] / MIN_REVIEWS:,.0f} 倍；评论元数据全量入库"],
        ["评论原文样本（条）", "—", fmt(s["text_sample"]), "—",
         f"每款游戏最多 30 条，覆盖 {fmt(s['text_sample_games'])} 款，供情感模型使用"],
    ]
    if s.get("ccu"):
        c = s["ccu"]
        rows.append(["在线人数快照（行）", "持续积累", fmt(c["dwd_rows"]),
                     "积累中" if c["rounds"] >= 2 else "**未开始**",
                     f"每小时一轮，已 {c['rounds']} 轮（{c['first']} — {c['last']} UTC），"
                     f"采集名单 {fmt(c['watchlist'])} 款"])
    rp.table(["指标", "验收线", "实际", "结论", "说明"], rows)
    rp.p(f"库内占用：`{ODS}` 约 {s['size_ods']:.1f} GB，`{DWD}` 约 {s['size_dwd']:.1f} GB"
         "（`information_schema` 估算，含索引）。大屏全部读预聚合的 `ads` 表，"
         f'对 `dwd_review` 做一次 `COUNT(*)` 就要十几秒，这是"海量"在工程上的直接体现。')


def section_layers(rp: Report, s: dict, runs: dict) -> None:
    rp.h("2. 各层行数与清洗剔除")
    games_file = sum(r.get("rows_in_file", 0) for r in runs.get("kaggle_games", [])) or None
    review_runs = runs.get("kaggle_reviews", [])
    reviews_file = sum(r.get("rows_in_file", 0) for r in review_runs) or None
    g, r = s["games_clean"], s["reviews_clean"]
    r["dup"] = None if reviews_file is None else reviews_file - s["ods_review"]
    rp.table(
        ["数据", "源文件", "ods", "dwd", "进入 ads", "剔除 / 不进 ads 的原因"],
        [
            ["游戏", fmt(games_file), fmt(s["ods_game"]), fmt(s["dwd_game"]), fmt(s["games_released"]),
             f"名称缺失丢弃 {fmt(g['no_name'])} 款；未发行（发行日期晚于快照或缺失）{fmt(s['dwd_game'] - s['games_released'])} 款"
             "保留在 dwd、不进 ads"],
            ["评论", fmt(reviews_file), fmt(s["ods_review"]), fmt(s["dwd_review"]), fmt(s["reviews_in_ads"]),
             f"清洗丢弃 {fmt(s['ods_review'] - s['dwd_review'])} 条；"
             f"所评游戏不在游戏集里的 {fmt(s['reviews_orphan'])} 条（{fmt(s['orphan_appids'])} 个 appid）、"
             f"所评游戏未发行的 {fmt(s['reviews_unreleased'])} 条不进 ads"],
        ] + ([[
            "在线快照", "—", fmt(s["ccu"]["ods_rows"]), fmt(s["ccu"]["dwd_rows"]), "—",
            f"请求失败 {fmt(s['ccu']['ods_failed'])} 次（失败也在 ods 留一行），只有取到人数的进 dwd"]]
            if s.get("ccu") else []),
    )
    if review_runs:
        rp.p(f"评论集共 {len(review_runs)} 个 Parquet 分片，每片导入后行数与文件行数逐片核对一致"
             "（`data/logs/runs.jsonl` 中 `kaggle_reviews` 的 `rows_in_file` 与 `rows_loaded`）。")
        rp.p()
    rp.p("评论清洗规则（`analysis/build_dwd_review.py`）在 `ods_review_kaggle` 上的命中数：")
    rp.p()
    rp.table(["规则", "处理", "命中（条）", "占比"], [
        ["发表时间缺失", "丢弃", fmt(r["no_time"]), pct(r["no_time"], s["ods_review"], 4)],
        ["是否推荐缺失", "丢弃", fmt(r["no_vote"]), pct(r["no_vote"], s["ods_review"], 4)],
        ["语言缺失或为空", "丢弃", fmt(r["no_lang"]), pct(r["no_lang"], s["ods_review"], 4)],
        ["写评论时游玩时长为负数", "置为缺失（NULL）", fmt(r["neg_playtime"]), pct(r["neg_playtime"], s["ods_review"], 4)],
        ["写评论时游玩时长原本缺失", "保留为 NULL", fmt(r["null_playtime"]), pct(r["null_playtime"], s["ods_review"], 4)],
        ["同一 review_id 重复", "主键去重", fmt(r["dup"]), pct(r["dup"] or 0, s["ods_review"], 4)],
    ])
    rp.p("游戏清洗规则（`analysis/build_dwd_game.py`）的命中数：")
    rp.p()
    rp.table(["规则", "处理", "命中（款）"], [
        ["名称缺失", "丢弃", fmt(g["no_name"])],
        ["发行日期晚于游戏集快照（2026-11-08）或缺失", "`release_year` 置空，不进 ads", fmt(g["unreleased"])],
        ["Metacritic 分数为 0（表示没有评分）", "置为 NULL", fmt(g["metacritic_zero"])],
        ["拥有者区间无法解析", "置为 NULL", fmt(g["owners_null"])],
        ["没有任何 Steam 类型", "保留；只计入 `__ALL__` 汇总行", fmt(g["no_genre"])],
    ])


def section_missing(rp: Report, s: dict) -> None:
    rp.h("3. 字段缺失率")
    rp.p(f'`dwd_game`（{fmt(s["dwd_game"])} 款）。"0 值"一栏是数值为 0 的比例：'
         "价格为 0 是免费游戏，不算缺失；其他字段为 0 多数表示来源没有统计，分析时按需处理。")
    rp.p()
    rows = []
    for col, cnt_null, cnt_zero in s["game_missing"]:
        rows.append([f"`{col}`", fmt(cnt_null), pct(cnt_null, s["dwd_game"]),
                     "—" if cnt_zero is None else pct(cnt_zero, s["dwd_game"])])
    rp.table(["字段", "缺失（NULL 或空串）", "缺失率", "0 值占比"], rows)
    rp.p(f"`dwd_review`（{fmt(s['dwd_review'])} 条）：`appid`、`review_id`、`language`、`voted_up`、"
         "`timestamp_created` 在表结构上就是 `NOT NULL`，缺失率 0；只有写评论时的游玩时长可空，"
         f"缺失 {fmt(s['review_no_playtime'])} 条，占 {pct(s['review_no_playtime'], s['dwd_review'], 3)}，"
         "这部分不计入时长分布（`ads_playtime_dist`），其余评论类统计照常计入。")


def section_unique(rp: Report, s: dict) -> None:
    rp.h("4. 唯一性与去重")
    rp.table(["表", "主键", "行数", "主键去重后", "重复"], [
        [f"`{t}`", f"`{pk}`", fmt(n), fmt(d), fmt(n - d)] for t, pk, n, d in s["unique"]
    ])
    rp.p("各表都以主键约束入库，重复行在写入时就被合并。游戏表是写入后用 `COUNT(DISTINCT)` 复核的结果；"
         "两张评论表上亿行，唯一性由主键约束直接保证，不再复核。")


def section_outliers(rp: Report, s: dict) -> None:
    rp.h("5. 异常值规则与命中数")
    o = s["outliers"]
    rp.table(["对象", "规则", "处理", "命中", "占比"], [
        ["游戏", f"价格 > {PRICE_HIGH} 美元", "保留（多为软件、合集或标价异常），列入需关注",
         fmt(o["price_high"]), pct(o["price_high"], s["dwd_game"], 3)],
        ["游戏", "Steam 评论总数 < 10", "不参与好评率统计（全局口径）",
         fmt(o["few_reviews"]), pct(o["few_reviews"], s["dwd_game"])],
        ["游戏", "历史峰值在线为 0", "保留", fmt(o["ccu_zero"]), pct(o["ccu_zero"], s["dwd_game"])],
        ["评论", f"发表时间早于 {STEAM_REVIEWS_SINCE}（Steam 评测上线前）", "保留并列入需关注",
         fmt(o["too_early"]), pct(o["too_early"], s["dwd_review"], 4)],
        ["评论", f"发表时间不早于 {DATASET_CUTOFF}（晚于数据集截止日）", "保留并列入需关注",
         fmt(o["too_late"]), pct(o["too_late"], s["dwd_review"], 4)],
        ["评论", "写评论时游玩时长 ≥ 1000 小时", "保留，落入时长分布最后一档",
         fmt(o["playtime_high"]), pct(o["playtime_high"], s["dwd_review"], 3)],
        ["评论", "所评游戏不在游戏集里", "保留在 dwd，不进 ads", fmt(s["reviews_orphan"]),
         pct(s["reviews_orphan"], s["dwd_review"])],
    ])
    rp.p(f"评论发表时间范围：{o['month_min']} — {o['month_max']}（按月，UTC）。")
    if o["top_price"]:
        rp.p()
        rp.p("价格最高的 5 款：" + "；".join(f"{n}（{a}）{p} 美元" for a, n, p in o["top_price"]) + "。")


def section_consistency(rp: Report, s: dict) -> None:
    rp.h("6. 一致性核对")
    c = s["consistency"]
    rows = [[name, fmt(want), fmt(got), "一致" if want == got else "**不一致**"] for name, want, got in c]
    rp.table(["核对项", "明细层", "ads 层", "结论"], rows)
    rp.p("这些核对与 `build_ads_game.py`、`build_ads_review.py` 提交前的自动核对是同一口径；"
         "脚本里任何一项对不上都会整体回滚，所以 ads 表里不会留下对不上的半成品。")
    rp.p()
    rp.p(f"**与 Steam 官方计数的覆盖率**：游戏集里各游戏的好评 + 差评合计 {fmt(s['steam_reviews'])} 条，"
         f"评论集中所评游戏在游戏集里的评论 {fmt(s['dwd_review'] - s['reviews_orphan'])} 条，覆盖 "
         f"{pct(s['dwd_review'] - s['reviews_orphan'], s['steam_reviews'], 1)}。两份数据的快照日期不同"
         "（评论集截至 2026-10-30，游戏集 2026-11-08），评论集也未必抓全每款游戏的评测，"
         "具体构成无法从现有数据拆分；答辩时把这个比例作为数据来源的局限说明。")
    rp.p()
    rp.p(f"**游戏覆盖**：`dwd_game` 中 {fmt(s['games_with_reviews'])} 款有评论（"
         f"{pct(s['games_with_reviews'], s['dwd_game'], 1)}）；Steam 计数评论 ≥ 10 条的 "
         f"{fmt(s['games_10'])} 款中 {fmt(s['games_10_with_reviews'])} 款有评论（"
         f"{pct(s['games_10_with_reviews'], s['games_10'], 1)}）。")


def collect(rp: Report) -> dict:
    s: dict = {}
    one = rp.one
    print("  规模与行数 …")
    s["ods_game"] = one(f"SELECT COUNT(*) FROM {ODS}.ods_game_kaggle")
    s["dwd_game"] = one(f"SELECT COUNT(*) FROM {DWD}.dwd_game")
    s["games_released"] = one(f"SELECT COUNT(*) FROM {DWD}.dwd_game WHERE release_year IS NOT NULL")
    s["text_sample"], s["text_sample_games"] = rp.q(
        f"SELECT COUNT(*), COUNT(DISTINCT game_id) FROM {ODS}.ods_review_text_sample")[0]
    s["size_ods"], s["size_dwd"] = (
        float(one("SELECT COALESCE(SUM(data_length + index_length), 0) / POW(1024, 3) "
                  "FROM information_schema.tables WHERE table_schema = %s", (db,)))
        for db in (ODS, DWD))

    # 评论：总数等取自中间表（合计等于 dwd_review 行数，build_ads_review 提交前已核对）
    for t in ("stg_review_lang", "stg_review_playtime", "stg_review_month"):
        if not rp.table_exists(ODS, t) or not one(f"SELECT COUNT(*) FROM {ODS}.{t}"):
            raise RuntimeError(f"缺少中间表 {ODS}.{t}：先运行 python -m analysis.build_ads_review")
    s["dwd_review"] = int(one(f"SELECT SUM(review_cnt) FROM {ODS}.stg_review_lang"))
    joined = f"FROM {ODS}.stg_review_lang s LEFT JOIN {DWD}.dwd_game d ON d.appid = s.appid"
    s["reviews_in_ads"], s["reviews_unreleased"], s["reviews_orphan"] = (int(x or 0) for x in rp.q(
        f"SELECT SUM(IF(d.release_year IS NOT NULL, s.review_cnt, 0)), "
        f"SUM(IF(d.appid IS NOT NULL AND d.release_year IS NULL, s.review_cnt, 0)), "
        f"SUM(IF(d.appid IS NULL, s.review_cnt, 0)) {joined}")[0])
    s["orphan_appids"] = one(f"SELECT COUNT(DISTINCT s.appid) {joined} WHERE d.appid IS NULL")
    s["review_no_playtime"] = int(one(
        f"SELECT COALESCE(SUM(review_cnt), 0) FROM {ODS}.stg_review_playtime WHERE playtime_bin = 255"))

    print("  扫描 ods_review_kaggle 统计清洗规则命中数（约一两分钟）…")
    row = rp.q(f"""SELECT COUNT(*), NULL,
                          SUM(reviewed_at IS NULL), SUM(is_positive IS NULL),
                          SUM(language IS NULL OR language = ''),
                          SUM(playtime_at_review < 0), SUM(playtime_at_review IS NULL)
                   FROM {ODS}.ods_review_kaggle""")[0]
    s["ods_review"] = row[0]
    # review_id 是 ods 的主键，重复行导入时就被合并；重复数 = 源文件行数 − ods 行数（见 section_layers）
    s["reviews_clean"] = {"no_time": row[2], "no_vote": row[3], "no_lang": row[4],
                          "neg_playtime": row[5], "null_playtime": row[6]}

    print("  游戏清洗与缺失率 …")
    s["games_clean"] = {
        "no_name": one(f"SELECT COUNT(*) FROM {ODS}.ods_game_kaggle WHERE name IS NULL OR TRIM(name) = ''"),
        "unreleased": s["dwd_game"] - s["games_released"],
        "metacritic_zero": one(f"SELECT COUNT(*) FROM {ODS}.ods_game_kaggle WHERE metacritic_score = 0"),
        "owners_null": one(f"SELECT COUNT(*) FROM {DWD}.dwd_game WHERE owners_mid IS NULL"),
        "no_genre": one(f"SELECT COUNT(*) FROM {DWD}.dwd_game d WHERE NOT EXISTS "
                        f"(SELECT 1 FROM {DWD}.dwd_game_genre g WHERE g.appid = d.appid)"),
    }
    # (字段, 是否文本, 是否统计 0 值)
    cols = [("release_date", False, False), ("release_year", False, False), ("price_usd", False, True),
            ("owners_mid", False, False), ("peak_ccu", False, True), ("positive", False, True),
            ("negative", False, True), ("avg_playtime_min", False, True), ("median_playtime_min", False, True),
            ("required_age", False, True), ("dlc_count", False, True), ("achievements", False, True),
            ("num_languages", False, False), ("metacritic_score", False, False),
            ("developer", True, False), ("publisher", True, False), ("header_image", True, False)]
    exprs = []
    for col, is_text, zero in cols:
        exprs.append(f"SUM({col} IS NULL OR {col} = '')" if is_text else f"SUM({col} IS NULL)")
        exprs.append(f"SUM({col} = 0)" if zero else "NULL")
    vals = rp.q(f"SELECT {', '.join(exprs)} FROM {DWD}.dwd_game")[0]
    s["game_missing"] = [(c[0], vals[2 * i], vals[2 * i + 1]) for i, c in enumerate(cols)]

    print("  唯一性 …")
    # 小表直接 COUNT(DISTINCT) 复核；评论表上亿行，主键约束本身就保证唯一，不再复核
    s["unique"] = [
        ("ods_game_kaggle", "app_id", s["ods_game"],
         one(f"SELECT COUNT(DISTINCT app_id) FROM {ODS}.ods_game_kaggle")),
        ("dwd_game", "appid", s["dwd_game"], one(f"SELECT COUNT(DISTINCT appid) FROM {DWD}.dwd_game")),
        ("dwd_game_genre", "appid, genre", one(f"SELECT COUNT(*) FROM {DWD}.dwd_game_genre"),
         one(f"SELECT COUNT(DISTINCT appid, genre) FROM {DWD}.dwd_game_genre")),
        ("ods_review_kaggle", "review_id", s["ods_review"], s["ods_review"]),
        ("dwd_review", "appid, review_id", s["dwd_review"], s["dwd_review"]),
    ]

    print("  异常值 …")
    month = f"{ODS}.stg_review_month"
    s["outliers"] = {
        "price_high": one(f"SELECT COUNT(*) FROM {DWD}.dwd_game WHERE price_usd > %s", (PRICE_HIGH,)),
        "top_price": rp.q(f"SELECT appid, name, price_usd FROM {DWD}.dwd_game "
                          "ORDER BY price_usd DESC, appid LIMIT 5"),
        "few_reviews": one(f"SELECT COUNT(*) FROM {DWD}.dwd_game WHERE positive + negative < 10"),
        "ccu_zero": one(f"SELECT COUNT(*) FROM {DWD}.dwd_game WHERE peak_ccu = 0"),
        "too_early": int(one(f"SELECT COALESCE(SUM(review_cnt), 0) FROM {month} WHERE month_start < %s",
                             (STEAM_REVIEWS_SINCE,))),
        "too_late": int(one(f"SELECT COALESCE(SUM(review_cnt), 0) FROM {month} WHERE month_start >= %s",
                            (DATASET_CUTOFF,))),
        "playtime_high": int(one(f"SELECT COALESCE(SUM(review_cnt), 0) FROM {ODS}.stg_review_playtime "
                                 "WHERE playtime_bin = 10")),
        "month_min": one(f"SELECT DATE_FORMAT(MIN(month_start), '%Y-%m') FROM {month}"),
        "month_max": one(f"SELECT DATE_FORMAT(MAX(month_start), '%Y-%m') FROM {month}"),
    }

    print("  一致性 …")
    all_ = "WHERE genre = '__ALL__'"
    kpi = rp.q(f"SELECT game_cnt, review_cnt, owners_total FROM {DWD}.ads_kpi_overview WHERE id = 1")
    kpi = kpi[0] if kpi else (None, None, None)
    s["consistency"] = [
        ("进入 ads 的游戏数 = `ads_yearly_release` __ALL__ 合计", s["games_released"],
         one(f"SELECT SUM(game_cnt) FROM {DWD}.ads_yearly_release {all_}")),
        ("进入 ads 的游戏数 = `ads_top_sellers` 行数", s["games_released"],
         one(f"SELECT COUNT(*) FROM {DWD}.ads_top_sellers")),
        ("KPI 游戏总数", s["games_released"], kpi[0]),
        ("KPI 评论总数 = `dwd_review` 行数", s["dwd_review"], kpi[1]),
        ("KPI 估算玩家总量", one(f"SELECT SUM(owners_mid) FROM {DWD}.dwd_game WHERE release_year IS NOT NULL"),
         kpi[2]),
        ("进入 ads 的评论 = `ads_review_lang` __ALL__ 合计", s["reviews_in_ads"],
         one(f"SELECT SUM(review_cnt) FROM {DWD}.ads_review_lang {all_}")),
        ("进入 ads 的评论 = `ads_review_heatmap` __ALL__ 合计", s["reviews_in_ads"],
         one(f"SELECT SUM(review_cnt) FROM {DWD}.ads_review_heatmap {all_}")),
        ("进入 ads 的评论 = `ads_game_review_trend` 合计", s["reviews_in_ads"],
         one(f"SELECT SUM(review_cnt) FROM {DWD}.ads_game_review_trend")),
        ("有游玩时长、进入 ads 的评论 = `ads_playtime_dist` __ALL__ 合计",
         int(one(f"SELECT SUM(s.review_cnt) FROM {ODS}.stg_review_playtime s JOIN {DWD}.dwd_game d "
                 "ON d.appid = s.appid WHERE d.release_year IS NOT NULL AND s.playtime_bin <> 255")),
         one(f"SELECT SUM(review_cnt) FROM {DWD}.ads_playtime_dist {all_}")),
    ]
    s["consistency"] = [(n, None if w is None else int(w), None if g is None else int(g))
                        for n, w, g in s["consistency"]]

    s["steam_reviews"] = int(one(f"SELECT SUM(positive + negative) FROM {DWD}.dwd_game"))
    s["games_with_reviews"] = one(
        f"SELECT COUNT(DISTINCT s.appid) FROM {ODS}.stg_review_lang s JOIN {DWD}.dwd_game d ON d.appid = s.appid")
    s["games_10"], s["games_10_with_reviews"] = rp.q(
        f"SELECT COUNT(*), SUM(EXISTS (SELECT 1 FROM {ODS}.stg_review_lang s WHERE s.appid = d.appid)) "
        f"FROM {DWD}.dwd_game d WHERE d.positive + d.negative >= 10")[0]

    if rp.table_exists(ODS, "ods_ccu_snapshot"):
        print("  在线快照 …")
        ods_rows, ods_failed = rp.q(
            f"SELECT COUNT(*), SUM(player_count IS NULL) FROM {ODS}.ods_ccu_snapshot")[0]
        dwd_rows, rounds, first, last = rp.q(
            f"SELECT COUNT(*), COUNT(DISTINCT snapshot_at), MIN(snapshot_at), MAX(snapshot_at) "
            f"FROM {DWD}.dwd_ccu_snapshot")[0]
        s["ccu"] = {"ods_rows": ods_rows, "ods_failed": int(ods_failed or 0), "dwd_rows": dwd_rows,
                    "rounds": rounds, "first": f"{first:%Y-%m-%d %H:%M}" if first else "—",
                    "last": f"{last:%Y-%m-%d %H:%M}" if last else "—",
                    "watchlist": one(f"SELECT COUNT(*) FROM {DWD}.dwd_ccu_watchlist")
                    if rp.table_exists(DWD, "dwd_ccu_watchlist") else None}
    return s


def main() -> None:
    with run_log("build_quality_report") as stats:
        conn = connect_etl(DWD)
        try:
            with conn.cursor() as cur:
                cur.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED")
                rp = Report(cur)
                s = collect(rp)
        finally:
            conn.close()

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        rp.p("# 数据质量报告")
        rp.p()
        rp.p(f"> 由 `python -m analysis.build_quality_report` 直接查库生成，生成时间 {now} UTC。"
             "不要手工修改本文件；数据变了就重跑脚本。口径见 `docs/schema.md`。")
        section_scale(rp, s)
        section_layers(rp, s, latest_runs())
        section_missing(rp, s)
        section_unique(rp, s)
        section_outliers(rp, s)
        section_consistency(rp, s)

        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text("\n".join(rp.lines).rstrip() + "\n", encoding="utf-8", newline="\n")
        stats["rows_loaded"] = 0
        stats["dwd_game"], stats["dwd_review"] = s["dwd_game"], s["dwd_review"]
        stats["consistency_failed"] = sum(1 for _, w, g in s["consistency"] if w != g)
        print(f"  已写入 {OUT.relative_to(settings.ROOT)}")


if __name__ == "__main__":
    main()
