# ==============================================================================
# COMMANDE DE GESTION: MISE À JOUR DES RETARDS ET EXPIRATIONS
# ==============================================================================
"""
Cette commande met automatiquement à jour:
1. Le statut des distributions de charge passées en retard
2. Le statut des tâches expirées (date_fin_planifiee dépassée)
3. Annule automatiquement les distributions actives des tâches expirées

Usage:
    python manage.py update_late_distributions

Configuration cron recommandée (toutes les 5 minutes):
    */5 * * * * cd /path/to/backend && python manage.py update_late_distributions

Cette commande:
1. Identifie les distributions NON_REALISEE dont la date+heure est passée → EN_RETARD
2. Identifie les tâches PLANIFIEE/EN_RETARD dont date_fin_planifiee < aujourd'hui → EXPIREE
3. Annule automatiquement les distributions actives des tâches expirées
4. Log tous les changements effectués
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

from api_planification.models import DistributionCharge, Tache
from api_planification.constants import STATUTS_ACTIFS


class Command(BaseCommand):
    help = "Met à jour les distributions en retard et expire les tâches dépassées"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche les distributions qui seraient mises à jour sans les modifier'
        )
        # Note: Django utilise déjà -v/--verbosity, on utilise --verbose-output
        parser.add_argument(
            '--verbose-output',
            action='store_true',
            help='Affiche des informations détaillées'
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        verbose = options.get('verbose_output', False)

        now = timezone.now()
        today = now.date()
        current_time = now.time()

        if verbose:
            self.stdout.write(f"Date/heure actuelle: {now.strftime('%Y-%m-%d %H:%M:%S')}")

        # Rechercher les distributions NON_REALISEE qui devraient être EN_RETARD
        # Critères:
        # 1. Statut = NON_REALISEE
        # 2. Date < aujourd'hui OU (Date = aujourd'hui ET heure_debut < heure actuelle)
        distributions_en_retard = []

        distributions_non_realisees = DistributionCharge.objects.filter(
            status='NON_REALISEE'
        ).select_related('tache')

        for dist in distributions_non_realisees:
            est_en_retard = False

            if dist.date < today:
                # Date passée → en retard
                est_en_retard = True
            elif dist.date == today and dist.heure_debut:
                # Aujourd'hui avec heure de début définie
                if current_time > dist.heure_debut:
                    est_en_retard = True

            if est_en_retard:
                distributions_en_retard.append(dist)

        # Afficher le résultat
        count = len(distributions_en_retard)

        if count == 0:
            self.stdout.write(
                self.style.SUCCESS("Aucune distribution en retard détectée.")
            )
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"[DRY-RUN] {count} distribution(s) seraient marquée(s) en retard:")
            )
            for dist in distributions_en_retard:
                self.stdout.write(
                    f"  - Distribution #{dist.id}: {dist.date} "
                    f"({dist.heure_debut or 'sans heure'}) - Tâche #{dist.tache_id}"
                )
            return

        # Appliquer les changements
        with transaction.atomic():
            ids_modifies = []
            for dist in distributions_en_retard:
                dist.status = 'EN_RETARD'
                dist.save(update_fields=['status', 'updated_at'])
                ids_modifies.append(dist.id)

                if verbose:
                    self.stdout.write(
                        f"  - Distribution #{dist.id} ({dist.date}): "
                        f"NON_REALISEE → EN_RETARD"
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"{count} distribution(s) marquée(s) EN_RETARD: {ids_modifies}"
            )
        )

        # ══════════════════════════════════════════════════════════════════════════
        # PHASE 2: EXPIRATION DES TÂCHES
        # ══════════════════════════════════════════════════════════════════════════
        # Identifier les tâches PLANIFIEE ou EN_RETARD dont date_fin_planifiee < aujourd'hui
        self._handle_task_expiration(today, dry_run, verbose)

    def _handle_task_expiration(self, today, dry_run, verbose):
        """
        Gère l'expiration des tâches et la synchronisation des distributions.

        Une tâche est expirée si:
        - Son statut est PLANIFIEE ou EN_RETARD
        - Sa date_fin_planifiee < aujourd'hui
        """
        if verbose:
            self.stdout.write("\n--- Vérification des tâches expirées ---")

        taches_a_expirer = Tache.objects.filter(
            statut__in=['PLANIFIEE', 'EN_RETARD'],
            date_fin_planifiee__lt=today,
            deleted_at__isnull=True
        )

        count = taches_a_expirer.count()

        if count == 0:
            if verbose:
                self.stdout.write(
                    self.style.SUCCESS("Aucune tâche à expirer.")
                )
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"[DRY-RUN] {count} tâche(s) seraient marquée(s) EXPIREE:")
            )
            for tache in taches_a_expirer:
                dist_actives = tache.distributions_charge.filter(status__in=STATUTS_ACTIFS).count()
                self.stdout.write(
                    f"  - Tâche #{tache.id} ({tache.reference or 'sans ref'}): "
                    f"fin planifiée {tache.date_fin_planifiee}, {dist_actives} distribution(s) active(s)"
                )
            return

        # Appliquer les expirations
        with transaction.atomic():
            taches_expirees = []
            distributions_annulees = 0

            for tache in taches_a_expirer:
                # Compter les distributions actives avant expiration
                dist_actives_avant = tache.distributions_charge.filter(
                    status__in=STATUTS_ACTIFS
                ).count()

                # Utiliser mark_as_expired() qui gère la synchronisation des distributions
                if tache.mark_as_expired():
                    taches_expirees.append({
                        'id': tache.id,
                        'reference': tache.reference,
                        'distributions_annulees': dist_actives_avant
                    })
                    distributions_annulees += dist_actives_avant

                    if verbose:
                        self.stdout.write(
                            f"  - Tâche #{tache.id} ({tache.reference or 'sans ref'}): "
                            f"PLANIFIEE/EN_RETARD → EXPIREE, "
                            f"{dist_actives_avant} distribution(s) annulée(s)"
                        )

        if taches_expirees:
            ids_expires = [t['id'] for t in taches_expirees]
            self.stdout.write(
                self.style.SUCCESS(
                    f"{len(taches_expirees)} tâche(s) marquée(s) EXPIREE: {ids_expires}"
                )
            )
            if distributions_annulees > 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"{distributions_annulees} distribution(s) automatiquement annulée(s)"
                    )
                )
