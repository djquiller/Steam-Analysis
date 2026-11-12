"""公共 HTTP 客户端：重试分类、退避、限速、密钥脱敏。全部用 httpx.MockTransport，不访问外网。"""
from __future__ import annotations

import logging

import httpx
import pytest

from crawler.common.http import HttpClient, HttpError, RateLimiter, redact

SECRET = "FAKE-KEY-FOR-UNIT-TESTS-ONLY-XYZ"
URL = "https://api.example.test/v1/thing"


def make_client(handler, **kwargs):
    """返回 (client, sleeps)。sleep 被替换成记录参数的假函数，测试不会真的等待。"""
    sleeps: list[float] = []
    client = HttpClient(transport=httpx.MockTransport(handler), sleep=sleeps.append,
                        secrets=[SECRET], **kwargs)
    return client, sleeps


def sequence(*responses):
    """依次返回给定的响应；元素是异常时抛出它。同时记录收到的请求。"""
    calls: list[httpx.Request] = []
    queue = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    return handler, calls


# ---------------------------------------------------------------- 重试 ----

@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_retryable_status_is_retried_then_succeeds(status):
    handler, calls = sequence(httpx.Response(status), httpx.Response(200, json={"ok": 1}))
    client, sleeps = make_client(handler)
    resp = client.get(URL)
    assert resp.status_code == 200
    assert resp.extensions["attempts"] == 2
    assert len(calls) == 2 and len(sleeps) == 1
    assert (client.stats.requests, client.stats.retries, client.stats.failures) == (2, 1, 0)


@pytest.mark.parametrize("exc", [
    httpx.ConnectError("connection refused"),
    httpx.ConnectTimeout("connect timed out"),
    httpx.ReadTimeout("read timed out"),
    httpx.RemoteProtocolError("server disconnected"),
])
def test_network_error_is_retried_then_succeeds(exc):
    handler, calls = sequence(exc, httpx.Response(200))
    client, _ = make_client(handler)
    assert client.get(URL).status_code == 200
    assert len(calls) == 2


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_non_retryable_4xx_fails_immediately(status):
    handler, calls = sequence(httpx.Response(status), httpx.Response(200))
    client, sleeps = make_client(handler)
    with pytest.raises(HttpError) as info:
        client.get(URL)
    assert len(calls) == 1 and sleeps == []
    assert info.value.kind == "status" and info.value.status == status and info.value.attempts == 1
    assert client.stats.failures == 1


def test_accepted_status_is_returned_without_retry():
    """调用方声明 404 是正常答复时，直接返回，不重试也不算失败。"""
    handler, calls = sequence(httpx.Response(404, json={"response": {"result": 42}}))
    client, sleeps = make_client(handler)
    resp = client.get(URL, accept_statuses=(200, 404))
    assert resp.status_code == 404
    assert len(calls) == 1 and sleeps == [] and client.stats.failures == 0


def test_gives_up_after_max_attempts():
    handler, calls = sequence(*[httpx.Response(503)] * 3)
    client, sleeps = make_client(handler, max_attempts=3)
    with pytest.raises(HttpError) as info:
        client.get(URL)
    assert len(calls) == 3 and len(sleeps) == 2  # 最后一次失败后不再等待
    assert info.value.status == 503 and info.value.attempts == 3
    assert (client.stats.requests, client.stats.retries, client.stats.failures) == (3, 2, 1)


def test_network_error_exhausted_reports_kind_network():
    handler, _ = sequence(*[httpx.ReadTimeout("read timed out")] * 2)
    client, _ = make_client(handler, max_attempts=2)
    with pytest.raises(HttpError) as info:
        client.get(URL)
    assert info.value.kind == "network" and info.value.status is None


def test_backoff_grows_exponentially_and_is_capped():
    handler, _ = sequence(*[httpx.Response(500)] * 5)
    client, sleeps = make_client(handler, max_attempts=5, backoff_base=1.0, backoff_max=5.0)
    with pytest.raises(HttpError):
        client.get(URL)
    # 基数 1、2、4、8，各加 0–25% 抖动，封顶 5
    assert 1.0 <= sleeps[0] <= 1.25
    assert 2.0 <= sleeps[1] <= 2.5
    assert 4.0 <= sleeps[2] <= 5.0
    assert sleeps[3] == 5.0


