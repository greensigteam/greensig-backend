"""
Management command to setup Celery Beat periodic tasks.

Usage:
    python manage.py setup_celery_beat

This creates/updates the periodic tasks in the database for:
- refresh_all_task_statuses: Every 5 minutes
- fix_inconsistent_distributions: Daily at midnight
"""

from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask, IntervalSchedule, CrontabSchedule
import json


class Command(BaseCommand):
    help = 'Setup Celery Beat periodic tasks for task status management'

    def handle(self, *args, **options):
        self.stdout.write('Setting up Celery Beat periodic tasks...')

        # ═══════════════════════════════════════════════════════════════════
        # 1. Créer l'intervalle de 5 minutes (si n'existe pas)
        # ═══════════════════════════════════════════════════════════════════
        interval_5min, created = IntervalSchedule.objects.get_or_create(
            every=5,
            period=IntervalSchedule.MINUTES,
        )
        if created:
            self.stdout.write(self.style.SUCCESS('  Created: 5 minutes interval'))

        # ═══════════════════════════════════════════════════════════════════
        # 2. Créer le crontab pour minuit (si n'existe pas)
        # ═══════════════════════════════════════════════════════════════════
        crontab_midnight, created = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='0',
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
        )
        if created:
            self.stdout.write(self.style.SUCCESS('  Created: Midnight crontab'))

        # ═══════════════════════════════════════════════════════════════════
        # 3. Tâche principale: refresh_all_task_statuses (toutes les 5 min)
        # ═══════════════════════════════════════════════════════════════════
        task_refresh, created = PeriodicTask.objects.update_or_create(
            name='Refresh Task Statuses (5 min)',
            defaults={
                'task': 'api_planification.tasks.refresh_all_task_statuses',
                'interval': interval_5min,
                'enabled': True,
                'description': 'Met à jour les statuts des tâches (EN_RETARD, EXPIREE) toutes les 5 minutes',
            }
        )
        status = 'Created' if created else 'Updated'
        self.stdout.write(self.style.SUCCESS(f'  {status}: refresh_all_task_statuses'))

        # ═══════════════════════════════════════════════════════════════════
        # 4. Tâche de maintenance: fix_inconsistent_distributions (quotidien)
        # ═══════════════════════════════════════════════════════════════════
        task_fix, created = PeriodicTask.objects.update_or_create(
            name='Fix Inconsistent Distributions (Daily)',
            defaults={
                'task': 'api_planification.tasks.fix_inconsistent_distributions',
                'crontab': crontab_midnight,
                'enabled': True,
                'description': 'Corrige les incohérences entre tâches et distributions chaque nuit',
            }
        )
        status = 'Created' if created else 'Updated'
        self.stdout.write(self.style.SUCCESS(f'  {status}: fix_inconsistent_distributions'))

        # ═══════════════════════════════════════════════════════════════════
        # 5. Désactiver les anciennes tâches (si elles existent)
        # ═══════════════════════════════════════════════════════════════════
        old_tasks = [
            'update_late_distributions',
            'check_task_expiration',
        ]
        disabled_count = PeriodicTask.objects.filter(
            task__in=[f'api_planification.tasks.{t}' for t in old_tasks]
        ).update(enabled=False)

        if disabled_count > 0:
            self.stdout.write(self.style.WARNING(
                f'  Disabled {disabled_count} old task(s) (replaced by refresh_all_task_statuses)'
            ))

        self.stdout.write(self.style.SUCCESS('\nCelery Beat setup complete!'))
        self.stdout.write('\nTo start Celery Beat, run:')
        self.stdout.write('  celery -A greensig_web beat -l info')
        self.stdout.write('\nTo start Celery Worker, run:')
        self.stdout.write('  celery -A greensig_web worker -l info -P solo  (Windows)')
        self.stdout.write('  celery -A greensig_web worker -l info          (Linux/Mac)')
