from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    """返回信封：code = 0 成功；40001 参数错误；40401 资源不存在；50001 数据库异常。"""

    code: int = Field(0, description="0 成功；40001 参数错误；40401 资源不存在；50001 数据库异常")
    msg: str = "ok"
    data: T | None = None
