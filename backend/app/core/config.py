"""后端配置：从仓库根目录的 .env 读取（环境变量优先）。

为什么读根目录的 .env：数据组和后端共用一份 .env（DB_HOST 切换样本库 / 全量库），
不在 backend/ 下另放一份，避免两边不一致。
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",  # .env 里还有 ETL、Steam API 等后端用不到的键
    )

    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_name: str = "steam"
    db_user: str = "api_reader"
    db_password: str = ""

    # 允许跨域访问的前端地址（Vite 开发服务器默认 5173），逗号分隔
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # /meta/filters 的类型列表会缓存这么多秒，用于校验 genre 参数
    genre_cache_seconds: int = 300

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
