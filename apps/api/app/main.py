"""ASGI entry point; routes and application factory live in app.api.routes."""
import sys
from .api import routes
sys.modules[__name__] = routes
