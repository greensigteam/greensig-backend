"""
GreenSIG Django project initialization.

This module ensures Celery is loaded when Django starts.
"""

# Import celery app so it's loaded when Django starts
from .celery import app as celery_app

__all__ = ('celery_app',)
