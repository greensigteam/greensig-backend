"""
Commande de maintenance : détecte les tâches sans distributions de charge
et crée automatiquement les distributions manquantes.

Usage:
    python manage.py fix_missing_distributions              # Dry-run (affiche sans créer)
    python manage.py fix_missing_distributions --apply      # Crée les distributions
    python manage.py fix_missing_distributions --apply --heures 8:00-16:00  # Horaires custom
"""

from datetime import datetime, timedelta, time
from django.core.management.base import BaseCommand
from django.db.models import Count

from api_planification.models import Tache, DistributionCharge


class Command(BaseCommand):
    help = 'Détecte et corrige les tâches sans distributions de charge'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Applique les corrections (sans ce flag, mode dry-run uniquement)',
        )
        parser.add_argument(
            '--heures',
            type=str,
            default='08:00-17:00',
            help='Plage horaire pour les distributions créées (format HH:MM-HH:MM, défaut: 08:00-17:00)',
        )
        parser.add_argument(
            '--statut',
            type=str,
            nargs='+',
            default=['PLANIFIEE', 'EN_COURS'],
            help='Statuts des tâches à traiter (défaut: PLANIFIEE EN_COURS)',
        )

    def handle(self, *args, **options):
        apply = options['apply']
        heures_str = options['heures']
        statuts = options['statut']

        # Parser la plage horaire
        try:
            h_debut_str, h_fin_str = heures_str.split('-')
            heure_debut = datetime.strptime(h_debut_str.strip(), '%H:%M').time()
            heure_fin = datetime.strptime(h_fin_str.strip(), '%H:%M').time()
        except (ValueError, AttributeError):
            self.stderr.write(self.style.ERROR(
                f'Format horaire invalide: "{heures_str}". Utilisez HH:MM-HH:MM (ex: 08:00-17:00)'
            ))
            return

        # Calculer les heures planifiées par jour
        debut_dt = datetime.combine(datetime.today(), heure_debut)
        fin_dt = datetime.combine(datetime.today(), heure_fin)
        heures_par_jour = round((fin_dt - debut_dt).total_seconds() / 3600, 2)

        if heures_par_jour <= 0:
            self.stderr.write(self.style.ERROR('L\'heure de fin doit être après l\'heure de début'))
            return

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'=== Recherche des tâches sans distributions ==='
        ))
        self.stdout.write(f'  Statuts ciblés : {", ".join(statuts)}')
        self.stdout.write(f'  Plage horaire  : {h_debut_str} - {h_fin_str} ({heures_par_jour}h/jour)')
        self.stdout.write(f'  Mode           : {"APPLICATION" if apply else "DRY-RUN (simulation)"}')
        self.stdout.write('')

        # Trouver les tâches sans distributions
        taches_sans_distrib = (
            Tache.objects
            .filter(statut__in=statuts)
            .annotate(nb_distributions=Count('distributions_charge'))
            .filter(nb_distributions=0)
            .select_related('id_type_tache', 'id_structure_client')
            .order_by('date_debut_planifiee')
        )

        count = taches_sans_distrib.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS(
                'Aucune tâche sans distributions trouvée. Tout est en ordre.'
            ))
            return

        self.stdout.write(self.style.WARNING(f'{count} tâche(s) sans distributions détectée(s) :'))
        self.stdout.write('')

        total_distributions_creees = 0

        for tache in taches_sans_distrib:
            type_tache_nom = tache.id_type_tache.nom_tache if tache.id_type_tache else '(sans type)'
            structure_nom = tache.id_structure_client.nom if tache.id_structure_client else '(sans structure)'

            # Calculer les jours ouvrés entre date_debut et date_fin
            jours = self._get_weekdays(tache.date_debut_planifiee, tache.date_fin_planifiee)
            nb_jours = len(jours)

            # Si la tâche a une charge estimée, répartir sur les jours
            if tache.charge_estimee_heures and tache.charge_estimee_heures > 0 and nb_jours > 0:
                heures_calculees = round(tache.charge_estimee_heures / nb_jours, 2)
            else:
                heures_calculees = heures_par_jour

            self.stdout.write(
                f'  [{tache.id}] {type_tache_nom} | {structure_nom} | '
                f'{tache.statut} | {tache.date_debut_planifiee} → {tache.date_fin_planifiee} | '
                f'{nb_jours} jour(s) ouvré(s) | {heures_calculees}h/jour'
            )

            if nb_jours == 0:
                self.stdout.write(self.style.WARNING(
                    f'        ⚠ Aucun jour ouvré dans la plage — distribution ignorée'
                ))
                continue

            if apply:
                distributions = []
                for jour in jours:
                    distributions.append(DistributionCharge(
                        tache=tache,
                        date=jour,
                        heures_planifiees=heures_calculees,
                        heure_debut=heure_debut,
                        heure_fin=heure_fin,
                        status='NON_REALISEE',
                        commentaire='Créée automatiquement par fix_missing_distributions',
                    ))
                DistributionCharge.objects.bulk_create(distributions)
                total_distributions_creees += len(distributions)
                self.stdout.write(self.style.SUCCESS(
                    f'        ✓ {len(distributions)} distribution(s) créée(s)'
                ))

        self.stdout.write('')

        if apply:
            self.stdout.write(self.style.SUCCESS(
                f'Terminé : {total_distributions_creees} distribution(s) créée(s) '
                f'pour {count} tâche(s).'
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f'DRY-RUN terminé. {count} tâche(s) à corriger. '
                f'Relancez avec --apply pour créer les distributions.'
            ))

    def _get_weekdays(self, date_debut, date_fin):
        """Retourne la liste des jours ouvrés (lun-ven) entre deux dates incluses."""
        jours = []
        current = date_debut
        while current <= date_fin:
            if current.weekday() < 5:  # 0=lundi ... 4=vendredi
                jours.append(current)
            current += timedelta(days=1)
        return jours
