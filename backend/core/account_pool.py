"""Pool nhiều tài khoản Gemini (cookie web) chạy luân phiên.

- Round-robin theo TỪNG request: acc1 -> acc2 -> acc3 -> acc1 ...
- Hết hạn mức (UsageLimitExceededError) -> 'exhausted' trong `exhausted_hours` giờ
- Cookie hỏng (AuthError)               -> 'auth_failed' tới khi reload accounts.json
- Lỗi khác lặp lại 3 lần                -> 'cooldown' `cooldown_minutes` phút
- 429 chặn IP (TemporarilyBlockedError) -> cả pool nghỉ (đổi tài khoản không giúp được)
- Không còn tài khoản nào dùng được     -> ném AllAccountsExhausted

File cấu hình `accounts.json` (đặt trong thư mục backend):
{
  "settings": {"min_delay": 1.0, "max_delay": 2.5, "exhausted_hours": 6, "cooldown_minutes": 10},
  "accounts": [
    {"name": "acc1", "secure_1psid": "...", "secure_1psidts": "...", "enabled": true,
     "daily_limit": null, "proxy": null}
  ]
}
"""
import asyncio
import json
import os
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

from gemini_webapi.exceptions import (
    AuthError,
    TemporarilyBlockedError,
    UsageLimitExceededError,
)

ACCOUNTS_PATH = "accounts.json"
USAGE_PATH = os.path.join("state", "accounts_usage.json")

DEFAULT_SETTINGS = {
    "min_delay": 1.0,
    "max_delay": 2.5,
    "exhausted_hours": 6,
    "cooldown_minutes": 10,
    "max_consecutive_errors": 3,
    "ip_block_minutes": [5, 10, 15],
    "init_timeout": 60,
}


class AllAccountsExhausted(Exception):
    pass


class PoolStopped(Exception):
    pass


@dataclass
class Account:
    name: str
    secure_1psid: str
    secure_1psidts: str
    enabled: bool = True
    daily_limit: Optional[int] = None
    proxy: Optional[str] = None
    # runtime
    status: str = "active"  # active | cooldown | exhausted | auth_failed | disabled
    until: Optional[float] = None  # epoch seconds
    requests_today: int = 0
    day: str = ""
    consecutive_errors: int = 0
    last_error: Optional[str] = None
    quota_remaining: Optional[float] = None
    quota_total: Optional[float] = None
    quota_reset: Optional[float] = None  # epoch seconds
    since_quota_check: int = 0
    client: Any = field(default=None, repr=False)

    def refresh(self, now: float):
        today = datetime.fromtimestamp(now).strftime("%Y-%m-%d")
        if self.day != today:
            self.day = today
            self.requests_today = 0
            if self.status == "exhausted" and self.until is None:
                self.status = "active"
        if not self.enabled:
            self.status = "disabled"
        elif self.status == "disabled":
            self.status = "active"
        if self.status in ("cooldown", "exhausted") and self.until is not None and now >= self.until:
            if self.status == "exhausted":
                self.quota_remaining = None  # số liệu cũ, sẽ đọc lại
            self.status = "active"
            self.until = None
            self.consecutive_errors = 0

    def to_status(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "requests_today": self.requests_today,
            "daily_limit": self.daily_limit,
            "until": datetime.fromtimestamp(self.until).isoformat(timespec="seconds") if self.until else None,
            "last_error": self.last_error,
            "quota_remaining": self.quota_remaining,
            "quota_total": self.quota_total,
            "quota_reset": datetime.fromtimestamp(self.quota_reset).isoformat(timespec="seconds") if self.quota_reset else None,
        }


def _default_client_factory(acc: Account):
    from gemini_webapi import GeminiClient
    return GeminiClient(acc.secure_1psid, acc.secure_1psidts, proxy=acc.proxy)


