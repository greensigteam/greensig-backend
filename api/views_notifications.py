"""
Views pour l'API de notifications.

Endpoints:
- GET /api/notifications/ - Liste des notifications de l'utilisateur
- GET /api/notifications/?all=true - (Admin) Liste de TOUTES les notifications
- GET /api/notifications/unread-count/ - Nombre de notifications non lues
- POST /api/notifications/<id>/mark-read/ - Marquer une notification comme lue
- POST /api/notifications/mark-all-read/ - Marquer toutes les notifications comme lues
- DELETE /api/notifications/<id>/ - Supprimer une notification
"""

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone

from .models import Notification
from .serializers import NotificationSerializer, AdminNotificationSerializer


def is_admin(user):
    """Verifie si l'utilisateur est admin."""
    return user.roles_utilisateur.filter(role__nom_role='ADMIN').exists() or user.is_superuser


class NotificationListView(generics.ListAPIView):
    """
    Liste les notifications de l'utilisateur connecte.

    GET /api/notifications/
    Query params:
    - lu: true/false - Filtrer par statut de lecture
    - type: string - Filtrer par type de notification
    - limit: int - Nombre max de resultats (defaut: 50)
    - offset: int - Decalage pour pagination (defaut: 0)
    - all: true - (Admin seulement) Voir TOUTES les notifications du systeme
    - role: string - (Admin + all=true) Filtrer par role destinataire (ADMIN, SUPERVISEUR, CLIENT)
    """
    permission_classes = [IsAuthenticated]
    # Desactiver la pagination par defaut - on gere manuellement avec limit/offset
    pagination_class = None

    def get_serializer_class(self):
        # Utiliser AdminNotificationSerializer si admin demande toutes les notifs
        # OU pour voir les destinataires d'actions effectuees (by_me)
        show_all = self.request.query_params.get('all') == 'true'
        show_by_me = self.request.query_params.get('by_me') == 'true'

        if (show_all and is_admin(self.request.user)) or show_by_me:
            return AdminNotificationSerializer
        return NotificationSerializer

    def get_queryset(self):
        user = self.request.user
        show_all = self.request.query_params.get('all') == 'true'
        show_by_me = self.request.query_params.get('by_me') == 'true'

        # Mes actions (ce que j'ai declenche)
        if show_by_me:
            queryset = Notification.objects.filter(
                acteur=user
            ).select_related('destinataire').order_by('-created_at')
        
        # Admin peut voir toutes les notifications
        elif show_all and is_admin(user):
            queryset = Notification.objects.all().select_related(
                'acteur', 'destinataire'
            ).order_by('-created_at')

            # Filtre par role du destinataire
            role_filter = self.request.query_params.get('role')
            if role_filter:
                if role_filter == 'SUPERVISEUR':
                    queryset = queryset.filter(destinataire__superviseur_profile__isnull=False)
                elif role_filter == 'CLIENT':
                    queryset = queryset.filter(destinataire__client_profile__isnull=False)
                elif role_filter == 'ADMIN':
                    queryset = queryset.filter(
                        destinataire__roles_utilisateur__role__nom_role='ADMIN'
                    ).distinct()
        else:
            # Utilisateur normal: seulement ses propres notifications (Inbox)
            # EXCLU l'auto-notification : ce qu'on fait soi-meme va dans "Mes operations"
            queryset = Notification.objects.filter(
                destinataire=user
            ).exclude(
                acteur=user
            ).select_related('acteur').order_by('-created_at')

        # Filtre par statut de lecture
        lu = self.request.query_params.get('lu')
        if lu is not None:
            queryset = queryset.filter(lu=lu.lower() == 'true')

        # Filtre par type
        type_notif = self.request.query_params.get('type')
        if type_notif:
            queryset = queryset.filter(type_notification=type_notif)

        # Pagination: offset et limite
        offset = self.request.query_params.get('offset', 0)
        limit = self.request.query_params.get('limit', 50)
        try:
            offset = max(int(offset), 0)
            limit = min(int(limit), 200)  # Max 200
        except (TypeError, ValueError):
            offset = 0
            limit = 50

        return queryset[offset:offset + limit]


class UnreadCountView(APIView):
    """
    Retourne le nombre de notifications non lues.

    GET /api/notifications/unread-count/
    Response: {"count": 5}
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Compter seulement les notifications non lues qui ne sont pas des auto-notifications
        count = Notification.objects.filter(
            destinataire=request.user,
            lu=False
        ).exclude(
            acteur=request.user
        ).count()
        return Response({'count': count})


class MarkReadView(APIView):
    """
    Marque une notification comme lue.

    POST /api/notifications/<id>/mark-read/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            notification = Notification.objects.get(
                pk=pk,
                destinataire=request.user
            )
            notification.marquer_comme_lu()
            return Response({'success': True, 'id': pk})
        except Notification.DoesNotExist:
            return Response(
                {'error': 'Notification non trouvee'},
                status=status.HTTP_404_NOT_FOUND
            )


class MarkAllReadView(APIView):
    """
    Marque toutes les notifications comme lues.

    POST /api/notifications/mark-all-read/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        count = Notification.objects.filter(
            destinataire=request.user,
            lu=False
        ).update(lu=True, date_lecture=timezone.now())

        return Response({'success': True, 'count': count})


class NotificationDeleteView(generics.DestroyAPIView):
    """
    Supprime une notification.

    DELETE /api/notifications/<id>/
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(destinataire=self.request.user)


class SendTestNotificationView(APIView):
    """
    Envoie une notification de test a l'utilisateur connecte.

    POST /api/notifications/test/
    Body (optionnel): {"titre": "...", "message": "..."}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from api.services.notifications import NotificationService

        titre = request.data.get('titre', 'Notification de test')
        message = request.data.get('message', 'Ceci est une notification de test!')

        result = NotificationService.send(
            type_notification='info',
            titre=titre,
            message=message,
            recipients=[request.user.id],
            priorite='normal',
            data={'test': True}
        )

        return Response({
            'success': result,
            'message': 'Notification envoyee' if result else 'Echec envoi'
        })