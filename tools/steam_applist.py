"""获取 Steam 商店全部游戏的 appid 与名称，支持全量与增量，结果写成 JSON。

做什么
------
调用 Steam Web API ``IStoreService/GetAppList/v1``，只取游戏类型（include_games），
不含 DLC、软件、视频、硬件。每个 appid 收一条，同一游戏的区服版、单人/多人拆分版、
增强版等各有自己的 appid，这里一律分开保留，不做合并。

两个输出文件（默认放在 data/raw/，该目录已被 .gitignore 忽略）：

- ``steam_applist.json``：数据集本身，按 appid 升序的数组，每条只有 appid 与 name::

    [
    {"appid": 10, "name": "Counter-Strike"},
    {"appid": 20, "name": "Team Fortress Classic"}
    ]

- ``steam_applist.state.json``：增量所需的状态，记录下一次增量的起点
  ``next_if_modified_since``（Unix 秒）和最近的运行统计。

全量与增量
----------
- 全量（``--full``，或主文件不存在时自动触发）：按 ``last_appid`` 翻页拉完全部游戏，
  整体替换主文件。上次有、这次没有的 appid（下架或改了类型）会被移除，数量记入状态文件。
- 增量（默认）：把状态文件里的 ``next_if_modified_since`` 传给接口，只拿此后新增或修改过的
  游戏，按 appid 合并进主文件：新 appid 追加，已有 appid 更新 name，不删除任何条目
  （接口不报告下架，只有全量能发现）。
- 起点 = 本次运行开始时刻 − 1 小时。多出的 1 小时重叠会重复拿到少量条目，按 appid 合并后
  结果不变，用来防止边界上的漏数。起点只在运行成功后才前移，所以中途失败或关机错过的时段，
  下一次运行会自动补上。

定时（``--schedule``）
----------------------
常驻进程，按 Steam 官方所用时区（America/Los_Angeles）每小时 00 分跑一次增量；启动时先立即跑
一次。``max_instances=1`` 防止上一轮没跑完又开新一轮，``coalesce=True`` 让休眠或关机期间错过的
多次只补跑一次。单次任务失败只记日志，不退出进程，下个整点再试。不加 ``--schedule`` 时跑一次即退出。

容错
----
- 遇到 429、5xx 或网络错误按指数退避重试 5 次，仍失败则报错退出，旧文件保持不动。
- 先写同目录的临时文件再 ``os.replace`` 原子替换，崩溃不会留下写了一半的 JSON。
- API Key 只从环境变量或项目根目录的 ``.env`` 读取 ``STEAM_API_KEY``；日志与报错信息中会把
  Key 替换成 ``***``，请求 URL 不打印。

依赖：httpx；``--schedule`` 另需 APScheduler 3.x（``APScheduler>=3.10,<4``）；Windows 上
zoneinfo 需要 tzdata。

用法::

    python tools/steam_applist.py              # 增量（首次没有主文件时自动全量）
    python tools/steam_applist.py --full       # 强制全量
    python tools/steam_applist.py --schedule   # 常驻，每小时整点增量
    python tools/steam_applist.py --out D:/x/applist.json
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

API_URL = "https://api.steampowered.com/IStoreService/GetAppList/v1/"
SOURCE = "IStoreService/GetAppList/v1"
FILTERS = {
    "include_games": True,
    "include_dlc": False,
    "include_software": False,
    "include_videos": False,
    "include_hardware": False,
}
PAGE_SIZE = 50_000           # 接口单页上限
OVERLAP_SECONDS = 3600       # 增量起点向前多取 1 小时
MAX_RETRIES = 5
BACKOFF_BASE_SECONDS = 2     # 第 n 次重试前等待 2**n 秒：2、4、8、16、32
TIMEOUT_SECONDS = 60
RUNS_KEPT = 200              # 状态文件里保留最近多少次运行记录（每小时一次约一周）
SCHEDULE_TZ = "America/Los_Angeles"  # Steam 官方使用的太平洋时间

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "data" / "raw" / "steam_applist.json"

log = logging.getLogger("steam_applist")


# ---------------------------------------------------------------- 配置与工具

def load_api_key() -> str:
    """优先读环境变量，其次读项目根目录 .env；不打印 Key。"""
    key = os.environ.get("STEAM_API_KEY", "").strip()
    env_file = ROOT / ".env"
    if not key and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("STEAM_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    if not key:
        raise SystemExit("缺少 STEAM_API_KEY：请在项目根目录 .env 中填写 "
                         "（申请地址 https://steamcommunity.com/dev/apikey）")
    return key


def redact(text: str, key: str) -> str:
    return text.replace(key, "***") if key else text


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def atomic_write_text(path: Path, text: str) -> None:
    """写同目录临时文件后原子替换；失败时删掉临时文件，不留过程文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


