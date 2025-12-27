"""
Custom pagination classes for GreenSIG API.
"""
from rest_framework.pagination import PageNumberPagination


class CustomPageNumberPagination(PageNumberPagination):
    """
    Pagination personnalisée permettant au client de spécifier la taille de page.

    - page_size par défaut: 50
    - page_size maximum: 10000
    - Paramètre query: page_size (ex: ?page_size=100)

    Utilisé par tous les ViewSets de l'API pour permettre au frontend
    de récupérer tous les résultats quand nécessaire.
    """
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 10000
