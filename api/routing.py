"""
Routing WebSocket pour les notifications temps reel.

URL: ws://host/ws/notifications/?token=<jwt_token>
"""

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/notifications/$', consumers.NotificationConsumer.as_asgi()),
]