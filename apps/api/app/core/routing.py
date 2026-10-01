"""Ordered, bounded model routing with per-process cooldowns and safe provenance."""
import os
from threading import Lock
import time

from .errors import AgentError, ProviderError
from .events import progress

GEMINI_DEFAULT = "gemini-3.1-flash-lite"
GEMINI_FALLBACKS = "gemini-3.5-flash-lite,gemini-3.8-flash,gemini-3.5-flash"


def enabled(name, default=True):
    return os.getenv(name, "true" if default else "false").lower() == "true"


def setting(name, default, lower, upper):
    try:
        value = float(os.getenv(name, str(default)))
        if not lower <= value <= upper:
            raise ValueError()
        return value
    except ValueError as exc:
        raise AgentError(f"{name} must be between {lower} and {upper}.") from exc


def models(provider, role, primary, defaults):
    if not enabled("AI_FALLBACK_ENABLED"):
        return [primary]
    configured = os.getenv(f"{provider}_{role.upper()}_FALLBACK_MODELS")
    if configured is None:
        configured = os.getenv(f"{provider}_FALLBACK_MODELS", defaults)
    # Cap fanout and remove duplicates while preserving configured order.
    return list(dict.fromkeys([primary, *(m.strip() for m in configured.split(",") if m.strip())]))[:5]


class RoutingBudget:
    def __init__(self):
        self.deadline = time.monotonic() + setting("AI_REQUEST_TIMEOUT_SECONDS", 150, 10, 600)
        self.remaining_attempts = int(setting("AI_MAX_MODEL_ATTEMPTS", 7, 1, 10))
        self.reserve_seconds = 0

    def take(self):
        seconds = self.deadline - time.monotonic() - self.reserve_seconds
        if seconds <= 0 or self.remaining_attempts <= 0:
            raise ProviderError("Agent request exhausted its fallback budget. Retry when provider capacity is available.", reason="budget")
        self.remaining_attempts -= 1
        return min(seconds, setting("AI_MODEL_TIMEOUT_SECONDS", 45, 5, 120))


class ModelPool:
    def __init__(self, provider):
        self.provider = provider
        self.cooldowns = {}
        self.lock = Lock()

    def run(self, role, candidates, invoke, budget=None):
        budget = budget or RoutingBudget()
        started = time.monotonic()
        attempts = []
        last = None
        for model in candidates:
            with self.lock:
                cooling = self.cooldowns.get(model, 0) > time.monotonic()
            if cooling:
                attempts.append({"provider": self.provider, "model": model, "status": "skipped", "reason": "cooldown"})
                continue
            try:
                timeout = budget.take()
            except ProviderError as exc:
                exc.attempts = attempts
                raise
            attempt_started = time.monotonic()
            try:
                value, run = invoke(model, timeout)
                attempts.append({"provider": self.provider, "model": model, "status": "completed",
                                 "duration_ms": round((time.monotonic() - attempt_started) * 1000)})
                run["attempts"] = attempts
                run["duration_ms"] = round((time.monotonic() - started) * 1000)
                return value, run
            except ProviderError as exc:
                attempts.append({"provider": self.provider, "model": model, "status": "failed", "reason": exc.reason,
                                 "duration_ms": round((time.monotonic() - attempt_started) * 1000)})
                exc.attempts = attempts
                if not exc.recoverable:
                    raise
                last = exc
                if exc.cooldown:
                    with self.lock:
                        self.cooldowns[model] = time.monotonic() + exc.cooldown
                progress(role, "fallback")
        message = str(last) if last else "All configured models are temporarily cooling down."
        raise ProviderError(f"{self.provider.title()} model chain exhausted: {message}", reason="exhausted", attempts=attempts)
