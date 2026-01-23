"""
Celery tasks for api_planification module.

Periodic tasks:
- refresh_all_task_statuses: Runs every 5 minutes (combines late + expired)
- update_late_distributions: Runs every 5 minutes to mark late distributions
- check_task_expiration: Runs every 5 minutes to mark expired tasks
- fix_inconsistent_distributions: Runs daily to fix data inconsistencies

⚡ All tasks are optimized to use batch SQL updates instead of N+1 loops.
"""

import logging
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Cache key pour la liste des tâches
CACHE_KEY_TACHES_LIST = 'taches_list_{user_id}_{params_hash}'
CACHE_TIMEOUT_TACHES = 60  # 1 minute


@shared_task(bind=True, name='api_planification.tasks.refresh_all_task_statuses')
def refresh_all_task_statuses(self):
    """
    ⚡ Tâche périodique principale pour rafraîchir tous les statuts.

    Combine update_late_distributions + check_task_expiration en une seule tâche
    optimisée avec des requêtes SQL batch.

    Runs every 5 minutes via Celery Beat.

    Returns:
        dict: Summary of all updates
    """
    from api_planification.models import Tache, DistributionCharge
    from django.db.models import Min, Max, Q

    now = timezone.now()
    today = now.date()
    current_time = now.time()

    try:
        with transaction.atomic():
            # ═══════════════════════════════════════════════════════════════
            # 1. DISTRIBUTIONS EN RETARD (batch update)
            # ═══════════════════════════════════════════════════════════════
            late_distributions = DistributionCharge.objects.filter(
                status='NON_REALISEE'
            ).filter(
                Q(date__lt=today) |
                Q(date=today, heure_debut__isnull=False, heure_debut__lt=current_time)
            ).update(status='EN_RETARD')

            # ═══════════════════════════════════════════════════════════════
            # 2. TÂCHES: Annoter avec dates min/max des distributions
            # ═══════════════════════════════════════════════════════════════
            taches = Tache.objects.filter(
                statut__in=['PLANIFIEE', 'EN_RETARD'],
                deleted_at__isnull=True
            ).annotate(
                first_dist_date=Min('distributions_charge__date'),
                first_dist_heure=Min('distributions_charge__heure_debut'),
                last_dist_date=Max('distributions_charge__date'),
                last_dist_heure=Max('distributions_charge__heure_fin')
            ).values(
                'id', 'statut', 'date_debut_planifiee', 'date_fin_planifiee',
                'first_dist_date', 'first_dist_heure', 'last_dist_date', 'last_dist_heure'
            )

            expired_ids = []
            late_ids = []

            for tache in taches:
                first_date = tache['first_dist_date'] or tache['date_debut_planifiee']
                first_heure = tache['first_dist_heure']
                last_date = tache['last_dist_date'] or tache['date_fin_planifiee']
                last_heure = tache['last_dist_heure']

                # Check EXPIREE
                is_expired = False
                if last_date:
                    if last_date < today:
                        is_expired = True
                    elif last_date == today and last_heure and current_time > last_heure:
                        is_expired = True

                if is_expired:
                    expired_ids.append(tache['id'])
                    continue

                # Check EN_RETARD (seulement si PLANIFIEE)
                if tache['statut'] == 'PLANIFIEE':
                    is_late = False
                    if first_date:
                        if first_date < today:
                            is_late = True
                        elif first_date == today and first_heure and current_time > first_heure:
                            is_late = True
                    if is_late:
                        late_ids.append(tache['id'])

            # ═══════════════════════════════════════════════════════════════
            # 3. BATCH UPDATES
            # ═══════════════════════════════════════════════════════════════
            expired_tasks = 0
            late_tasks = 0

            if expired_ids:
                expired_tasks = Tache.objects.filter(id__in=expired_ids).update(statut='EXPIREE')
                # Annuler les distributions actives
                DistributionCharge.objects.filter(
                    tache_id__in=expired_ids,
                    status__in=['NON_REALISEE', 'EN_RETARD']
                ).update(status='ANNULEE', motif_report_annulation='AUTRE')

            if late_ids:
                late_tasks = Tache.objects.filter(id__in=late_ids).update(statut='EN_RETARD')

            # ═══════════════════════════════════════════════════════════════
            # 4. INVALIDER LE CACHE si des changements
            # ═══════════════════════════════════════════════════════════════
            if expired_tasks > 0 or late_tasks > 0 or late_distributions > 0:
                invalidate_taches_cache()

    except Exception as e:
        logger.error(f"Error in refresh_all_task_statuses: {str(e)}")
        return {'success': False, 'error': str(e)}

    result = {
        'success': True,
        'late_distributions': late_distributions,
        'late_tasks': late_tasks,
        'expired_tasks': expired_tasks,
        'timestamp': now.isoformat(),
    }

    total = late_distributions + late_tasks + expired_tasks
    if total > 0:
        logger.info(
            f"refresh_all_task_statuses: {late_distributions} dist late, "
            f"{late_tasks} tasks late, {expired_tasks} tasks expired"
        )

    return result


