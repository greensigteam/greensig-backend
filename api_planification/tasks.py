"""
Celery tasks for api_planification module.

NOTE: Le systeme de statuts EN_RETARD et EXPIREE a ete supprime.
Les taches restent PLANIFIEE jusqu'a demarrage explicite par l'utilisateur.

Taches restantes:
- invalidate_taches_cache: Invalide le cache des taches (utilitaire)
"""

import logging
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Cache key pour la liste des taches
CACHE_KEY_TACHES_LIST = 'taches_list_{user_id}_{params_hash}'
CACHE_TIMEOUT_TACHES = 60  # 1 minute


def invalidate_taches_cache():
    """Invalide le cache de la liste des taches pour tous les utilisateurs."""
    try:
        # Supprimer toutes les cles commencant par 'taches_list_'
        cache.delete_pattern('greensig:taches_list_*')
    except AttributeError:
        # Si delete_pattern n'est pas disponible
        logger.warning("Cache backend doesn't support delete_pattern, skipping cache invalidation")
    except Exception as e:
        logger.warning(f"Failed to invalidate taches cache: {e}")


# ==============================================================================
# TACHES CELERY DESACTIVEES
# ==============================================================================
# Les taches suivantes ont ete supprimees car le systeme de statuts
# EN_RETARD et EXPIREE n'existe plus.
#
# Les taches restent PLANIFIEE jusqu'a ce que l'utilisateur les demarre
# explicitement. Une distribution ne peut pas etre demarree avant sa date
# planifiee.
# ==============================================================================


@shared_task(bind=True, name='api_planification.tasks.refresh_all_task_statuses')
def refresh_all_task_statuses(self):
    """
    DESACTIVEE: Cette tache ne fait plus rien.

    Anciennement: Mettait a jour les statuts EN_RETARD et EXPIREE.
    Maintenant: Le systeme simplifie ne calcule plus automatiquement ces statuts.

    Cette tache est conservee pour eviter les erreurs si elle est encore
    programmee dans Celery Beat, mais elle ne fait rien.
    """
    logger.info("refresh_all_task_statuses: DESACTIVEE (systeme simplifie)")
    return {
        'success': True,
        'message': 'Task disabled - simplified status system',
        'late_distributions': 0,
        'late_tasks': 0,
        'expired_tasks': 0,
        'timestamp': timezone.now().isoformat(),
    }


@shared_task(bind=True, name='api_planification.tasks.update_late_distributions')
def update_late_distributions(self):
    """
    DESACTIVEE: Cette tache ne fait plus rien.

    Anciennement: Marquait les distributions comme EN_RETARD.
    Maintenant: Le statut EN_RETARD n'existe plus.
    """
    logger.info("update_late_distributions: DESACTIVEE (systeme simplifie)")
    return {
        'success': True,
        'message': 'Task disabled - EN_RETARD status removed',
        'updated_distributions': 0,
        'updated_tasks': 0,
    }


@shared_task(bind=True, name='api_planification.tasks.fix_inconsistent_distributions')
def fix_inconsistent_distributions(self):
    """
    DESACTIVEE: Cette tache ne fait plus rien.

    Anciennement: Corrigeait les distributions des taches EXPIREE.
    Maintenant: Le statut EXPIREE n'existe plus.
    """
    logger.info("fix_inconsistent_distributions: DESACTIVEE (systeme simplifie)")
    return {
        'success': True,
        'message': 'Task disabled - EXPIREE status removed',
        'fixed_count': 0,
    }


@shared_task(bind=True, name='api_planification.tasks.mark_expired_tasks')
def mark_expired_tasks(self):
    """
    DESACTIVEE: Cette tache ne fait plus rien.

    Anciennement: Marquait les taches comme EXPIREE.
    Maintenant: Le statut EXPIREE n'existe plus.
    """
    logger.info("mark_expired_tasks: DESACTIVEE (systeme simplifie)")
    return {
        'success': True,
        'message': 'Task disabled - EXPIREE status removed',
        'expired_count': 0,
    }
