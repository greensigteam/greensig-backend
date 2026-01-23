"""
Celery configuration for greensig_web project.

This module configures Celery for asynchronous task processing:
- Background exports (PDF, Excel, GeoJSON)
- Periodic tasks via Celery Beat (database scheduler)
- Async notifications
"""

import os
from celery import Celery

# Set the default Django settings module for Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')

# Create Celery app
app = Celery('greensig_web')

# Load config from Django settings, using CELERY_ namespace
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all registered Django apps
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task to verify Celery is working."""
    print(f'Request: {self.request!r}')