def invalidate_taches_cache():
    """Invalide le cache de la liste des tâches pour tous les utilisateurs."""
    try:
        # Supprimer toutes les clés commençant par 'taches_list_'
        # Note: Cette méthode dépend du backend de cache
        cache.delete_pattern('greensig:taches_list_*')
    except AttributeError:
        # Si delete_pattern n'est pas disponible, on clear tout
        # (pas idéal mais fonctionne)
        logger.warning("Cache backend doesn't support delete_pattern, skipping cache invalidation")
    except Exception as e:
        logger.warning(f"Failed to invalidate taches cache: {e}")


@shared_task(bind=True, name='api_planification.tasks.update_late_distributions')
def update_late_distributions(self):
    """
    Periodic task to mark distributions as EN_RETARD.

    ⚡ OPTIMISÉ: Utilise des updates en batch au lieu de boucles N+1.

    Runs every 5 minutes and checks for distributions where:
    - Status is NON_REALISEE
    - The scheduled start time (date + heure_debut) has passed

    Returns:
        dict: Summary with counts of updated distributions and tasks
    """
    from api_planification.models import DistributionCharge, Tache
    from django.db.models import Q

    now = timezone.now()
    today = now.date()
    current_time = now.time()

    try:
        with transaction.atomic():
            # ⚡ BATCH UPDATE: Distributions en retard (date passée OU heure passée)
            late_distributions_query = DistributionCharge.objects.filter(
                status='NON_REALISEE'
            ).filter(
                Q(date__lt=today) |  # Date passée
                Q(date=today, heure_debut__isnull=False, heure_debut__lt=current_time)  # Heure passée
            )

            updated_distributions = late_distributions_query.update(status='EN_RETARD')

            # ⚡ BATCH UPDATE: Tâches en retard (ont des distributions en retard)
            late_task_ids = list(
                DistributionCharge.objects.filter(status='EN_RETARD')
                .values_list('tache_id', flat=True)
                .distinct()
            )

            updated_tasks = Tache.objects.filter(
                id__in=late_task_ids,
                statut='PLANIFIEE',
                deleted_at__isnull=True
            ).update(statut='EN_RETARD')

    except Exception as e:
        logger.error(f"Error in update_late_distributions: {str(e)}")
        return {
            'success': False,
            'error': str(e),
        }

    result = {
        'success': True,
        'updated_distributions': updated_distributions,
        'updated_tasks': updated_tasks,
        'timestamp': now.isoformat(),
    }

    if updated_distributions > 0 or updated_tasks > 0:
        logger.info(
            f"update_late_distributions: {updated_distributions} distributions, "
            f"{updated_tasks} tasks updated"
        )

    return result


