"""
Management command to setup Celery Beat periodic tasks.

Usage:
    python manage.py setup_celery_beat

This creates/updates ALL periodic tasks in the database:

PLANIFICATION:
- refresh_all_task_statuses: Every 5 minutes (statuts EN_RETARD, EXPIREE)
- fix_inconsistent_distributions: Daily at midnight (maintenance données)

API:
- cleanup_old_exports: Daily at 3 AM (nettoie exports > 7 jours)
"""

from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask, IntervalSchedule, CrontabSchedule
import json


class Command(BaseCommand):
    help = 'Setup ALL Celery Beat periodic tasks for GreenSIG'

    def handle(self, *args, **options):
        self.stdout.write('Setting up Celery Beat periodic tasks...\n')

        # ═══════════════════════════════════════════════════════════════════
        # SCHEDULES
        # ═══════════════════════════════════════════════════════════════════

        # Intervalle 5 minutes
        interval_5min, created = IntervalSchedule.objects.get_or_create(
            every=5,
            period=IntervalSchedule.MINUTES,
        )
        if created:
            self.stdout.write(self.style.SUCCESS('  Created: 5 minutes interval'))

        # Crontab minuit (00:00)
        crontab_midnight, created = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='0',
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
        )
        if created:
            self.stdout.write(self.style.SUCCESS('  Created: Midnight crontab (00:00)'))

        # Crontab 3h du matin (03:00)
        crontab_3am, created = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='3',
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
        )
        if created:
            self.stdout.write(self.style.SUCCESS('  Created: 3 AM crontab (03:00)'))

        self.stdout.write('')

        # ═══════════════════════════════════════════════════════════════════
        # TÂCHES PLANIFICATION
        # ═══════════════════════════════════════════════════════════════════
        self.stdout.write(self.style.MIGRATE_HEADING('PLANIFICATION TASKS:'))

        # 1. refresh_all_task_statuses (toutes les 5 min)
        task, created = PeriodicTask.objects.update_or_create(
            name='Refresh Task Statuses (5 min)',
            defaults={
                'task': 'api_planification.tasks.refresh_all_task_statuses',
                'interval': interval_5min,
                'crontab': None,
                'enabled': True,
                'description': 'Met à jour les statuts des tâches (EN_RETARD, EXPIREE) toutes les 5 minutes',
            }
        )
        status = 'Created' if created else 'Updated'
        self.stdout.write(self.style.SUCCESS(f'  ✓ {status}: refresh_all_task_statuses (every 5 min)'))

        # 2. fix_inconsistent_distributions (quotidien à minuit)
        task, created = PeriodicTask.objects.update_or_create(
            name='Fix Inconsistent Distributions (Daily)',
            defaults={
                'task': 'api_planification.tasks.fix_inconsistent_distributions',
                'interval': None,
                'crontab': crontab_midnight,
                'enabled': True,
                'description': 'Corrige les incohérences entre tâches et distributions chaque nuit à minuit',
            }
        )
        status = 'Created' if created else 'Updated'
        self.stdout.write(self.style.SUCCESS(f'  ✓ {status}: fix_inconsistent_distributions (daily 00:00)'))

        # ═══════════════════════════════════════════════════════════════════
        # TÂCHES API (Maintenance)
        # ═══════════════════════════════════════════════════════════════════
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('API MAINTENANCE TASKS:'))

        # 3. cleanup_old_exports (quotidien à 3h du matin)
        task, created = PeriodicTask.objects.update_or_create(
            name='Cleanup Old Exports (Daily)',
            defaults={
                'task': 'api.tasks.cleanup_old_exports',
                'interval': None,
                'crontab': crontab_3am,
                'kwargs': json.dumps({'days': 7}),
                'enabled': True,
                'description': 'Supprime les fichiers d\'export (PDF, Excel, GeoJSON) de plus de 7 jours',
            }
        )
        status = 'Created' if created else 'Updated'
        self.stdout.write(self.style.SUCCESS(f'  ✓ {status}: cleanup_old_exports (daily 03:00, retention: 7 days)'))

        # ═══════════════════════════════════════════════════════════════════
        # DÉSACTIVATION DES ANCIENNES TÂCHES
        # ═══════════════════════════════════════════════════════════════════
        self.stdout.write('')
        old_tasks = [
            'api_planification.tasks.update_late_distributions',
            'api_planification.tasks.check_task_expiration',
        ]
        disabled_count = PeriodicTask.objects.filter(
            task__in=old_tasks
        ).update(enabled=False)

        if disabled_count > 0:
            self.stdout.write(self.style.WARNING(
                f'  ⚠ Disabled {disabled_count} legacy task(s) (replaced by refresh_all_task_statuses)'
            ))

        # ═══════════════════════════════════════════════════════════════════
        # RÉSUMÉ
        # ═══════════════════════════════════════════════════════════════════
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('═' * 60))
        self.stdout.write(self.style.SUCCESS('Celery Beat setup complete!'))
        self.stdout.write(self.style.SUCCESS('═' * 60))

        self.stdout.write('')
        self.stdout.write('Configured periodic tasks:')
        self.stdout.write('  1. refresh_all_task_statuses    → Every 5 minutes')
        self.stdout.write('  2. fix_inconsistent_distributions → Daily at 00:00')
        self.stdout.write('  3. cleanup_old_exports          → Daily at 03:00')

        self.stdout.write('')
        self.stdout.write('To verify in Django Admin:')
        self.stdout.write('  → /admin/django_celery_beat/periodictask/')

        self.stdout.write('')
        self.stdout.write('To start Celery services:')
        self.stdout.write('  celery -A greensig_web beat -l info')
        self.stdout.write('  celery -A greensig_web worker -l info -P solo  (Windows)')
        self.stdout.write('  celery -A greensig_web worker -l info          (Linux/Mac)')
