"""所有采集脚本共用的 HTTP 客户端。

做什么：在 httpx 之上统一四件事——超时、重试、限速、User-Agent，并保证密钥不进日志。
为什么集中在这里：
  - 超时：本机网络经过代理（TUN / fake-ip），出现过连接"半死"、请求一直不返回的情况，
    所以连接、读取、写入、取连接四个阶段都设了上限，任何请求都不会无限期挂住。
  - 重试：只重试"再试一次可能成功"的情况——429、5xx、网络错误（含超时）；
    其余 4xx（如 400、403、404）重试也没用，立刻返回或报错。等待时间按指数退避加随机抖动，
    服务器给了 Retry-After 就听它的。
  - 限速：两次请求的发起时刻至少间隔 min_interval 秒，多线程共用一个客户端时也成立。
  - 脱敏：Steam Web API 的密钥放在查询参数 key 里，而 httpx 的异常信息和它自带的日志
    都会带完整 URL。本模块抛出的异常、写出的日志一律先经过 redact()；httpx / httpcore
    自带的日志调到 WARNING 以上。

用法（appdetails、SteamSpy 等以后的采集各建一个实例，限速各自设）：

    client = HttpClient(min_interval=0.2, secrets=[api_key])
    resp = client.get(url, params={"appid": 730, "key": api_key}, accept_statuses=(200, 404))
    ...
    client.close()
"""
from __future__ import annotations

import logging
import random
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Iterable, Mapping

import httpx

log = logging.getLogger(__name__)

# httpx 在 INFO 级别会打印 "HTTP Request: GET <完整 URL>"，其中带密钥，必须关掉。
for _name in ("httpx", "httpcore"):
    logging.getLogger(_name).setLevel(logging.WARNING)

DEFAULT_USER_AGENT = "steam-analysis-crawler/0.1 (course project; python-httpx)"

# 这些查询参数的值一律视为密钥，输出前替换成 ***。
DEFAULT_SECRET_PARAMS = ("key", "api_key", "apikey", "token", "access_token")

RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})


def redact(text: object, *, secret_params: Iterable[str] = DEFAULT_SECRET_PARAMS,
           secrets: Iterable[str] = ()) -> str:
    """去掉文本里的密钥：先按参数名（?key=…），再按密钥的字面值各替换一遍。

    两种方式都做，是因为密钥既可能出现在 URL 里，也可能被别的库拼进异常信息的其他位置。
    """
    out = str(text)
    names = "|".join(re.escape(p) for p in secret_params)
    if names:
        out = re.sub(rf"(?i)([?&;]|\b)({names})=[^&\s'\"<>)]*", r"\1\2=***", out)
    for secret in secrets:
        if secret:
            out = out.replace(secret, "***")
    return out


class HttpError(Exception):
    """请求最终失败。信息已脱敏，可以直接写日志或入库。

    kind:   "network"（连接失败、超时等，没拿到响应）或 "status"（拿到了不接受的状态码）
    status: HTTP 状态码；网络错误时为 None
    """

    def __init__(self, message: str, *, kind: str, status: int | None, url: str, attempts: int):
        super().__init__(message)
        self.kind = kind
        self.status = status
        self.url = url
        self.attempts = attempts


@dataclass
class HttpStats:
    """累计计数，采集脚本把它们写进运行记录。"""
    requests: int = 0   # 实际发出的请求数（含重试）
    retries: int = 0    # 其中属于重试的次数
    failures: int = 0   # 重试用尽或不可重试、最终失败的调用数
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add(self, **delta: int) -> None:
        with self._lock:
            for name, n in delta.items():
                setattr(self, name, getattr(self, name) + n)


