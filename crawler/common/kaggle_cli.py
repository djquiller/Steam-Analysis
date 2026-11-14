"""调用 Kaggle 命令行下载文件。

为什么单独封装：Windows 上 Anaconda 的 Scripts 目录不一定在 PATH 里，直接写 "kaggle" 可能找不到；
这里先查 PATH，再退回到当前 Python 解释器旁边的 Scripts 目录。认证令牌由 Kaggle CLI 自己从
%USERPROFILE%\\.kaggle\\kaggle.json 读取，代码不接触令牌内容。
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def kaggle_exe() -> str:
    found = shutil.which("kaggle")
    if found:
        return found
    for cand in (Path(sys.executable).parent / "Scripts" / "kaggle.exe",
                 Path(sys.executable).parent / "kaggle.exe"):
        if cand.exists():
            return str(cand)
    raise RuntimeError("找不到 kaggle 命令：请先 python -m pip install -r requirements.txt")


def download_file(dataset: str, file: str, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run([kaggle_exe(), "datasets", "download", dataset, "-f", file, "-p", str(dest_dir)], check=True)
    return dest_dir / file
