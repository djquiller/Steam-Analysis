"""采一轮在线人数快照：名单里每款游戏调一次 GetNumberOfCurrentPlayers。

流程：读名单（steam.dwd_ccu_watchlist）→ 逐款请求 → 每款的原始结果（含失败）写
steam_ods.ods_ccu_snapshot → 其中取到人数的写 steam.dwd_ccu_snapshot。

几条设计：
  - snapshot_at 取本轮开始时刻所在的 UTC 整点（向下取整）。两张表的主键都是
    (appid, snapshot_at)，写入用 INSERT … ON DUPLICATE KEY UPDATE，
    所以同一小时内重跑只会覆盖，不会多出行。
  - 单款失败不影响其他款：每款各自 try，失败原因分类计数后写进运行记录。
    接口对一部分 appid（下架、工具类、从未有人在线的）固定返回 404，这算"无数据"，不重试。
  - 整轮断网时不逐款耗完重试：连续 ABORT_AFTER 款都是网络错误就放弃本轮，
    已拿到的结果照常入库，然后报错，由调用方（定时进程）等下个小时再试。
  - 限速：全客户端每 0.2 秒最多发起一个请求（5 次/秒），4 个线程并发只是为了不被
    单个慢请求拖住。约 750 款一轮 2.5–3 分钟，一天约 1.8 万次，远低于
    Steam Web API 每个密钥每天 10 万次的上限。

手动跑一轮：python -m crawler.ccu_snapshot
"""
from __future__ import annotations

import logging
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import NamedTuple

from .ccu_watchlist import load_watchlist, utcnow
from .common import settings
from .common.db import connect_etl
from .common.http import HttpClient, HttpError
from .common.runlog import run_log

log = logging.getLogger(__name__)

API_URL = "https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/"
MIN_INTERVAL = 0.2      # 秒；全局 5 次/秒
WORKERS = 4
ABORT_AFTER = 20        # 连续这么多款网络错误就认定断网，放弃本轮
RAW_BODY_MAX = 2000


class RoundAborted(RuntimeError):
    """本轮因为连续网络错误被放弃。"""


class Result(NamedTuple):
    appid: int
    fetched_at: datetime
    http_status: int | None
    attempts: int
    raw_body: str | None
    error: str | None        # None 表示成功
    category: str            # ok / no_data / bad_payload / http_<状态码> / network
    player_count: int | None


def parse_player_count(payload: object) -> int | None:
    """从 {"response": {"player_count": N, "result": 1}} 里取 N；结构不对或 result≠1 返回 None。"""
    try:
        resp = payload["response"]  # type: ignore[index]
        if resp.get("result") != 1:
            return None
        n = resp["player_count"]
    except (KeyError, TypeError, AttributeError):
        return None
    if isinstance(n, bool) or not isinstance(n, int) or n < 0:
        return None
    return n


def fetch_one(client: HttpClient, api_key: str, appid: int) -> Result:
    """请求一款游戏。任何失败都收成 Result 返回，不向外抛。"""
    try:
        resp = client.get(API_URL, params={"appid": appid, "key": api_key},
                          accept_statuses=(200, 404))
    except HttpError as exc:
        category = "network" if exc.kind == "network" else f"http_{exc.status}"
        return Result(appid, utcnow(), exc.status, exc.attempts, None, str(exc)[:255], category, None)

    body = resp.text[:RAW_BODY_MAX]
    attempts = resp.extensions.get("attempts", 1)
    count = None
    if resp.status_code == 200:
        try:
            count = parse_player_count(resp.json())
        except ValueError:
            count = None
    if count is not None:
        return Result(appid, utcnow(), 200, attempts, body, None, "ok", count)
    if resp.status_code == 404:
        return Result(appid, utcnow(), 404, attempts, body, "接口返回 404（该 appid 无在线人数数据）", "no_data", None)
    return Result(appid, utcnow(), resp.status_code, attempts, body, "响应里没有有效的 player_count", "bad_payload", None)


# 已经成功的行不被后来失败的结果覆盖：每一列都先判断"新结果成功，或旧行本来就没成功"。
# MySQL 按书写顺序依次赋值，后面的表达式会读到前面已改过的值，所以 player_count 必须放最后。
_KEEP = "new.player_count IS NOT NULL OR ods_ccu_snapshot.player_count IS NULL"
ODS_UPSERT = f"""
INSERT INTO ods_ccu_snapshot
  (appid, snapshot_at, fetched_at, http_status, attempts, raw_body, error, player_count)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s) AS new
ON DUPLICATE KEY UPDATE
  fetched_at   = IF({_KEEP}, new.fetched_at,   ods_ccu_snapshot.fetched_at),
  http_status  = IF({_KEEP}, new.http_status,  ods_ccu_snapshot.http_status),
  attempts     = IF({_KEEP}, new.attempts,     ods_ccu_snapshot.attempts),
  raw_body     = IF({_KEEP}, new.raw_body,     ods_ccu_snapshot.raw_body),
  error        = IF({_KEEP}, new.error,        ods_ccu_snapshot.error),
  player_count = IF({_KEEP}, new.player_count, ods_ccu_snapshot.player_count)
"""

