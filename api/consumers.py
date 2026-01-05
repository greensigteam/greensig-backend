"""
WebSocket Consumers pour les notifications temps reel.

Architecture:
- Chaque utilisateur connecte rejoint un groupe 'notifications_user_{user_id}'
- Les notifications sont envoyees au groupe de l'utilisateur cible
- Le consumer gere la reception et l'envoi de messages WebSocket
"""

import json
import logging
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger(__name__)


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    """
    Consumer WebSocket pour les notifications temps reel.

    Fonctionnalites:
    - Connexion authentifiee (JWT requis)
    - Reception des notifications en temps reel
    - Marquer les notifications comme lues
    - Recuperer les notifications non lues au connect

    URL: ws://host/ws/notifications/?token=<jwt_token>
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None
        self.group_name = None

    async def connect(self):
        """Gere la connexion WebSocket."""
        self.user = self.scope.get('user')

        # Verifier l'authentification
        if not self.user or isinstance(self.user, AnonymousUser):
            logger.warning("[WS] Connexion refusee: utilisateur non authentifie")
            await self.close(code=4001)  # Code personnalise: Non authentifie
            return

        # Nom du groupe pour cet utilisateur
        self.group_name = f"notifications_user_{self.user.id}"

        # Rejoindre le groupe
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        # Accepter la connexion
        await self.accept()

        logger.info(f"[WS] Connexion acceptee: {self.user.email} (groupe: {self.group_name})")

        # Envoyer le nombre de notifications non lues
        unread_count = await self.get_unread_count()
        await self.send_json({
            'type': 'connection_established',
            'message': 'Connecte aux notifications',
            'unread_count': unread_count,
        })

    async def disconnect(self, close_code):
        """Gere la deconnexion WebSocket."""
        if self.group_name:
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
            logger.info(f"[WS] Deconnexion: {self.user.email if self.user else 'Unknown'}")

    async def receive_json(self, content):
        """
        Gere les messages recus du client.

        Messages supportes:
        - {'action': 'mark_read', 'notification_id': <id>}
        - {'action': 'mark_all_read'}
        - {'action': 'get_unread'}
        - {'action': 'ping'}
        """
        action = content.get('action')

        if action == 'mark_read':
            notification_id = content.get('notification_id')
            if notification_id:
                success = await self.mark_notification_read(notification_id)
                await self.send_json({
                    'type': 'mark_read_response',
                    'notification_id': notification_id,
                    'success': success,
                })

        elif action == 'mark_all_read':
            count = await self.mark_all_notifications_read()
            await self.send_json({
                'type': 'mark_all_read_response',
                'count': count,
            })

        elif action == 'get_unread':
            notifications = await self.get_unread_notifications()
            await self.send_json({
                'type': 'unread_notifications',
                'notifications': notifications,
                'count': len(notifications),
            })

        elif action == 'ping':
            await self.send_json({
                'type': 'pong',
                'timestamp': content.get('timestamp'),
            })

        else:
            logger.warning(f"[WS] Action inconnue: {action}")

    async def notification_message(self, event):
        """
        Handler pour les messages de notification envoyes au groupe.
        Appele quand NotificationService envoie une notification.
        """
        notification = event.get('notification')
        if notification:
            await self.send_json({
                'type': 'new_notification',
                'notification': notification,
            })

    # =========================================================================
    # METHODES DATABASE
    # =========================================================================

    @database_sync_to_async
    def get_unread_count(self):
        """Retourne le nombre de notifications non lues."""
        from api.models import Notification
        return Notification.objects.filter(
            destinataire=self.user,
            lu=False
        ).count()

    @database_sync_to_async
    def get_unread_notifications(self):
        """Retourne les 50 dernieres notifications non lues."""
        from api.models import Notification
        notifications = Notification.objects.filter(
            destinataire=self.user,
            lu=False
        ).select_related('acteur').order_by('-created_at')[:50]

        return [n.to_websocket_payload() for n in notifications]

    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        """Marque une notification comme lue."""
        from api.models import Notification
        try:
            notification = Notification.objects.get(
                id=notification_id,
                destinataire=self.user
            )
            notification.marquer_comme_lu()
            return True
        except Notification.DoesNotExist:
            return False

    @database_sync_to_async
    def mark_all_notifications_read(self):
        """Marque toutes les notifications comme lues."""
        from api.models import Notification
        from django.utils import timezone

        count = Notification.objects.filter(
            destinataire=self.user,
            lu=False
        ).update(lu=True, date_lecture=timezone.now())

        return count