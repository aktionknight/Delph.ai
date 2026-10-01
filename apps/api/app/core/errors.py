class AgentError(Exception):
    """Safe provider or agent contract failure."""
    pass


class ProviderError(AgentError):
    """Classified failures for safe model/provider failover."""
    def __init__(self, message, *, reason, recoverable=True, cooldown=0, attempts=None):
        super().__init__(message)
        self.reason = reason
        self.recoverable = recoverable
        self.cooldown = cooldown
        self.attempts = attempts or []