class AccountPool:
    def __init__(
        self,
        accounts_path: str = ACCOUNTS_PATH,
        usage_path: str = USAGE_PATH,
        client_factory: Callable[[Account], Any] = _default_client_factory,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], Any] = asyncio.sleep,
    ):
        self.accounts_path = accounts_path
        self.usage_path = usage_path
        self.client_factory = client_factory
        self.clock = clock
        self.sleep = sleep
        self.settings = dict(DEFAULT_SETTINGS)
        self.accounts: list[Account] = []
        self._idx = -1
        self._lock = asyncio.Lock()
        self._last_request = 0.0
        self.blocked_until: Optional[float] = None
        self._block_level = 0
        self.on_event: Optional[Callable[[str], None]] = None

    # ------------------------------------------------------------ config
    def load(self):
        if not os.path.exists(self.accounts_path):
            raise FileNotFoundError(
                f"Không tìm thấy {os.path.abspath(self.accounts_path)}. "
                "Hãy tạo file này từ accounts.example.json."
            )
        with open(self.accounts_path, "r", encoding="utf-8-sig") as f:  # -sig: Notepad có thể thêm BOM
            data = json.load(f)
        if isinstance(data, list):
            data = {"accounts": data}
        self.settings = {**DEFAULT_SETTINGS, **data.get("settings", {})}

        old = {a.name: a for a in self.accounts}
        usage = self._read_usage()
        accounts = []
        for i, raw in enumerate(data.get("accounts", [])):
            name = raw.get("name") or f"acc{i + 1}"
            acc = Account(
                name=name,
                secure_1psid=raw["secure_1psid"],
                secure_1psidts=raw.get("secure_1psidts", ""),
                enabled=raw.get("enabled", True),
                daily_limit=raw.get("daily_limit"),
                proxy=raw.get("proxy"),
            )
            prev = old.get(name)
            u = usage.get(name, {})
            acc.day = u.get("day", "")
            acc.requests_today = u.get("requests_today", 0)
            # Cookie có thể đã được cập nhật -> bỏ trạng thái auth_failed
            cookie_changed = prev is not None and prev.secure_1psid != acc.secure_1psid
            status = u.get("status", "active")
            if status == "auth_failed" and (cookie_changed or prev is None and u.get("psid_tail") != acc.secure_1psid[-8:]):
                status = "active"
            acc.status = status
            acc.until = u.get("until")
            acc.last_error = u.get("last_error")
            if prev is not None and not cookie_changed:
                acc.client = prev.client
            accounts.append(acc)
        self.accounts = accounts
        now = self.clock()
        for a in self.accounts:
            a.refresh(now)
        self._save_usage()

    def _read_usage(self) -> dict:
        if os.path.exists(self.usage_path):
            try:
                with open(self.usage_path, "r", encoding="utf-8-sig") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_usage(self):
        os.makedirs(os.path.dirname(self.usage_path) or ".", exist_ok=True)
        data = {
            a.name: {
                "day": a.day,
                "requests_today": a.requests_today,
                "status": a.status if a.status != "disabled" else "active",
                "until": a.until,
                "last_error": a.last_error,
                "psid_tail": a.secure_1psid[-8:],
            }
            for a in self.accounts
        }
        tmp = self.usage_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.usage_path)

    def status(self) -> dict:
        now = self.clock()
        for a in self.accounts:
            a.refresh(now)
        return {
            "accounts": [a.to_status() for a in self.accounts],
            "ip_blocked_until": datetime.fromtimestamp(self.blocked_until).isoformat(timespec="seconds")
            if self.blocked_until and self.blocked_until > now else None,
        }

    # ------------------------------------------------------------ helpers
    def _emit(self, msg: str):
        if self.on_event:
            try:
                self.on_event(msg)
            except Exception:
                pass

    def _next_available(self) -> Optional[Account]:
        n = len(self.accounts)
        now = self.clock()
        for step in range(1, n + 1):
            i = (self._idx + step) % n
            acc = self.accounts[i]
            acc.refresh(now)
            if acc.status == "active":
                self._idx = i
                return acc
        return None

    def _earliest_recovery(self) -> Optional[float]:
        """Thời điểm sớm nhất có tài khoản 'cooldown' hồi lại. None nếu không còn ai có thể hồi trong phiên."""
        times = [a.until for a in self.accounts if a.status == "cooldown" and a.until]
        return min(times) if times else None

    async def _sleep_checked(self, seconds: float, should_stop):
        end = self.clock() + seconds
        while True:
            if should_stop and should_stop():
                raise PoolStopped("Người dùng đã dừng")
            remaining = end - self.clock()
            if remaining <= 0:
                return
            await self.sleep(min(1.0, remaining))

    async def _close_client(self, acc: Account):
        if acc.client is not None:
            try:
                await acc.client.close()
            except Exception:
                pass
            acc.client = None

    async def _get_client(self, acc: Account):
        if acc.client is None:
            client = self.client_factory(acc)
            await client.init(timeout=self.settings["init_timeout"], auto_close=False, auto_refresh=True)
            acc.client = client
            self._read_quota(acc)
        return acc.client

    def _read_quota(self, acc: Account):
        """Đọc hạn mức Gemini Flash mà gemini_webapi đã lấy (thuộc tính nội bộ, có thể không có)."""
        quotas = getattr(acc.client, "_quotas", None)
        if not isinstance(quotas, dict):
            return
        for q in quotas.values():
            if isinstance(q, dict) and q.get("action_id") == 11:  # Gemini Flash
                acc.quota_remaining = q.get("remaining")
                acc.quota_total = q.get("total")
                acc.quota_reset = q.get("reset_time")
                acc.since_quota_check = 0
                return

    async def _refresh_quota(self, acc: Account):
        fetch = getattr(acc.client, "_fetch_quota", None)
        if fetch is None:
            return
        try:
            await fetch(flash=True)
            self._read_quota(acc)
        except Exception:
            pass

    def _mark_exhausted(self, acc: Account):
        acc.status = "exhausted"
        now = self.clock()
        if acc.quota_reset and acc.quota_reset > now:
            acc.until = float(acc.quota_reset) + 30  # đợi thêm 30s cho chắc
        else:
            acc.until = now + self.settings["exhausted_hours"] * 3600

    # ------------------------------------------------------------ main API
    async def generate(self, prompt: str, model: str = "gemini-flash", should_stop=None, max_attempts: Optional[int] = None) -> str:
        if not self.accounts:
            self.load()
        if not self.accounts:
            raise AllAccountsExhausted("accounts.json không có tài khoản nào")

        attempts = 0
        limit = max_attempts or (len(self.accounts) * 2 + 3)
        last_exc: Optional[Exception] = None

        while True:
            if should_stop and should_stop():
                raise PoolStopped("Người dùng đã dừng")

            # 1. Pool đang bị chặn IP
            now = self.clock()
            if self.blocked_until and now < self.blocked_until:
                wait = self.blocked_until - now
                self._emit(f"IP đang bị Gemini tạm chặn, nghỉ {wait / 60:.1f} phút...")
                await self._sleep_checked(wait, should_stop)
                continue

            # 2. Chọn tài khoản kế tiếp
            async with self._lock:
                acc = self._next_available()
                if acc is None:
                    recovery = self._earliest_recovery()
                    self._save_usage()
                    if recovery is None:
                        raise AllAccountsExhausted(
                            "Toàn bộ tài khoản Gemini đã hết hạn mức hoặc cookie hết hạn. "
                            "Hãy chạy lại sau hoặc cập nhật accounts.json."
                        )
                else:
                    # Giãn cách giữa các request
                    gap = random.uniform(self.settings["min_delay"], self.settings["max_delay"])
                    wait = self._last_request + gap - self.clock()
                    if wait > 0:
                        await self.sleep(wait)
                    self._last_request = self.clock()

            if acc is None:
                wait = max(1.0, recovery - self.clock())
                self._emit(f"Mọi tài khoản đang nghỉ tạm, chờ {wait / 60:.1f} phút...")
                await self._sleep_checked(wait, should_stop)
                continue

            # 3. Gọi Gemini
            try:
                client = await self._get_client(acc)
                if acc.quota_remaining is not None and acc.quota_remaining <= 0:
                    self._mark_exhausted(acc)
                    acc.last_error = "Hạn mức Flash = 0"
                    self._emit(f"[{acc.name}] đã hết hạn mức (theo quota), chuyển tài khoản.")
                    self._save_usage()
                    continue
                resp = await client.generate_content(prompt, model=model, temporary=True)
                text = (resp.text or "").strip()
                if not text:
                    raise RuntimeError("Gemini trả về rỗng")
                acc.requests_today += 1
                acc.consecutive_errors = 0
                acc.last_error = None
                self._block_level = 0
                acc.since_quota_check += 1
                if acc.since_quota_check >= 10:
                    await self._refresh_quota(acc)
                if acc.daily_limit and acc.requests_today >= acc.daily_limit:
                    acc.status = "exhausted"
                    acc.until = None  # hồi lại khi sang ngày mới
                    self._emit(f"[{acc.name}] đã dùng hết {acc.daily_limit} request/ngày, chuyển tài khoản.")
                self._save_usage()
                return text

            except UsageLimitExceededError as e:
                await self._refresh_quota(acc)
                self._mark_exhausted(acc)
                acc.last_error = f"Hết hạn mức: {e}"
                self._emit(f"[{acc.name}] hết hạn mức, chuyển sang tài khoản khác.")
                last_exc = e
            except AuthError as e:
                acc.status = "auth_failed"
                acc.until = None
                acc.last_error = f"Cookie lỗi/hết hạn: {e}"
                await self._close_client(acc)
                self._emit(f"[{acc.name}] cookie hết hạn, bỏ qua tài khoản này.")
                last_exc = e
            except TemporarilyBlockedError as e:
                steps = self.settings["ip_block_minutes"]
                minutes = steps[min(self._block_level, len(steps) - 1)]
                self._block_level += 1
                self.blocked_until = self.clock() + minutes * 60
                acc.last_error = f"IP bị chặn tạm thời: {e}"
                self._emit(f"Gemini chặn IP tạm thời (429). Cả pool nghỉ {minutes} phút.")
                last_exc = e
                self._save_usage()
                continue  # không tính vào số lần thử
            except Exception as e:
                acc.consecutive_errors += 1
                acc.last_error = f"{type(e).__name__}: {e}"
                if "UNAUTHENTICATED" in str(e).upper():
                    # Phiên hỏng (thường do cookie __Secure-1PSIDTS bị xoay ở trình duyệt/tiến trình khác).
                    # Đóng client để lần tới đăng nhập lại từ cookie trong accounts.json.
                    await self._close_client(acc)
                    self._emit(f"[{acc.name}] phiên đăng nhập mất hiệu lực, sẽ đăng nhập lại.")
                if acc.consecutive_errors >= self.settings["max_consecutive_errors"]:
                    acc.status = "cooldown"
                    acc.until = self.clock() + self.settings["cooldown_minutes"] * 60
                    await self._close_client(acc)
                    self._emit(f"[{acc.name}] lỗi liên tiếp, tạm nghỉ {self.settings['cooldown_minutes']} phút.")
                last_exc = e

            self._save_usage()
            attempts += 1
            if attempts >= limit:
                raise RuntimeError(f"Gọi Gemini thất bại sau {attempts} lần thử: {last_exc}")

    async def close(self):
        for a in self.accounts:
            await self._close_client(a)


_pool: Optional[AccountPool] = None


def get_pool() -> AccountPool:
    global _pool
    if _pool is None:
        _pool = AccountPool()
    return _pool
