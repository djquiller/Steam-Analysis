"""定时采集的常驻进程（APScheduler）。

任务：
  - 在线人数：每小时第 2 分钟（UTC）采一轮。不卡在整点，是为了避开整点的流量高峰，
    同时保证一轮（约 3 分钟）落在同一个小时内。
  - 采集名单：每天 UTC 00:50 重建一次（与采集错开）。

几个行为：
  - 不叠加：同一任务最多一个实例在跑（max_instances=1），上一轮没结束时这一轮直接跳过并记警告。
  - 错过的触发（电脑休眠、进程卡住）：10 分钟内补跑一次，多次错过只补一次（coalesce）；
    超过 10 分钟就等下一个小时，不补历史——在线人数是瞬时值，过后补不回来。
  - 启动时：如果当前这个小时还没有快照，立即补采一轮；已经有了就等下一个触发点。
    加 --no-catchup 可以关掉。
  - 某一轮整体失败（断网、数据库连不上）：只记日志和运行记录，进程不退出，下个小时照常再试。
  - 退出：Ctrl+C（或 Ctrl+Break、终止信号）后不再触发新任务；正在采的一轮会停止发新请求，
    把已拿到的结果入库后退出，最多等一个请求的超时时间。

为什么用 BackgroundScheduler 加主线程循环，而不是 BlockingScheduler：后者的主线程阻塞在
无超时的等待上，Windows 上这种等待收不到 Ctrl+C。主线程用短 sleep 轮询就能及时响应。

启动（仓库根目录，单独开一个终端长期运行）：

    python -m crawler.scheduler

日志同时输出到终端和 data/logs/scheduler.log；每轮的数字在 data/logs/runs.jsonl。
"""
from __future__ import annotations

import argparse
import logging
import signal
import threading
import time
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

from apscheduler.events import EVENT_JOB_MAX_INSTANCES, EVENT_JOB_MISSED
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from . import ccu_snapshot, ccu_watchlist
from .common import settings
from .common.db import connect_etl

log = logging.getLogger("crawler.scheduler")
stop = threading.Event()

MISFIRE_GRACE_SEC = 600


def job_ccu() -> None:
    """采一轮在线人数。所有异常都在这里吃掉：一轮失败不能让常驻进程退出。"""
    if stop.is_set():
        return
    try:
        rec = ccu_snapshot.collect_once(stop)
        log.info("在线人数 %s：名单 %d，成功 %d，失败 %d %s，请求 %d，用时 %.1f 秒",
                 rec["snapshot_at"], rec["watchlist"], rec["ok"], rec["failures"],
                 rec["failure_kinds"], rec["requests"], rec.get("elapsed_sec", 0))
    except Exception as exc:  # noqa: BLE001
        # 采集模块抛出的信息已经脱敏；数据库异常不含密码。
        log.error("在线人数本轮失败，下个触发点再试：%s: %s", type(exc).__name__, exc)


def job_watchlist() -> None:
    if stop.is_set():
        return
    try:
        log.info("采集名单已刷新：%d 款", ccu_watchlist.refresh_watchlist())
    except Exception as exc:  # noqa: BLE001
        log.error("刷新采集名单失败，沿用旧名单：%s: %s", type(exc).__name__, exc)


def has_snapshot_for_current_hour() -> bool:
    hour = ccu_watchlist.utcnow().replace(minute=0, second=0)
    conn = connect_etl(settings.DB_NAME)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM dwd_ccu_snapshot WHERE snapshot_at = %s LIMIT 1", (hour,))
            return cur.fetchone() is not None
    finally:
        conn.close()


def setup_logging() -> None:
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)
    settings.LOG_DIR.mkdir(parents=True, exist_ok=True)
    file = RotatingFileHandler(settings.LOG_DIR / "scheduler.log", maxBytes=2_000_000,
                               backupCount=3, encoding="utf-8")
    file.setFormatter(fmt)
    root.addHandler(file)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)


def main() -> None:
    parser = argparse.ArgumentParser(description="定时采集常驻进程")
    parser.add_argument("--no-catchup", action="store_true", help="启动时不补采当前小时")
    args = parser.parse_args()
    setup_logging()

    scheduler = BackgroundScheduler(
        timezone=timezone.utc,
        job_defaults={"max_instances": 1, "coalesce": True, "misfire_grace_time": MISFIRE_GRACE_SEC},
    )
    scheduler.add_listener(
        lambda e: log.warning("任务 %s 上一轮还没结束，本次触发跳过", e.job_id), EVENT_JOB_MAX_INSTANCES)
    scheduler.add_listener(
        lambda e: log.warning("任务 %s 错过了触发时间且超出补跑期限，跳过", e.job_id), EVENT_JOB_MISSED)

    catchup = False
    if not args.no_catchup:
        try:
            catchup = not has_snapshot_for_current_hour()
        except Exception as exc:  # noqa: BLE001
            log.error("启动时查不了数据库，跳过补采：%s: %s", type(exc).__name__, exc)
    job_kwargs = {"next_run_time": datetime.now(timezone.utc)} if catchup else {}
    scheduler.add_job(job_ccu, CronTrigger(minute=2, timezone=timezone.utc),
                      id="ccu_snapshot", **job_kwargs)
    scheduler.add_job(job_watchlist, CronTrigger(hour=0, minute=50, timezone=timezone.utc),
                      id="ccu_watchlist")

    def on_signal(signum, _frame) -> None:
        log.info("收到退出信号（%s），正在收尾……", signal.Signals(signum).name)
        stop.set()

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)
    if hasattr(signal, "SIGBREAK"):  # Windows 的 Ctrl+Break
        signal.signal(signal.SIGBREAK, on_signal)

    scheduler.start()
    log.info("定时进程已启动：按 Ctrl+C 退出")
    try:
        while not stop.is_set():
            time.sleep(0.5)
    finally:
        stop.set()
        scheduler.shutdown(wait=True)  # 等正在跑的一轮把已拿到的结果入库
        log.info("定时进程已退出。")


if __name__ == "__main__":
    main()
