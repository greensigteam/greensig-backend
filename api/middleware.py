"""
Middleware pour l'authentification WebSocket via JWT.

Ce middleware extrait le token JWT de la query string ou des headers
et authentifie l'utilisateur pour les connexions WebSocket.
"""

import logging
from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

logger = logging.getLogger(__name__)


@database_sync_to_async
def get_user_from_token(token_key):
    """
    Valide le token JWT et retourne l'utilisateur associe.

    Args:
        token_key: Le token JWT brut

    Returns:
        User instance ou AnonymousUser si invalide
    """
    try:
        from api_users.models import Utilisateur

        # Valider le token
        access_token = AccessToken(token_key)
        user_id = access_token['user_id']

        # Recuperer l'utilisateur
        user = Utilisateur.objects.get(id=user_id, actif=True)
        logger.debug(f"[WS Auth] Utilisateur authentifie: {user.email}")
        return user

    except (InvalidToken, TokenError) as e:
        logger.warning(f"[WS Auth] Token invalide: {e}")
        return AnonymousUser()
    except Utilisateur.DoesNotExist:
        logger.warning(f"[WS Auth] Utilisateur non trouve pour le token")
        return AnonymousUser()
    except Exception as e:
        logger.error(f"[WS Auth] Erreur inattendue: {e}")
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """
    Middleware d'authentification JWT pour les WebSockets.

    Le token peut etre passe de deux facons:
    1. Query string: ws://host/ws/notifications/?token=<jwt_token>
    2. Header: Authorization: Bearer <jwt_token> (via le premier message)

    Usage dans asgi.py:
        application = ProtocolTypeRouter({
            "websocket": JWTAuthMiddleware(
                URLRouter(websocket_urlpatterns)
            ),
        })
    """

    async def __call__(self, scope, receive, send):
        # Extraire le token de la query string
        query_string = scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)

        token = None

        # Methode 1: Token dans la query string
        if 'token' in query_params:
            token = query_params['token'][0]
            logger.debug("[WS Auth] Token trouve dans query string")

        # Methode 2: Token dans les headers (pour certains clients)
        if not token:
            headers = dict(scope.get('headers', []))
            auth_header = headers.get(b'authorization', b'').decode()
            if auth_header.startswith('Bearer '):
                token = auth_header[7:]
                logger.debug("[WS Auth] Token trouve dans header Authorization")

        # Authentifier l'utilisateur
        if token:
            scope['user'] = await get_user_from_token(token)
        else:
            logger.debug("[WS Auth] Aucun token trouve")
            scope['user'] = AnonymousUser()

        return await super().__call__(scope, receive, send)