from contextvars import ContextVar

progress_sink = ContextVar("agent_progress", default=None)

def progress(role, status):
    sink = progress_sink.get()
    if sink:
        sink(role, status)