def test_retry_after_header_is_honoured():
    handler, _ = sequence(httpx.Response(429, headers={"Retry-After": "7"}), httpx.Response(200))
    client, sleeps = make_client(handler, backoff_base=1.0)
    client.get(URL)
    assert sleeps == [7.0]


def test_user_agent_and_timeouts_are_set():
    handler, calls = sequence(httpx.Response(200))
    client, _ = make_client(handler, user_agent="unit-test/1.0", connect_timeout=3, read_timeout=9)
    client.get(URL)
    assert calls[0].headers["User-Agent"] == "unit-test/1.0"
    timeout = calls[0].extensions["timeout"]
    assert timeout["connect"] == 3 and timeout["read"] == 9
    assert timeout["write"] is not None and timeout["pool"] is not None


# ---------------------------------------------------------------- 限速 ----

def test_rate_limiter_spaces_out_requests():
    now = [100.0]
    sleeps: list[float] = []

    def fake_sleep(sec: float) -> None:
        sleeps.append(sec)
        now[0] += sec

    limiter = RateLimiter(0.5, clock=lambda: now[0], sleep=fake_sleep)
    for _ in range(3):
        limiter.wait()
    assert sleeps == [0.5, 0.5]  # 第一次不等，之后每次间隔 0.5 秒
    now[0] += 10                 # 空闲很久之后不需要再等，也不会"攒额度"连发
    limiter.wait()
    limiter.wait()
    assert sleeps == [0.5, 0.5, 0.5]


def test_client_applies_rate_limit_to_every_request():
    now = [0.0]
    waits: list[float] = []

    def fake_sleep(sec: float) -> None:
        waits.append(sec)
        now[0] += sec

    handler, _ = sequence(*[httpx.Response(200)] * 3)
    client = HttpClient(transport=httpx.MockTransport(handler), min_interval=0.2,
                        sleep=fake_sleep, clock=lambda: now[0])
    for _ in range(3):
        client.get(URL)
    assert waits == pytest.approx([0.2, 0.2])


# ---------------------------------------------------------------- 脱敏 ----

def test_redact_by_param_name():
    text = f"GET https://x.test/a?appid=730&key={SECRET}&format=json failed"
    out = redact(text)
    assert SECRET not in out
    assert "appid=730" in out and "key=***" in out and "format=json" in out


def test_redact_does_not_touch_lookalike_params():
    assert redact("https://x.test/a?monkey=banana&keyword=abc") == "https://x.test/a?monkey=banana&keyword=abc"


def test_redact_by_literal_value_outside_url():
    assert SECRET not in redact(f"header X-Auth: {SECRET}", secrets=[SECRET])


def test_error_message_and_url_have_no_secret():
    handler, _ = sequence(httpx.Response(403))
    client, _ = make_client(handler)
    with pytest.raises(HttpError) as info:
        client.get(URL, params={"appid": 730, "key": SECRET})
    assert SECRET not in str(info.value) and SECRET not in info.value.url
    assert "appid=730" in info.value.url and "key=***" in info.value.url


def test_network_error_text_containing_url_is_redacted():
    """底层异常信息里带完整 URL（含密钥）时，抛出的 HttpError 里也不能有。"""
    leaky = httpx.ConnectError(f"cannot connect to {URL}?appid=730&key={SECRET}")
    handler, _ = sequence(leaky)
    client, _ = make_client(handler, max_attempts=1)
    with pytest.raises(HttpError) as info:
        client.get(URL, params={"appid": 730, "key": SECRET})
    assert SECRET not in str(info.value)


def test_logs_have_no_secret(caplog):
    """重试时本模块写的日志、以及 httpx 自带的请求日志，都不能出现密钥。"""
    handler, _ = sequence(httpx.Response(503), httpx.ReadTimeout("timed out"), httpx.Response(200))
    client, _ = make_client(handler)
    with caplog.at_level(logging.DEBUG):
        logging.getLogger("httpx").setLevel(logging.WARNING)  # caplog 不改已显式设置的级别，这里再确认一次
        client.get(URL, params={"appid": 730, "key": SECRET})
    assert len(caplog.records) >= 2
    assert SECRET not in caplog.text
    assert "key=***" in caplog.text
