# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Attestplane Contributors
"""Thread-safe LLM provider router with 429-triggered blacklist.

Provider priority (per Opus-V1 arch review 2026-05-30):
  implement: modelscope → deepseek
  fix_ci:    modelscope → deepseek
  review_pr: deepseek only (ERNIE-Speed coding gap too large)

Blacklist TTL:
  volc    → until next 00:00 Asia/Shanghai (daily quota window)
  baidu   → 60 s (QPS-level rate limit)
  deepseek → 60 s (paid fallback; rare)
"""

import logging
import os
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

_log = logging.getLogger("autodev.llm_router")
_CST = timezone(timedelta(hours=8))


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str
    api_key_env: str
    model_env: str
    default_model: str
    # None = blacklist until next 00:00 CST; int = blacklist for N seconds
    blacklist_ttl: int | None

    @property
    def api_key(self) -> str:
        return os.environ.get(self.api_key_env, "")

    @property
    def model(self) -> str:
        return os.environ.get(self.model_env, self.default_model)

    def is_configured(self) -> bool:
        return bool(self.api_key)


_PROVIDERS: dict[str, Provider] = {
    "modelscope": Provider(
        name="modelscope",
        base_url="https://api-inference.modelscope.cn/v1",
        api_key_env="MODELSCOPE_API_KEY",
        model_env="MODELSCOPE_MODEL",
        default_model="Qwen/Qwen2.5-Coder-32B-Instruct",
        blacklist_ttl=60,
    ),
    "deepseek": Provider(
        name="deepseek",
        base_url="https://api.deepseek.com",
        api_key_env="DEEPSEEK_API_KEY",
        model_env="DEEPSEEK_MODEL",  # L5: was QWEN_MODEL (legacy); set DEEPSEEK_MODEL to override
        default_model="deepseek-v4-flash",
        blacklist_ttl=60,
    ),
}

_IMPLEMENT_ORDER = ["modelscope", "deepseek"]
_FIX_CI_ORDER = ["modelscope", "deepseek"]
_REVIEW_ORDER = ["deepseek"]

# Pre-compiled so is_rate_limit_error doesn't recompile on every hot retry call. (M10 fix)
_RE_429 = re.compile(r"\b429\b")

# QPS-level rate limit → short blacklist (ttl seconds).
_RATE_LIMIT_SIGNALS = (
    "rate limit",
    "ratelimit",
    "too many requests",
)

# Daily-quota exhausted → blacklist until next 00:00 CST (None TTL).
# Patterns are intentionally narrow to avoid false-positive blacklisting from benign
# error messages that happen to contain common words like "billing". (M1 fix)
_QUOTA_SIGNALS = (
    "quota exceeded",
    "insufficient_quota",
    "insufficient quota",
    "account balance is insufficient",
    "no remaining credits",
    "credit balance insufficient",
)


def is_rate_limit_error(err: str) -> bool:
    """Return True if err signals any provider throttle (QPS or daily quota).

    Intentionally includes _QUOTA_SIGNALS: both QPS rate-limits and daily-quota
    exhaustion should trigger provider rotation / blacklist logic. Callers that
    need to distinguish quota exhaustion from pure QPS limiting should call
    is_quota_exhausted() separately.
    """
    lower = err.lower()
    if _RE_429.search(lower):  # pre-compiled; avoids per-call compile on hot retry path (M10 fix)
        return True
    return any(s in lower for s in _RATE_LIMIT_SIGNALS) or any(s in lower for s in _QUOTA_SIGNALS)


def is_quota_exhausted(err: str) -> bool:
    """Daily quota exhausted — should blacklist until next reset, not just 60s."""
    lower = err.lower()
    return any(s in lower for s in _QUOTA_SIGNALS)


class LLMRouter:
    """Singleton-per-process; thread-safe via threading.Lock."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._blacklist: dict[str, datetime] = {}

    def providers_for(self, activity_type: str) -> list[Provider]:
        """Return ordered, non-blacklisted, configured providers."""
        if activity_type == "implement":
            order = _IMPLEMENT_ORDER
        elif activity_type == "fix_ci":
            order = _FIX_CI_ORDER
        elif activity_type == "review":
            order = _REVIEW_ORDER
        else:
            raise ValueError(f"unknown activity_type {activity_type!r} — expected implement/fix_ci/review")
        now = datetime.now(timezone.utc)
        with self._lock:
            # Inline availability check (no nested lock — threading.Lock is non-reentrant).
            available = []
            for n in order:
                exp = self._blacklist.get(n)
                if exp is not None and exp <= now:
                    self._blacklist.pop(n, None)
                    exp = None
                if exp is not None:
                    continue  # still blacklisted
                if _PROVIDERS[n].is_configured():
                    available.append(_PROVIDERS[n])
            if not available:
                # All providers blacklisted — clear the blacklist for the first configured
                # one and use it as emergency fallback. Without clearing, the caller would
                # get a 429, retry, and hit the same blacklisted provider forever. (H5 fix)
                # Only the first provider is cleared; the others remain blacklisted so they
                # are skipped on this call. (L6 clarification)
                for n in order:
                    p = _PROVIDERS[n]
                    if p.is_configured():
                        self._blacklist.pop(n, None)
                        available = [p]
                        _log.warning(
                            "all providers blacklisted; force-clearing %s as emergency fallback", n
                        )
                        break
        return available

    def blacklist(self, name: str, *, until_midnight: bool = False) -> None:
        p = _PROVIDERS.get(name)
        if p is None:
            return
        with self._lock:
            if until_midnight or p.blacklist_ttl is None:
                now_cst = datetime.now(_CST)
                expires = (now_cst + timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                ).astimezone(timezone.utc)
            else:
                expires = datetime.now(timezone.utc) + timedelta(seconds=p.blacklist_ttl)
            self._blacklist[name] = expires
        _log.warning(
            "provider %s blacklisted until %s",
            name,
            expires.isoformat(),
        )

    def blacklist_state(self) -> dict[str, str]:
        with self._lock:
            return {k: v.isoformat() for k, v in self._blacklist.items()}


# Process-level singleton (safe: Temporal worker is a single long-lived process)
router = LLMRouter()