DWD_UPSERT = """
INSERT INTO dwd_ccu_snapshot (appid, snapshot_at, player_count)
VALUES (%s, %s, %s) AS new
ON DUPLICATE KEY UPDATE player_count = new.player_count
"""


def _write(database: str, sql: str, rows: list[tuple]) -> None:
    if not rows:
        return
    conn = connect_etl(database)
    try:
        with conn.cursor() as cur:
            # 逐行 execute：executemany 会把语句改写成多值 INSERT，和行别名 "AS new" 的写法不兼容。
            for row in rows:
                cur.execute(sql, row)
        conn.commit()
    finally:
        conn.close()


def _count(database: str, table: str, snapshot_at: datetime) -> int:
    conn = connect_etl(database)
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {table} WHERE snapshot_at = %s", (snapshot_at,))
            return cur.fetchone()[0]
    finally:
        conn.close()


def collect_once(stop: threading.Event | None = None) -> dict:
    """采一轮并入库，返回运行记录。stop 被置位时尽快收尾（已拿到的结果照常入库）。

    连续网络错误导致放弃时抛 RoundAborted；数据库不可用等其他错误原样抛出。
    """
    stop = stop or threading.Event()
    api_key = settings.env("STEAM_API_KEY")
    snapshot_at = utcnow().replace(minute=0, second=0)

    with run_log("ccu_snapshot", snapshot_at=snapshot_at.isoformat(sep=" ")) as rec:
        appids = load_watchlist()
        rec["watchlist"] = len(appids)

        aborted = threading.Event()
        streak_lock = threading.Lock()
        streak = 0

        def work(appid: int) -> Result | None:
            nonlocal streak
            if stop.is_set() or aborted.is_set():
                return None
            result = fetch_one(client, api_key, appid)
            with streak_lock:
                streak = streak + 1 if result.category == "network" else 0
                if streak >= ABORT_AFTER:
                    aborted.set()
            return result

        with HttpClient(min_interval=MIN_INTERVAL, connect_timeout=5, read_timeout=10,
                        max_attempts=3, secrets=[api_key]) as client:
            with ThreadPoolExecutor(max_workers=WORKERS, thread_name_prefix="ccu") as pool:
                results = []
                log.info("开始采集 %s（UTC）：名单 %d 款", snapshot_at, len(appids))
                for done, r in enumerate(pool.map(work, appids), start=1):
                    if r is not None:
                        results.append(r)
                    # 中断或放弃后，剩下的款只是被跳过，不再刷进度
                    if r is not None and (done % 100 == 0 or done == len(appids)):
                        ok_so_far = sum(x.player_count is not None for x in results)
                        log.info("进度 %d/%d：成功 %d，失败 %d", done, len(appids),
                                 ok_so_far, len(results) - ok_so_far)
            rec["requests"] = client.stats.requests
            rec["retries"] = client.stats.retries

        categories = Counter(r.category for r in results)
        ok = [r for r in results if r.player_count is not None]
        rec["ok"] = len(ok)
        rec["failures"] = len(results) - len(ok)
        rec["failure_kinds"] = {k: v for k, v in sorted(categories.items()) if k != "ok"}
        rec["skipped"] = len(appids) - len(results)

        _write(settings.DB_ODS_NAME, ODS_UPSERT,
               [(r.appid, snapshot_at, r.fetched_at, r.http_status, r.attempts,
                 r.raw_body, r.error, r.player_count) for r in results])
        _write(settings.DB_NAME, DWD_UPSERT, [(r.appid, snapshot_at, r.player_count) for r in ok])
        rec["rows_loaded"] = len(ok)
        # 库里本小时的实际行数：重跑时它不该增加。
        rec["ods_rows_this_hour"] = _count(settings.DB_ODS_NAME, "ods_ccu_snapshot", snapshot_at)
        rec["dwd_rows_this_hour"] = _count(settings.DB_NAME, "dwd_ccu_snapshot", snapshot_at)

        if aborted.is_set():
            raise RoundAborted(f"连续 {ABORT_AFTER} 款网络错误，放弃本轮（已处理 {len(results)}/{len(appids)} 款）")
        if stop.is_set():
            rec["interrupted"] = True
        return rec


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    collect_once()