@shared_task(bind=True, name='api_planification.tasks.fix_inconsistent_distributions')
def fix_inconsistent_distributions(self):
    """
    Daily task to fix data inconsistencies between tasks and distributions.

    Runs at midnight and performs the following corrections:

    1. Tasks marked as EXPIREE with active distributions:
       - Annule all active distributions

    2. Tasks marked as ANNULEE with active distributions:
       - Annule all active distributions

    3. Distributions past their end time still marked NON_REALISEE:
       - Mark as EN_RETARD

    4. Tasks with all distributions REALISEE but still marked EN_COURS:
       - Mark task as TERMINEE

    Returns:
        dict: Summary of all corrections made
    """
    from api_planification.models import DistributionCharge, Tache
    from api_planification.business_rules import (
        corriger_distributions_tache_expiree,
        corriger_distributions_tache_annulee,
        synchroniser_tache_apres_completion,
        STATUTS_ACTIFS,
    )
    from api_planification.constants import STATUTS_ACTIFS

    now = timezone.now()
    today = now.date()

    fixed_expired_tasks = 0
    fixed_cancelled_tasks = 0
    fixed_late_distributions = 0
    fixed_completed_tasks = 0
    errors = []

    try:
        with transaction.atomic():
            # 1. Fix expired tasks with active distributions
            expired_tasks = Tache.objects.filter(
                statut='EXPIREE',
                deleted_at__isnull=True,
                distributions_charge__status__in=STATUTS_ACTIFS
            ).distinct()

            for tache in expired_tasks:
                try:
                    count = corriger_distributions_tache_expiree(tache)
                    if count > 0:
                        fixed_expired_tasks += 1
                        logger.info(
                            f"Fixed expired task {tache.reference}: "
                            f"{count} distributions cancelled"
                        )
                except Exception as e:
                    errors.append(f"Expired task {tache.id}: {str(e)}")

            # 2. Fix cancelled tasks with active distributions
            cancelled_tasks = Tache.objects.filter(
                statut='ANNULEE',
                deleted_at__isnull=True,
                distributions_charge__status__in=STATUTS_ACTIFS
            ).distinct()

            for tache in cancelled_tasks:
                try:
                    count = corriger_distributions_tache_annulee(tache)
                    if count > 0:
                        fixed_cancelled_tasks += 1
                        logger.info(
                            f"Fixed cancelled task {tache.reference}: "
                            f"{count} distributions cancelled"
                        )
                except Exception as e:
                    errors.append(f"Cancelled task {tache.id}: {str(e)}")

            # 3. Fix distributions past their end time
            # Distributions where date < today or (date = today and heure_fin < now)
            past_distributions = DistributionCharge.objects.filter(
                status='NON_REALISEE'
            ).filter(
                date__lt=today
            )

            for dist in past_distributions:
                try:
                    dist.status = 'EN_RETARD'
                    dist.save(update_fields=['status', 'updated_at'])
                    fixed_late_distributions += 1
                except Exception as e:
                    errors.append(f"Late distribution {dist.id}: {str(e)}")

            # 4. Fix tasks with all distributions completed but still EN_COURS
            in_progress_tasks = Tache.objects.filter(
                statut='EN_COURS',
                deleted_at__isnull=True
            )

            for tache in in_progress_tasks:
                try:
                    # Check if all distributions are done
                    active_count = tache.distributions_charge.filter(
                        status__in=STATUTS_ACTIFS
                    ).count()

                    realisee_count = tache.distributions_charge.filter(
                        status='REALISEE'
                    ).count()

                    total_count = tache.distributions_charge.count()

                    # If no active distributions and at least one is completed
                    if active_count == 0 and realisee_count > 0:
                        if synchroniser_tache_apres_completion(tache):
                            fixed_completed_tasks += 1
                            logger.info(f"Fixed task {tache.reference}: marked as TERMINEE")
                except Exception as e:
                    errors.append(f"Completion task {tache.id}: {str(e)}")

    except Exception as e:
        logger.error(f"Error in fix_inconsistent_distributions: {str(e)}")
        return {
            'success': False,
            'error': str(e),
        }

    result = {
        'success': True,
        'fixed_expired_tasks': fixed_expired_tasks,
        'fixed_cancelled_tasks': fixed_cancelled_tasks,
        'fixed_late_distributions': fixed_late_distributions,
        'fixed_completed_tasks': fixed_completed_tasks,
        'errors': errors if errors else None,
        'timestamp': now.isoformat(),
    }

    total_fixes = (
        fixed_expired_tasks + fixed_cancelled_tasks +
        fixed_late_distributions + fixed_completed_tasks
    )

    if total_fixes > 0:
        logger.info(
            f"fix_inconsistent_distributions: {total_fixes} total fixes "
            f"(expired={fixed_expired_tasks}, cancelled={fixed_cancelled_tasks}, "
            f"late={fixed_late_distributions}, completed={fixed_completed_tasks})"
        )
    else:
        logger.info("fix_inconsistent_distributions: No inconsistencies found")

    return result


@shared_task(bind=True, name='api_planification.tasks.check_task_expiration')
def check_task_expiration(self):
    """
    Periodic task to mark tasks as EXPIREE when their end date has passed.

    ⚡ OPTIMISÉ: Utilise des annotations SQL au lieu de boucles N+1.

    Runs every 5 minutes and checks for tasks where:
    - Status is PLANIFIEE or EN_RETARD
    - All distributions have passed their scheduled end time

    Returns:
        dict: Summary with count of expired tasks
    """
    from api_planification.models import Tache, DistributionCharge
    from django.db.models import Max, Q

    now = timezone.now()
    today = now.date()
    current_time = now.time()

    try:
        with transaction.atomic():
            # ⚡ OPTIMISATION: Annoter avec la dernière date/heure des distributions
            taches = Tache.objects.filter(
                statut__in=['PLANIFIEE', 'EN_RETARD'],
                deleted_at__isnull=True
            ).annotate(
                last_dist_date=Max('distributions_charge__date'),
                last_dist_heure=Max('distributions_charge__heure_fin')
            ).values('id', 'date_fin_planifiee', 'last_dist_date', 'last_dist_heure')

            expired_ids = []
            for tache in taches:
                last_date = tache['last_dist_date'] or tache['date_fin_planifiee']
                last_heure = tache['last_dist_heure']

                is_expired = False
                if last_date:
                    if last_date < today:
                        is_expired = True
                    elif last_date == today and last_heure and current_time > last_heure:
                        is_expired = True

                if is_expired:
                    expired_ids.append(tache['id'])

            # ⚡ BATCH UPDATE: Marquer les tâches expirées
            expired_count = 0
            if expired_ids:
                expired_count = Tache.objects.filter(id__in=expired_ids).update(statut='EXPIREE')

                # Annuler les distributions actives des tâches expirées
                DistributionCharge.objects.filter(
                    tache_id__in=expired_ids,
                    status__in=['NON_REALISEE', 'EN_RETARD']
                ).update(status='ANNULEE', motif_report_annulation='AUTRE')

    except Exception as e:
        logger.error(f"Error in check_task_expiration: {str(e)}")
        return {
            'success': False,
            'error': str(e),
        }

    result = {
        'success': True,
        'expired_tasks': expired_count,
        'timestamp': now.isoformat(),
    }

    if expired_count > 0:
        logger.info(f"check_task_expiration: {expired_count} tasks expired")

    return result
