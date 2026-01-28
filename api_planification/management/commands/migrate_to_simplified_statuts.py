"""
Migration des statuts vers le système simplifié.

Ce script migre les données existantes:
- Tâches EN_RETARD ou EXPIREE → PLANIFIEE
- Distributions EN_RETARD → NON_REALISEE

Usage:
    python manage.py migrate_to_simplified_statuts --dry-run  # Voir les changements sans les appliquer
    python manage.py migrate_to_simplified_statuts            # Appliquer les changements
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from api_planification.models import Tache, DistributionCharge


class Command(BaseCommand):
    help = "Migre les statuts EN_RETARD et EXPIREE vers le système simplifié"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche les changements sans les appliquer',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING("\n[DRY-RUN] Aucune modification ne sera effectuee\n"))
        else:
            self.stdout.write(self.style.SUCCESS("\nMigration des statuts vers le systeme simplifie\n"))

        # =====================================================================
        # 1. Migration des taches EN_RETARD -> PLANIFIEE
        # =====================================================================
        self.stdout.write("=" * 60)
        self.stdout.write("TACHES EN_RETARD -> PLANIFIEE")
        self.stdout.write("=" * 60)

        taches_en_retard = Tache.objects.filter(statut='EN_RETARD')
        count_en_retard = taches_en_retard.count()

        if count_en_retard > 0:
            self.stdout.write(f"\n  Trouvé: {count_en_retard} tâche(s) EN_RETARD")

            for tache in taches_en_retard[:10]:  # Afficher les 10 premières
                self.stdout.write(f"    - #{tache.id} ({tache.reference or 'sans ref'}) - {tache.id_type_tache.nom_tache}")

            if count_en_retard > 10:
                self.stdout.write(f"    ... et {count_en_retard - 10} autre(s)")

            if not dry_run:
                with transaction.atomic():
                    updated = taches_en_retard.update(statut='PLANIFIEE')
                    self.stdout.write(self.style.SUCCESS(f"\n  [OK] {updated} tache(s) migree(s) EN_RETARD -> PLANIFIEE"))
        else:
            self.stdout.write(self.style.SUCCESS("\n  [OK] Aucune tache EN_RETARD a migrer"))

        # =====================================================================
        # 2. Migration des taches EXPIREE -> PLANIFIEE
        # =====================================================================
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("TACHES EXPIREE -> PLANIFIEE")
        self.stdout.write("=" * 60)

        taches_expirees = Tache.objects.filter(statut='EXPIREE')
        count_expirees = taches_expirees.count()

        if count_expirees > 0:
            self.stdout.write(f"\n  Trouvé: {count_expirees} tâche(s) EXPIREE")

            for tache in taches_expirees[:10]:
                self.stdout.write(f"    - #{tache.id} ({tache.reference or 'sans ref'}) - {tache.id_type_tache.nom_tache}")

            if count_expirees > 10:
                self.stdout.write(f"    ... et {count_expirees - 10} autre(s)")

            if not dry_run:
                with transaction.atomic():
                    updated = taches_expirees.update(statut='PLANIFIEE')
                    self.stdout.write(self.style.SUCCESS(f"\n  [OK] {updated} tache(s) migree(s) EXPIREE -> PLANIFIEE"))
        else:
            self.stdout.write(self.style.SUCCESS("\n  [OK] Aucune tache EXPIREE a migrer"))

        # =====================================================================
        # 3. Migration des distributions EN_RETARD -> NON_REALISEE
        # =====================================================================
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("DISTRIBUTIONS EN_RETARD -> NON_REALISEE")
        self.stdout.write("=" * 60)

        distributions_en_retard = DistributionCharge.objects.filter(status='EN_RETARD')
        count_dist_retard = distributions_en_retard.count()

        if count_dist_retard > 0:
            self.stdout.write(f"\n  Trouvé: {count_dist_retard} distribution(s) EN_RETARD")

            for dist in distributions_en_retard[:10]:
                self.stdout.write(f"    - #{dist.id} (Tâche #{dist.tache_id}) - {dist.date}")

            if count_dist_retard > 10:
                self.stdout.write(f"    ... et {count_dist_retard - 10} autre(s)")

            if not dry_run:
                with transaction.atomic():
                    updated = distributions_en_retard.update(status='NON_REALISEE')
                    self.stdout.write(self.style.SUCCESS(f"\n  [OK] {updated} distribution(s) migree(s) EN_RETARD -> NON_REALISEE"))
        else:
            self.stdout.write(self.style.SUCCESS("\n  [OK] Aucune distribution EN_RETARD a migrer"))

        # =====================================================================
        # 4. Restauration des distributions ANNULEE des taches reactivees
        # =====================================================================
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("RESTAURATION DES DISTRIBUTIONS ANNULEES")
        self.stdout.write("=" * 60)

        # Trouver les distributions ANNULEE avec motif EXPIRATION dont la tâche est maintenant PLANIFIEE
        distributions_a_restaurer = DistributionCharge.objects.filter(
            status='ANNULEE',
            motif_report_annulation='EXPIRATION',
            tache__statut='PLANIFIEE'
        )
        count_a_restaurer = distributions_a_restaurer.count()

        if count_a_restaurer > 0:
            self.stdout.write(f"\n  Trouvé: {count_a_restaurer} distribution(s) ANNULEE (motif EXPIRATION) à restaurer")

            for dist in distributions_a_restaurer[:10]:
                self.stdout.write(f"    - #{dist.id} (Tâche #{dist.tache_id}) - {dist.date}")

            if count_a_restaurer > 10:
                self.stdout.write(f"    ... et {count_a_restaurer - 10} autre(s)")

            if not dry_run:
                with transaction.atomic():
                    updated = distributions_a_restaurer.update(
                        status='NON_REALISEE',
                        motif_report_annulation=''  # Vide au lieu de None (contrainte DB)
                    )
                    self.stdout.write(self.style.SUCCESS(f"\n  [OK] {updated} distribution(s) restauree(s) ANNULEE -> NON_REALISEE"))
        else:
            self.stdout.write(self.style.SUCCESS("\n  [OK] Aucune distribution a restaurer"))

        # =====================================================================
        # Resume
        # =====================================================================
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("RESUME")
        self.stdout.write("=" * 60)

        total_changes = count_en_retard + count_expirees + count_dist_retard + count_a_restaurer

        if dry_run:
            self.stdout.write(f"\n  Total des modifications a effectuer: {total_changes}")
            self.stdout.write(self.style.WARNING("\n  Executez sans --dry-run pour appliquer les changements\n"))
        else:
            self.stdout.write(f"\n  Total des modifications effectuees: {total_changes}")
            self.stdout.write(self.style.SUCCESS("\n  Migration terminee avec succes!\n"))
