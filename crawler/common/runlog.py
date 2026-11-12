"""记录每次运行的来源、起止时间、请求数、失败数、入库行数。

这些数字是《数据质量报告》和答辩"数据来源与规模"页的依据（见 crawler/CLAUDE.md），
所以每次运行都追加一行 JSON 到 data/logs/runs.jsonl，同时打印到终端。
"""
from __future__ import annotations

import json
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

from . import settings


@contextmanager
def run_log(source: str, **extra) -> Iterator[dict]:
    """用法：with run_log("kaggle_games") as log: ...; log["rows_loaded"] = n"""
    record = {
        "source": source,
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "requests": 0,
        "failures": 0,
        "rows_loaded": 0,
        **extra,
    }
    start = time.perf_counter()
    status = "ok"
    try:
        yield record
    except BaseException as exc:
        status = f"error: {type(exc).__name__}: {exc}"
        raise
    finally:
        record["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        record["elapsed_sec"] = round(time.perf_counter() - start, 1)
        record["status"] = status
        settings.LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(settings.LOG_DIR / "runs.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        print("[run]", json.dumps(record, ensure_ascii=False))
