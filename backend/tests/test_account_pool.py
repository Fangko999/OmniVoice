import asyncio
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from gemini_webapi.exceptions import AuthError, TemporarilyBlockedError, UsageLimitExceededError

from core.account_pool import AccountPool, AllAccountsExhausted


class FakeClock:
    def __init__(self):
        self.t = 1_700_000_000.0

    def __call__(self):
        return self.t

    async def sleep(self, s):
        self.t += s


class FakeResp:
    def __init__(self, text):
        self.text = text


def make_pool(tmp_path, n, behaviors, settings=None):
    """behaviors: dict name -> list of results ('ok' | Exception instance), consumed in order; default 'ok'."""
    cfg = {
        "settings": {"min_delay": 0, "max_delay": 0, **(settings or {})},
        "accounts": [{"name": f"acc{i}", "secure_1psid": f"psid{i}xxxxxxxx", "secure_1psidts": "t"} for i in range(1, n + 1)],
    }
    p = tmp_path / "accounts.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    calls = []

    class FakeClient:
        def __init__(self, acc):
            self.acc = acc

        async def init(self, **kw):
            pass

        async def close(self):
            pass

        async def generate_content(self, prompt, model=None, temporary=False):
            calls.append(self.acc.name)
            queue = behaviors.get(self.acc.name, [])
            r = queue.pop(0) if queue else "ok"
            if isinstance(r, Exception):
                raise r
            return FakeResp(f"{self.acc.name}:{r}")

    clock = FakeClock()
    pool = AccountPool(str(p), str(tmp_path / "usage.json"), client_factory=FakeClient, clock=clock, sleep=clock.sleep)
    pool.load()
    return pool, calls, clock


def run(coro):
    return asyncio.run(coro)


def test_round_robin(tmp_path):
    pool, calls, _ = make_pool(tmp_path, 3, {})
    for _ in range(6):
        run(pool.generate("x"))
    assert calls == ["acc1", "acc2", "acc3", "acc1", "acc2", "acc3"]


def test_usage_limit_switches_and_skips(tmp_path):
    pool, calls, _ = make_pool(tmp_path, 2, {"acc1": [UsageLimitExceededError("quota")]})
    assert run(pool.generate("x")).startswith("acc2")
    run(pool.generate("x"))
    run(pool.generate("x"))
    assert calls == ["acc1", "acc2", "acc2", "acc2"]
    st = {a["name"]: a["status"] for a in pool.status()["accounts"]}
    assert st == {"acc1": "exhausted", "acc2": "active"}


def test_exhausted_recovers_after_hours(tmp_path):
    pool, calls, clock = make_pool(tmp_path, 1, {"acc1": [UsageLimitExceededError("q")]}, {"exhausted_hours": 1})
    with pytest.raises(AllAccountsExhausted):
        run(pool.generate("x"))
    clock.t += 3601
    assert run(pool.generate("x")).startswith("acc1")


def test_all_exhausted_raises(tmp_path):
    pool, _, _ = make_pool(tmp_path, 2, {
        "acc1": [UsageLimitExceededError("q")],
        "acc2": [AuthError("bad cookie")],
    })
    with pytest.raises(AllAccountsExhausted):
        run(pool.generate("x"))
    st = {a["name"]: a["status"] for a in pool.status()["accounts"]}
    assert st == {"acc1": "exhausted", "acc2": "auth_failed"}


def test_ip_block_pauses_whole_pool(tmp_path):
    pool, calls, clock = make_pool(tmp_path, 2, {"acc1": [TemporarilyBlockedError("429")]}, {"ip_block_minutes": [5]})
    t0 = clock.t
    out = run(pool.generate("x"))
    assert clock.t - t0 >= 300
    assert out.startswith("acc2")


def test_transient_errors_cooldown(tmp_path):
    pool, calls, _ = make_pool(tmp_path, 2, {"acc1": [RuntimeError("e")] * 3}, {"max_consecutive_errors": 3})
    for _ in range(6):
        run(pool.generate("x"))
    # acc1 lỗi 3 lần liên tiếp (xen kẽ acc2 thành công) -> cooldown
    assert pool.status()["accounts"][0]["status"] == "cooldown"


def test_daily_limit(tmp_path):
    pool, calls, _ = make_pool(tmp_path, 2, {})
    pool.accounts[0].daily_limit = 2
    for _ in range(6):
        run(pool.generate("x"))
    assert calls.count("acc1") == 2


