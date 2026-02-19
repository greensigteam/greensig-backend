"""
Gestion centralisée du cache Redis.

Utilise un système de **compteurs de version** pour l'invalidation,
compatible avec tous les backends Django (natif et django-redis).

Principe :
  - Chaque domaine de cache a un compteur de version (clé persistante dans Redis).
  - Les clés de cache incluent la version courante du domaine.
  - Invalider = incrémenter le compteur → les anciennes clés deviennent orphelines
    et expirent naturellement après leur TTL.

Domaines :
  - TACHES    : liste des tâches + distributions
  - KPIS      : indicateurs de performance
  - REPORTING : statistiques globales (dashboard)
  - STATISTICS: inventaire des objets GIS
  - FILTERS   : options de filtrage dynamiques
"""

import hashlib
import json
import logging

from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)

# ==============================================================================
# CLÉS DE VERSION PAR DOMAINE
# ==============================================================================

VERSION_KEYS = {
    'TACHES': 'cache_version:taches',
    'KPIS': 'cache_version:kpis',
    'REPORTING': 'cache_version:reporting',
    'STATISTICS': 'cache_version:statistics',
    'FILTERS': 'cache_version:filters',
}

# ==============================================================================
# TTL PAR DOMAINE (secondes)
# ==============================================================================

CACHE_TTL = {
    'TACHES': 300,      # 5 minutes
    'KPIS': 300,         # 5 minutes (courant), 3600 (mois passés — géré dans la vue)
    'REPORTING': 300,    # 5 minutes
    'STATISTICS': 300,   # 5 minutes
    'FILTERS': 300,      # 5 minutes
}


# ==============================================================================
# API PUBLIQUE
# ==============================================================================

def get_cache_version(domain: str) -> int:
    """Retourne la version courante d'un domaine de cache."""
    key = VERSION_KEYS.get(domain)
    if not key:
        raise ValueError(f"Domaine de cache inconnu : {domain}")
    version = cache.get(key)
    if version is None:
        # timeout=None → ne jamais expirer (Django: None = forever, 0 = don't cache)
        cache.set(key, 0, timeout=None)
        return 0
    return version


def make_cache_key(domain: str, *parts) -> str:
    """Construit une clé de cache versionnée.

    Exemples:
        make_cache_key('TACHES', user_id, role, params_hash)
        → 'taches:v3:42:ADMIN:a1b2c3d4'

        make_cache_key('KPIS', '2026-01', 'all', 'all')
        → 'kpis:v7:2026-01:all:all'
    """
    version = get_cache_version(domain)
    prefix = domain.lower()
    parts_str = ':'.join(str(p) for p in parts)
    return f'{prefix}:v{version}:{parts_str}'


def get_cache_ttl(domain: str) -> int:
    """Retourne le TTL configuré pour un domaine."""
    return CACHE_TTL.get(domain, 300)


def cache_get(domain: str, *parts):
    """Récupère une valeur du cache (versionnée)."""
    key = make_cache_key(domain, *parts)
    return cache.get(key)


def cache_set(domain: str, *parts, data, ttl: int | None = None):
    """Stocke une valeur dans le cache (versionnée).

    Args:
        domain: Le domaine de cache
        *parts: Les parties de la clé (après le domaine et la version)
        data: Les données à stocker
        ttl: TTL en secondes (utilise le TTL du domaine par défaut)
    """
    key = make_cache_key(domain, *parts)
    timeout = ttl if ttl is not None else get_cache_ttl(domain)
    cache.set(key, data, timeout)


def invalidate(*domains: str):
    """Invalide un ou plusieurs domaines de cache.

    Incrémente le compteur de version de chaque domaine spécifié.
    Les anciennes entrées deviennent orphelines et expirent naturellement.

    Exemples:
        invalidate('TACHES')
        invalidate('TACHES', 'KPIS', 'REPORTING')
    """
    for domain in domains:
        key = VERSION_KEYS.get(domain)
        if not key:
            logger.warning(f"Domaine de cache inconnu : {domain}")
            continue
        # Lecture manuelle + écriture pour garantir timeout=None (cache forever).
        # On évite cache.incr() car Django RedisCache sérialise les valeurs
        # (pickle), ce qui fait échouer le INCRBY natif de Redis.
        version = cache.get(key)
        if version is not None:
            cache.set(key, version + 1, timeout=None)
        else:
            cache.set(key, 1, timeout=None)


def hash_params(params: dict) -> str:
    """Hash un dictionnaire de paramètres pour l'inclure dans une clé de cache."""
    params_str = json.dumps(params, sort_keys=True, default=str)
    return hashlib.md5(params_str.encode()).hexdigest()[:8]


# ==============================================================================
# GRAPHE DE DÉPENDANCES : mutations → domaines à invalider
# ==============================================================================

def invalidate_on_tache_mutation():
    """Appelé après create/update/delete d'une Tache."""
    invalidate('TACHES', 'KPIS', 'REPORTING')


def invalidate_on_distribution_mutation():
    """Appelé après create/update/delete d'une Distribution."""
    invalidate('TACHES', 'KPIS', 'REPORTING')


def invalidate_on_reclamation_mutation():
    """Appelé après create/update/delete d'une Réclamation."""
    invalidate('KPIS', 'REPORTING')


def invalidate_on_gis_object_mutation():
    """Appelé après create/update/delete d'un Objet GIS (Arbre, Gazon, Puits, etc.)."""
    invalidate('STATISTICS', 'FILTERS')


def invalidate_on_site_mutation():
    """Appelé après create/update/delete d'un Site ou SousSite."""
    invalidate('STATISTICS', 'FILTERS', 'REPORTING')


def invalidate_on_team_mutation():
    """Appelé après create/update/delete d'une Équipe, Opérateur ou Superviseur."""
    invalidate('REPORTING')
