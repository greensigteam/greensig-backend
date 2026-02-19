"""
Management command to setup Celery Beat periodic tasks.

Usage:
    python manage.py setup_celery_beat

This creates/updates ALL periodic tasks in the database:

API:
- cleanup_old_exports: Daily at 3 AM (nettoie exports > 7 jours)

DESACTIVEES (systeme simplifie - plus de EN_RETARD/EXPIREE):
- refresh_all_task_statuses: Desactivee
- fix_inconsistent_distributions: Desactivee
"""

from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask, IntervalSchedule, CrontabSchedule
import json


class Command(BaseCommand):
    help = 'Setup ALL Celery Beat periodic tasks for GreenSIG'

    def handle(self, *args, **options):
        self.stdout.write('Setting up Celery Beat periodic tasks...\n')

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

        # ===================================================================
        # TACHES API (Maintenance)
        # ===================================================================
        self.stdout.write(self.style.MIGRATE_HEADING('API MAINTENANCE TASKS:'))

        # cleanup_old_exports (quotidien a 3h du matin)
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
        self.stdout.write(self.style.SUCCESS(f'  [OK] {status}: cleanup_old_exports (daily 03:00, retention: 7 days)'))

        # ===================================================================
        # RECLAMATIONS (Auto-cloture)
        # ===================================================================
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('RECLAMATIONS TASKS:'))

        # Schedule: toutes les heures
        schedule_1h, _ = IntervalSchedule.objects.get_or_create(
            every=1, period=IntervalSchedule.HOURS,
        )

        task, created = PeriodicTask.objects.update_or_create(
            name='Auto-close Pending Reclamations (Hourly)',
            defaults={
                'task': 'api_reclamations.tasks.auto_close_pending_reclamations',
                'interval': schedule_1h,
                'crontab': None,
                'enabled': True,
                'description': 'Rappel 24h + auto-cloture 48h des reclamations en attente de validation',
            }
        )
        status = 'Created' if created else 'Updated'
        self.stdout.write(self.style.SUCCESS(f'  [OK] {status}: auto_close_pending_reclamations (hourly)'))

        # ===================================================================
        # DESACTIVATION DES ANCIENNES TACHES (systeme simplifie)
        # ===================================================================
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('DISABLING LEGACY TASKS:'))

        old_tasks = [
            'api_planification.tasks.update_late_distributions',
            'api_planification.tasks.check_task_expiration',
            'api_planification.tasks.refresh_all_task_statuses',
            'api_planification.tasks.fix_inconsistent_distributions',
            'api_planification.tasks.mark_expired_tasks',
        ]
        disabled_count = PeriodicTask.objects.filter(
            task__in=old_tasks
        ).update(enabled=False)

        if disabled_count > 0:
            self.stdout.write(self.style.WARNING(
                f'  [!] Disabled {disabled_count} legacy task(s) (EN_RETARD/EXPIREE system removed)'
            ))
        else:
            self.stdout.write(self.style.SUCCESS('  [OK] No legacy tasks to disable'))

        # ===================================================================
        # RESUME
        # ===================================================================
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('Celery Beat setup complete!'))
        self.stdout.write(self.style.SUCCESS('=' * 60))

        self.stdout.write('')
        self.stdout.write('Active periodic tasks:')
        self.stdout.write('  1. cleanup_old_exports                 -> Daily at 03:00')
        self.stdout.write('  2. auto_close_pending_reclamations     -> Hourly (rappel 24h + auto-cloture 48h)')

        self.stdout.write('')
        self.stdout.write('Disabled tasks (simplified status system):')
        self.stdout.write('  - refresh_all_task_statuses')
        self.stdout.write('  - fix_inconsistent_distributions')

        self.stdout.write('')
        self.stdout.write('To verify in Django Admin:')
        self.stdout.write('  -> /admin/django_celery_beat/periodictask/')

        self.stdout.write('')
        self.stdout.write('To start Celery services:')
        self.stdout.write('  celery -A greensig_web beat -l info')
        self.stdout.write('  celery -A greensig_web worker -l info -P solo  (Windows)')
        self.stdout.write('  celery -A greensig_web worker -l info          (Linux/Mac)')