# ---------------------------------------------------------------- 读写文件

def load_apps(path: Path) -> dict[int, str]:
    with path.open(encoding="utf-8") as f:
        return {int(a["appid"]): a["name"] for a in json.load(f)}


def dump_apps(path: Path, apps: dict[int, str]) -> None:
    # 一行一个对象：仍是标准 JSON，但比整体缩进小得多，也便于 diff
    lines = (json.dumps({"appid": appid, "name": apps[appid]}, ensure_ascii=False)
             for appid in sorted(apps))
    atomic_write_text(path, "[\n" + ",\n".join(lines) + "\n]\n")


def state_path_for(out: Path) -> Path:
    return out.with_name(out.stem + ".state.json")


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def dump_state(path: Path, state: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")


# ---------------------------------------------------------------- 请求接口

def get_page(client: httpx.Client, key: str, params: dict[str, Any]) -> dict[str, Any]:
    """请求一页；429、5xx、网络错误按指数退避重试，其余 4xx 直接失败。"""
    for attempt in range(MAX_RETRIES + 1):
        reason: str
        try:
            resp = client.get(API_URL, params={"key": key, **params})
        except httpx.TransportError as e:
            reason = f"网络错误 {type(e).__name__}: {redact(str(e), key)}"
        else:
            if resp.status_code == 200:
                return resp.json().get("response", {})
            if resp.status_code in (401, 403):
                raise RuntimeError(f"HTTP {resp.status_code}：API Key 无效或无权限")
            if resp.status_code != 429 and resp.status_code < 500:
                raise RuntimeError(f"HTTP {resp.status_code}：请求参数有误")
            reason = f"HTTP {resp.status_code}"
        if attempt == MAX_RETRIES:
            raise RuntimeError(f"重试 {MAX_RETRIES} 次后仍失败（{reason}）")
        wait = BACKOFF_BASE_SECONDS ** (attempt + 1)
        log.warning("%s，%d 秒后第 %d 次重试", reason, wait, attempt + 1)
        time.sleep(wait)
    raise AssertionError("unreachable")


def fetch(key: str, if_modified_since: int | None) -> tuple[dict[int, str], int]:
    """按 last_appid 翻页取完；返回 {appid: name} 与请求次数。"""
    params: dict[str, Any] = {k: str(v).lower() for k, v in FILTERS.items()}
    params["max_results"] = PAGE_SIZE
    if if_modified_since is not None:
        params["if_modified_since"] = if_modified_since
    apps: dict[int, str] = {}
    requests = 0
    last_appid = 0
    with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
        while True:
            page = get_page(client, key, {**params, "last_appid": last_appid})
            requests += 1
            for app in page.get("apps", []):
                apps[int(app["appid"])] = app.get("name", "")
            log.info("第 %d 页：%d 条，累计 %d 条", requests, len(page.get("apps", [])), len(apps))
            if not page.get("have_more_results"):
                break
            last_appid = int(page["last_appid"])
    return apps, requests


# ---------------------------------------------------------------- 一次运行

def run_once(out: Path, force_full: bool) -> dict[str, Any]:
    key = load_api_key()
    state_path = state_path_for(out)
    state = load_state(state_path)
    started = utc_now()

    full = force_full or not out.exists() or "next_if_modified_since" not in state
    old = {} if not out.exists() else load_apps(out)
    since = None if full else int(state["next_if_modified_since"])
    if since is None:
        log.info("全量获取开始")
    else:
        log.info("增量获取开始：if_modified_since=%s",
                 iso(datetime.fromtimestamp(since, timezone.utc)))

    try:
        fetched, requests = fetch(key, since)
    except Exception as e:  # 确保 Key 不会出现在向上抛出的信息里
        raise RuntimeError(redact(str(e), key)) from None

    if full:
        new = fetched
        added = len(new.keys() - old.keys())
        renamed = sum(1 for a in new.keys() & old.keys() if new[a] != old[a])
        removed = len(old.keys() - new.keys())
    else:
        new = dict(old)
        added = len(fetched.keys() - old.keys())
        renamed = sum(1 for a in fetched.keys() & old.keys() if fetched[a] != old[a])
        removed = 0
        new.update(fetched)

    finished = utc_now()
    run = {
        "mode": "full" if full else "incremental",
        "started_at": iso(started),
        "finished_at": iso(finished),
        "if_modified_since": since,
        "requests": requests,
        "fetched": len(fetched),
        "added": added,
        "renamed": renamed,
        "removed": removed,
        "app_count": len(new),
    }
    state = {
        "source": SOURCE,
        "filters": FILTERS,
        "data_file": out.name,
        "app_count": len(new),
        "next_if_modified_since": int(started.timestamp()) - OVERLAP_SECONDS,
        "last_full_at": iso(started) if full else state.get("last_full_at"),
        "last_run_at": iso(started),
        "runs": (state.get("runs", []) + [run])[-RUNS_KEPT:],
    }
    # 先写数据再写状态：若两步之间崩溃，状态里还是旧起点，下次只会多取一段，不会漏
    dump_apps(out, new)
    dump_state(state_path, state)
    log.info("完成（%s）：本次取回 %d 条，新增 %d，改名 %d，移除 %d，现有 %d 条，用时 %.1f 秒",
             run["mode"], len(fetched), added, renamed, removed, len(new),
             (finished - started).total_seconds())
    return run


def run_scheduled(out: Path, force_full: bool) -> None:
    from zoneinfo import ZoneInfo

    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

    def job(full: bool = False) -> None:
        try:
            run_once(out, full)
        except Exception as e:  # 单次失败不退出常驻进程，下个整点再试
            log.error("本次运行失败：%s", e)

    job(force_full)  # 启动时先跑一次
    tz = ZoneInfo(SCHEDULE_TZ)
    scheduler = BlockingScheduler(timezone=tz)
    scheduler.add_job(job, CronTrigger(minute=0, timezone=tz), id="steam_applist",
                      max_instances=1, coalesce=True, misfire_grace_time=3600)
    log.info("已进入定时模式：每小时 00 分（%s）执行增量，Ctrl+C 退出", SCHEDULE_TZ)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("已退出定时模式")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="获取 Steam 商店全部游戏的 appid 与名称（全量 / 增量）")
    parser.add_argument("--full", action="store_true", help="强制全量，整体替换主文件")
    parser.add_argument("--schedule", action="store_true",
                        help="常驻进程，启动时跑一次，之后每小时 00 分（太平洋时间）跑增量")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help=f"主文件路径，默认 {DEFAULT_OUT.relative_to(ROOT).as_posix()}；"
                             "状态文件放在同目录的 <主文件名>.state.json")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        stream=sys.stdout)
    # httpx 在 INFO 级别会打印完整请求 URL（含 key=...），压到 WARNING 以免泄露 Key
    logging.getLogger("httpx").setLevel(logging.WARNING)
    out = args.out.resolve()
    if args.schedule:
        run_scheduled(out, args.full)
        return 0
    try:
        run_once(out, args.full)
    except Exception as e:
        log.error("运行失败：%s", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
