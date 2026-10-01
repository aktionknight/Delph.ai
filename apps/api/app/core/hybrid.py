"""Configured primary provider followed by another credentialed provider."""
import os
import time

from .errors import AgentError, ProviderError
from .events import progress
from .gemini import GeminiProvider
from .groq import GroqProvider
from .routing import RoutingBudget, enabled


class HybridProvider(GeminiProvider):
    def __init__(self, transport=None, groq_transport=None):
        super().__init__(transport)
        self.groq = GroqProvider(groq_transport)

    def generate(self, role, instructions, payload, schema):
        legacy = "REPAIR_PROVIDER" if payload.get("operation") == "repair" else "WRITER_PROVIDER"
        configured = os.getenv(f"{role.upper()}_PROVIDER")
        if configured is None and role == "creative":
            configured = os.getenv(legacy)
        provider = (configured or "gemini").lower()
        if provider not in {"gemini", "groq"}:
            raise AgentError(f"Unsupported provider for {role}. Select gemini or groq.")
        order = [provider]
        if enabled("AI_FALLBACK_ENABLED") and enabled("AI_PROVIDER_FALLBACK_ENABLED"):
            order.append("groq" if provider == "gemini" else "gemini")
        budget = RoutingBudget()
        attempts = []
        started = time.monotonic()
        for index, candidate in enumerate(order):
            if not os.getenv("GEMINI_API_KEY" if candidate == "gemini" else "GROQ_API_KEY"):
                attempts.append({"provider": candidate, "status": "skipped", "reason": "missing_key"})
                continue
            # Leave time and an attempt for a credentialed secondary provider.
            has_secondary = index == 0 and len(order) > 1 and bool(os.getenv("GROQ_API_KEY" if candidate == "gemini" else "GEMINI_API_KEY"))
            budget.reserve_seconds = min(45, max(0, (budget.deadline - time.monotonic()) / 3)) if has_secondary else 0
            saved_attempt = 1 if has_secondary and budget.remaining_attempts > 1 else 0
            budget.remaining_attempts -= saved_attempt
            try:
                output, run = (super().generate(role, instructions, payload, schema, budget=budget) if candidate == "gemini" else
                               self.groq.generate(role, instructions, payload, schema, budget=budget))
                run["attempts"] = attempts + run["attempts"]
                run["duration_ms"] = round((time.monotonic() - started) * 1000)
                return output, run
            except ProviderError as exc:
                attempts.extend(exc.attempts)
                if not exc.recoverable:
                    raise
                progress(role, "provider_fallback")
            finally:
                budget.remaining_attempts += saved_attempt
        if all(a.get("reason") == "missing_key" for a in attempts):
            raise AgentError("Set GEMINI_API_KEY or GROQ_API_KEY to run the AI agents.")
        raise ProviderError("All configured AI model/provider fallbacks are unavailable. Try again after quota resets or add capacity with another provider key.",
                            reason="exhausted", attempts=attempts)
