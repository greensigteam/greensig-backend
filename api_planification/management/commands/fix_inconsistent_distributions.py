# ==============================================================================
# COMMANDE DE CORRECTION: DISTRIBUTIONS INCOHÉRENTES
# ==============================================================================
"""
Script de migration pour corriger les incohérences entre les statuts des tâches
et leurs distributions.

Ce script identifie et corrige les cas suivants:
1. Tâches EXPIREE avec distributions encore actives → Annuler avec motif EXPIRATION
2. Tâches ANNULEE avec distributions encore actives → Annuler avec motif ANNULATION_TACHE

Usage:
    # Voir les incohérences sans les corriger
    python manage.py fix_inconsistent_distributions --dry-run

    # Corriger les incohérences
    python manage.py fix_inconsistent_distributions

    # Mode verbose pour détails
    python manage.py fix_inconsistent_distributions --verbose-output

ATTENTION: Ce script modifie les données. Toujours faire un --dry-run d'abord.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from api_planification.models import Tache
from api_planification.constants import STATUTS_ACTIFS
from api_planification.business_rules import (
    corriger_distributions_tache_expiree,
    corriger_distributions_tache_annulee,
)


class Command(BaseCommand):
    help = "Corrige les distributions incohérentes (tâches EXPIREE/ANNULEE avec distributions actives)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche les corrections qui seraient effectuées sans les appliquer'
        )
        parser.add_argument(
            '--verbose-output',
            action='store_true',
            help='Affiche des informations détaillées'
        )
        parser.add_argument(
            '--type',
            choices=['expiree', 'annulee', 'all'],
            default='all',
            help='Type d\'incohérence à corriger (défaut: all)'
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        verbose = options.get('verbose_output', False)
        fix_type = options.get('type', 'all')

        self.stdout.write("=" * 70)
        self.stdout.write("CORRECTION DES DISTRIBUTIONS INCOHÉRENTES")
        self.stdout.write("=" * 70)

        total_corrige = 0

        # Phase 1: Tâches EXPIREE avec distributions actives
        if fix_type in ('expiree', 'all'):
            nb_corrige = self._fix_taches_expirees(dry_run, verbose)
            total_corrige += nb_corrige

        # Phase 2: Tâches ANNULEE avec distributions actives
        if fix_type in ('annulee', 'all'):
            nb_corrige = self._fix_taches_annulees(dry_run, verbose)
            total_corrige += nb_corrige

        # Résumé final
        self.stdout.write("\n" + "=" * 70)
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"[DRY-RUN] {total_corrige} distribution(s) seraient corrigée(s)"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"TERMINÉ: {total_corrige} distribution(s) corrigée(s)"
                )
            )

    def _fix_taches_expirees(self, dry_run, verbose):
        """Corrige les distributions des tâches expirées."""
        self.stdout.write("\n--- Phase 1: Tâches EXPIREE ---")

        # Trouver les tâches EXPIREE avec des distributions actives
        taches_avec_incoh = []
        taches_expirees = Tache.objects.filter(
            statut='EXPIREE',
            deleted_at__isnull=True
        ).prefetch_related('distributions_charge')

        for tache in taches_expirees:
            dist_actives = tache.distributions_charge.filter(status__in=STATUTS_ACTIFS)
            count = dist_actives.count()
            if count > 0:
                taches_avec_incoh.append({
                    'tache': tache,
                    'distributions_actives': count,
                    'distributions': list(dist_actives.values('id', 'date', 'status'))
                })

        if not taches_avec_incoh:
            self.stdout.write(
                self.style.SUCCESS("  Aucune incohérence détectée pour les tâches EXPIREE")
            )
            return 0

        total_distributions = sum(t['distributions_actives'] for t in taches_avec_incoh)

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"  [DRY-RUN] {len(taches_avec_incoh)} tâche(s) EXPIREE "
                    f"avec {total_distributions} distribution(s) active(s):"
                )
            )
            for item in taches_avec_incoh:
                tache = item['tache']
                self.stdout.write(
                    f"    - Tâche #{tache.id} ({tache.reference or 'sans ref'}): "
                    f"{item['distributions_actives']} distribution(s)"
                )
                if verbose:
                    for d in item['distributions']:
                        self.stdout.write(
                            f"      • Distribution #{d['id']}: {d['date']} - {d['status']}"
                        )
            return total_distributions

        # Appliquer les corrections
        with transaction.atomic():
            for item in taches_avec_incoh:
                tache = item['tache']
                nb_corrige = corriger_distributions_tache_expiree(tache)

                if verbose:
                    self.stdout.write(
                        f"  ✓ Tâche #{tache.id} ({tache.reference or 'sans ref'}): "
                        f"{nb_corrige} distribution(s) annulée(s) (motif: EXPIRATION)"
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"  {total_distributions} distribution(s) corrigée(s) "
                f"pour {len(taches_avec_incoh)} tâche(s) EXPIREE"
            )
        )
        return total_distributions

    def _fix_taches_annulees(self, dry_run, verbose):
        """Corrige les distributions des tâches annulées."""
        self.stdout.write("\n--- Phase 2: Tâches ANNULEE ---")

        # Trouver les tâches ANNULEE avec des distributions actives
        taches_avec_incoh = []
        taches_annulees = Tache.objects.filter(
            statut='ANNULEE',
            deleted_at__isnull=True
        ).prefetch_related('distributions_charge')

        for tache in taches_annulees:
            dist_actives = tache.distributions_charge.filter(status__in=STATUTS_ACTIFS)
            count = dist_actives.count()
            if count > 0:
                taches_avec_incoh.append({
                    'tache': tache,
                    'distributions_actives': count,
                    'distributions': list(dist_actives.values('id', 'date', 'status'))
                })

        if not taches_avec_incoh:
            self.stdout.write(
                self.style.SUCCESS("  Aucune incohérence détectée pour les tâches ANNULEE")
            )
            return 0

        total_distributions = sum(t['distributions_actives'] for t in taches_avec_incoh)

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"  [DRY-RUN] {len(taches_avec_incoh)} tâche(s) ANNULEE "
                    f"avec {total_distributions} distribution(s) active(s):"
                )
            )
            for item in taches_avec_incoh:
                tache = item['tache']
                self.stdout.write(
                    f"    - Tâche #{tache.id} ({tache.reference or 'sans ref'}): "
                    f"{item['distributions_actives']} distribution(s)"
                )
                if verbose:
                    for d in item['distributions']:
                        self.stdout.write(
                            f"      • Distribution #{d['id']}: {d['date']} - {d['status']}"
                        )
            return total_distributions

        # Appliquer les corrections
        with transaction.atomic():
            for item in taches_avec_incoh:
                tache = item['tache']
                nb_corrige = corriger_distributions_tache_annulee(tache)

                if verbose:
                    self.stdout.write(
                        f"  ✓ Tâche #{tache.id} ({tache.reference or 'sans ref'}): "
                        f"{nb_corrige} distribution(s) annulée(s) (motif: ANNULATION_TACHE)"
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"  {total_distributions} distribution(s) corrigée(s) "
                f"pour {len(taches_avec_incoh)} tâche(s) ANNULEE"
            )
        )
        return total_distributions