class RateLimiter:
    """保证相邻两次请求的发起时刻至少间隔 min_interval 秒（线程安全）。"""

    def __init__(self, min_interval: float, *, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        self.min_interval = max(0.0, float(min_interval))
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._next_slot = 0.0

    def wait(self) -> None:
        if self.min_interval <= 0:
            return
        # 在锁内只做"预约时刻"，睡眠放在锁外，多个线程可以同时等各自的时刻。
        with self._lock:
            now = self._clock()
            slot = max(now, self._next_slot)
            self._next_slot = slot + self.min_interval
        delay = slot - now
        if delay > 0:
            self._sleep(delay)


class HttpClient:
    """带超时、重试、限速、脱敏的 GET 客户端。可在多个线程间共用。"""

    def __init__(
        self,
        *,
        user_agent: str = DEFAULT_USER_AGENT,
        connect_timeout: float = 5.0,
        read_timeout: float = 15.0,
        max_attempts: int = 3,
        backoff_base: float = 1.0,
        backoff_max: float = 30.0,
        min_interval: float = 0.0,
        secret_params: Iterable[str] = DEFAULT_SECRET_PARAMS,
        secrets: Iterable[str] = (),
        headers: Mapping[str, str] | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        if max_attempts < 1:
            raise ValueError("max_attempts 至少为 1")
        self.max_attempts = max_attempts
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max
        self.stats = HttpStats()
        self._secret_params = tuple(secret_params)
        self._secrets = tuple(s for s in secrets if s)
        self._sleep = sleep
        self._limiter = RateLimiter(min_interval, clock=clock, sleep=sleep)
        # write / pool 也设上限：四个阶段缺任何一个，半死的连接都可能让线程永久挂住。
        timeout = httpx.Timeout(connect=connect_timeout, read=read_timeout,
                                write=read_timeout, pool=connect_timeout + read_timeout)
        self._client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": user_agent, "Accept": "application/json", **(headers or {})},
            transport=transport,
            follow_redirects=True,
        )

    # -- 对外接口 ---------------------------------------------------------
    def redact(self, text: object) -> str:
        return redact(text, secret_params=self._secret_params, secrets=self._secrets)

    def get(self, url: str, *, params: Mapping[str, object] | None = None,
            accept_statuses: Iterable[int] = (200,),
            headers: Mapping[str, str] | None = None) -> httpx.Response:
        """发 GET 请求，返回状态码在 accept_statuses 里的响应；否则抛 HttpError。

        accept_statuses 让调用方声明"哪些状态码算正常答复"。例如在线人数接口对查不到的
        appid 返回 404，那是一个有效答案，调用方传 (200, 404) 自己区分，不会被重试。
        """
        accept = frozenset(accept_statuses)
        safe_url = self.redact(httpx.URL(url, params=dict(params) if params else None))
        last_error = "未发出请求"
        last_status: int | None = None
        last_kind = "network"

        for attempt in range(1, self.max_attempts + 1):
            self._limiter.wait()
            self.stats.add(requests=1, retries=1 if attempt > 1 else 0)
            retry_after: float | None = None
            try:
                resp = self._client.get(url, params=params, headers=headers)
            except httpx.TransportError as exc:
                # 连接失败、各类超时、连接被重置、代理错误：都值得再试。
                last_kind, last_status = "network", None
                last_error = f"{type(exc).__name__}: {self.redact(exc)}"
            else:
                if resp.status_code in accept:
                    resp.extensions["attempts"] = attempt  # 调用方想知道重试了几次时从这里取
                    return resp
                last_kind, last_status = "status", resp.status_code
                last_error = f"HTTP {resp.status_code}"
                if resp.status_code not in RETRYABLE_STATUSES:
                    break  # 其余 4xx：重试没有意义
                retry_after = _parse_retry_after(resp.headers.get("Retry-After"))

            if attempt < self.max_attempts:
                delay = self._backoff(attempt, retry_after)
                log.warning("请求失败，%.1f 秒后重试（第 %d/%d 次）：%s  %s",
                            delay, attempt, self.max_attempts, last_error, safe_url)
                self._sleep(delay)

        self.stats.add(failures=1)
        raise HttpError(f"{last_error}（共尝试 {attempt} 次）：{safe_url}",
                        kind=last_kind, status=last_status, url=safe_url, attempts=attempt)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- 内部 -------------------------------------------------------------
    def _backoff(self, attempt: int, retry_after: float | None) -> float:
        """第 attempt 次失败后的等待：base × 2^(attempt-1)，加 0–25% 抖动，封顶 backoff_max。"""
        delay = self.backoff_base * (2 ** (attempt - 1))
        delay *= 1 + random.uniform(0, 0.25)
        if retry_after is not None:
            delay = max(delay, retry_after)
        return min(delay, self.backoff_max)


def _parse_retry_after(value: str | None) -> float | None:
    """只认"秒数"形式的 Retry-After；HTTP 日期形式很少见，忽略后按退避处理。"""
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None
