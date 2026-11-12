"""读取仓库根目录的 .env。

为什么集中在这里：密钥和数据库地址只允许出现在 .env（见根目录 CLAUDE.md "密钥"一条），
所有脚本都从这里取配置，避免各自读环境变量、各自写默认值。
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env", encoding="utf-8")


def env(name: str, default: str | None = None) -> str:
    """取配置项；没有默认值又没配置时直接报错，提示去填 .env。"""
    value = os.getenv(name, default)
    if value is None or value == "":
        raise RuntimeError(f"缺少配置 {name}：请在 {ROOT / '.env'} 中填写（参考 .env.example）")
    return value


DB_HOST = env("DB_HOST", "127.0.0.1")
DB_PORT = int(env("DB_PORT", "3306"))
DB_NAME = env("DB_NAME", "steam")
DB_ODS_NAME = env("DB_ODS_NAME", "steam_ods")
DATA_DIR = ROOT / env("DATA_DIR", "data/raw")
LOG_DIR = ROOT / "data" / "logs"