def test_auth_failed_reset_when_cookie_changes(tmp_path):
    pool, _, _ = make_pool(tmp_path, 1, {"acc1": [AuthError("x")]})
    with pytest.raises(AllAccountsExhausted):
        run(pool.generate("x"))
    cfg = json.loads((tmp_path / "accounts.json").read_text(encoding="utf-8"))
    cfg["accounts"][0]["secure_1psid"] = "newcookie123456789"
    (tmp_path / "accounts.json").write_text(json.dumps(cfg), encoding="utf-8")
    pool.load()
    assert pool.status()["accounts"][0]["status"] == "active"


def test_zero_quota_skipped_and_recovers_at_reset(tmp_path):
    pool, calls, clock = make_pool(tmp_path, 2, {})
    reset_at = clock.t + 1800
    orig_factory = pool.client_factory

    def factory(acc):
        c = orig_factory(acc)
        if acc.name == "acc1":
            c._quotas = {"x": {"action_id": 11, "remaining": 0, "total": 100, "reset_time": reset_at}}
        return c

    pool.client_factory = factory
    for _ in range(3):
        assert run(pool.generate("x")).startswith("acc2")
    st = pool.status()["accounts"][0]
    assert st["status"] == "exhausted"
    clock.t = reset_at + 31
    run(pool.generate("x"))
    run(pool.generate("x"))
    assert "acc1" in calls


class _Status:
    def __init__(self, name):
        self.name = name


def test_unauthenticated_at_init_fails_fast(tmp_path):
    """Cookie hết hạn: gemini_webapi init vẫn 'thành công' nhưng account_status=UNAUTHENTICATED."""
    pool, calls, _ = make_pool(tmp_path, 3, {})
    orig = pool.client_factory

    def factory(acc):
        c = orig(acc)
        if acc.name != "acc3":
            c.account_status = _Status("UNAUTHENTICATED")
        return c

    pool.client_factory = factory
    assert run(pool.generate("x")).startswith("acc3")
    st = {a["name"]: a["status"] for a in pool.status()["accounts"]}
    assert st == {"acc1": "auth_failed", "acc2": "auth_failed", "acc3": "active"}


def test_all_unauthenticated_message(tmp_path):
    pool, calls, _ = make_pool(tmp_path, 2, {})
    orig = pool.client_factory

    def factory(acc):
        c = orig(acc)
        c.account_status = _Status("UNAUTHENTICATED")
        return c

    pool.client_factory = factory
    with pytest.raises(AllAccountsExhausted, match="Cookie của TẤT CẢ"):
        run(pool.generate("x"))
    assert calls == []  # không gửi câu hỏi nào


def test_repeated_unauthenticated_generate_is_bounded(tmp_path):
    err = RuntimeError("gemini-flash is not available for use. Account status: UNAUTHENTICATED")
    pool, calls, _ = make_pool(tmp_path, 1, {"acc1": [err] * 10})
    with pytest.raises(AllAccountsExhausted):
        run(pool.generate("x"))
    assert len(calls) == 2  # đăng nhập lại 1 lần, vẫn lỗi -> auth_failed
    assert pool.status()["accounts"][0]["status"] == "auth_failed"


def test_rotated_cookie_persisted(tmp_path):
    pool, _, _ = make_pool(tmp_path, 1, {})
    orig = pool.client_factory

    class _C:
        def __init__(self, name, value, domain=".google.com"):
            self.name, self.value, self.domain = name, value, domain

    class _Jar:
        jar = [_C("__Secure-1PSID", "psid1xxxxxxxx"), _C("__Secure-1PSIDTS", "rotated-ts")]

    def factory(acc):
        c = orig(acc)
        c.cookies = _Jar()
        return c

    pool.client_factory = factory
    run(pool.generate("x"))
    cfg = json.loads((tmp_path / "accounts.json").read_text(encoding="utf-8"))
    assert cfg["accounts"][0]["secure_1psidts"] == "rotated-ts"
    assert cfg["settings"]["min_delay"] == 0  # giữ nguyên phần khác
    pool.load()
    assert pool.accounts[0].client is not None  # cookie đổi do chính pool -> không đăng nhập lại


def test_auth_failed_reset_when_only_psidts_changes(tmp_path):
    pool, _, _ = make_pool(tmp_path, 1, {"acc1": [AuthError("x")]})
    with pytest.raises(AllAccountsExhausted):
        run(pool.generate("x"))
    cfg = json.loads((tmp_path / "accounts.json").read_text(encoding="utf-8"))
    cfg["accounts"][0]["secure_1psidts"] = "new-ts"
    (tmp_path / "accounts.json").write_text(json.dumps(cfg), encoding="utf-8")
    fresh = AccountPool(str(tmp_path / "accounts.json"), str(tmp_path / "usage.json"))
    fresh.load()  # như khởi động lại server
    assert fresh.status()["accounts"][0]["status"] == "active"
