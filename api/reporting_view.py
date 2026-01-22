# api/reporting_view.py
"""
Vue pour le dashboard de reporting global.
Agrège les statistiques de toutes les sources (tâches, réclamations, équipes, inventaire).
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Avg, Sum, Q, F
from django.utils import timezone
from datetime import timedelta

from .models import (
    Site, SousSite, Objet,
    Arbre, Gazon, Palmier, Arbuste, Vivace, Cactus, Graminee,
    Puit, Pompe, Vanne, Clapet, Canalisation, Aspersion, Goutte, Ballon
)


class ReportingView(APIView):
    """
    Vue pour retourner les statistiques globales pour le dashboard de reporting.

    GET /api/reporting/

    Returns:
        {
            "taches": {
                "total": 150,
                "terminees": 120,
                "en_cours": 20,
                "planifiees": 10,
                "en_retard": 5,
                "taux_realisation": 80.0,
                "taux_respect_delais": 85.0
            },
            "reclamations": {
                "total": 45,
                "nouvelles_7j": 12,
                "en_retard": 5,
                "resolues_7j": 28,
                "par_type": [...],
                "delai_moyen_heures": 24.5
            },
            "equipes": {
                "total": 5,
                "actives": 4,
                "charge_moyenne": 75.0,
                "charges": [...]
            },
            "inventaire": {
                "total_objets": 1500,
                "vegetation": 1200,
                "hydraulique": 300,
                "par_etat": {...}
            }
        }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        now = timezone.now()
        seven_days_ago = now - timedelta(days=7)
        thirty_days_ago = now - timedelta(days=30)

        stats = {
            'taches': self._get_taches_stats(now, seven_days_ago),
            'reclamations': self._get_reclamations_stats(now, seven_days_ago),
            'equipes': self._get_equipes_stats(),
            'inventaire': self._get_inventaire_stats(),
        }

        return Response(stats)

    def _get_taches_stats(self, now, seven_days_ago):
        """Statistiques des tâches."""
        try:
            from api_planification.models import Tache

            # Tâches non supprimées
            taches = Tache.objects.filter(deleted_at__isnull=True)

            total = taches.count()
            terminees = taches.filter(statut='TERMINEE').count()
            en_cours = taches.filter(statut='EN_COURS').count()
            planifiees = taches.filter(statut='PLANIFIEE').count()

            # Tâches en retard (date fin planifiée dépassée et pas terminée)
            en_retard = taches.filter(
                date_fin_planifiee__lt=now,
                statut__in=['PLANIFIEE', 'EN_COURS']
            ).count()

            # Tâches terminées dans les délais
            terminees_dans_delais = taches.filter(
                statut='TERMINEE',
                date_fin_reelle__isnull=False,
                date_fin_reelle__lte=F('date_fin_planifiee')
            ).count()

            # Calculs des taux
            taux_realisation = (terminees / total * 100) if total > 0 else 0
            taux_respect_delais = (terminees_dans_delais / terminees * 100) if terminees > 0 else 0

            # Tâches des 7 derniers jours
            terminees_7j = taches.filter(
                statut='TERMINEE',
                date_fin_reelle__gte=seven_days_ago
            ).count()

            creees_7j = taches.filter(
                date_creation__gte=seven_days_ago
            ).count()

            return {
                'total': total,
                'terminees': terminees,
                'en_cours': en_cours,
                'planifiees': planifiees,
                'en_retard': en_retard,
                'taux_realisation': round(taux_realisation, 1),
                'taux_respect_delais': round(taux_respect_delais, 1),
                'terminees_7j': terminees_7j,
                'creees_7j': creees_7j,
            }
        except Exception as e:
            return {
                'total': 0,
                'terminees': 0,
                'en_cours': 0,
                'planifiees': 0,
                'en_retard': 0,
                'taux_realisation': 0,
                'taux_respect_delais': 0,
                'error': str(e)
            }

    def _get_reclamations_stats(self, now, seven_days_ago):
        """Statistiques des réclamations."""
        try:
            from api_reclamations.models import Reclamation, SatisfactionClient

            reclamations = Reclamation.objects.all()

            total = reclamations.count()

            # Nouvelles réclamations (7 derniers jours)
            nouvelles_7j = reclamations.filter(
                date_creation__gte=seven_days_ago
            ).count()

            # Réclamations en retard (date clôture prévue dépassée et pas clôturée)
            en_retard = reclamations.filter(
                date_cloture_prevue__lt=now,
                statut__in=['NOUVELLE', 'PRISE_EN_COMPTE', 'EN_COURS']
            ).count()

            # Résolues dans les 7 derniers jours
            resolues_7j = reclamations.filter(
                statut__in=['RESOLUE', 'CLOTUREE'],
                date_cloture_reelle__gte=seven_days_ago
            ).count()

            # Par statut
            par_statut = dict(
                reclamations.values('statut')
                .annotate(count=Count('id'))
                .values_list('statut', 'count')
            )

            # Par type
            par_type = list(
                reclamations.values('type_reclamation__nom_reclamation')
                .annotate(count=Count('id'))
                .order_by('-count')[:5]
            )

            # Délai moyen de traitement (pour les clôturées)
            delai_moyen = None
            cloturees = reclamations.filter(
                statut='CLOTUREE',
                date_cloture_reelle__isnull=False
            )
            if cloturees.exists():
                delais = []
                for rec in cloturees[:100]:  # Limiter pour performance
                    if rec.date_creation and rec.date_cloture_reelle:
                        delta = rec.date_cloture_reelle - rec.date_creation
                        delais.append(delta.total_seconds() / 3600)
                if delais:
                    delai_moyen = round(sum(delais) / len(delais), 1)

            # Satisfaction moyenne
            satisfaction = SatisfactionClient.objects.aggregate(
                moyenne=Avg('note'),
                count=Count('id')
            )

            return {
                'total': total,
                'nouvelles_7j': nouvelles_7j,
                'en_retard': en_retard,
                'resolues_7j': resolues_7j,
                'par_statut': par_statut,
                'par_type': par_type,
                'delai_moyen_heures': delai_moyen,
                'satisfaction_moyenne': round(satisfaction['moyenne'], 1) if satisfaction['moyenne'] else None,
                'nombre_evaluations': satisfaction['count'],
            }
        except Exception as e:
            return {
                'total': 0,
                'nouvelles_7j': 0,
                'en_retard': 0,
                'resolues_7j': 0,
                'error': str(e)
            }

    def _get_equipes_stats(self):
        """Statistiques des équipes."""
        try:
            from api_users.models import Equipe, Operateur, Absence, StatutAbsence
            from api_planification.models import Tache, DistributionCharge

            today = timezone.now().date()
            # Période de la semaine en cours (lundi à dimanche)
            week_start = today - timedelta(days=today.weekday())
            week_end = week_start + timedelta(days=6)

            equipes = Equipe.objects.filter(actif=True)
            total_equipes = equipes.count()

            charges = []
            for equipe in equipes:
                # Compter les tâches en cours et planifiées pour cette équipe
                taches_equipe = Tache.objects.filter(
                    deleted_at__isnull=True,
                    statut__in=['PLANIFIEE', 'EN_COURS']
                ).filter(
                    Q(equipes=equipe) | Q(id_equipe=equipe)
                ).distinct()

                nb_taches = taches_equipe.count()

                # ✅ AMÉLIORATION: Calculer la charge basée sur les heures des distributions
                # Heures planifiées pour la semaine en cours
                heures_planifiees_semaine = DistributionCharge.objects.filter(
                    tache__in=taches_equipe,
                    date__gte=week_start,
                    date__lte=week_end,
                    status='NON_REALISEE'  # Seulement les distributions non encore réalisées
                ).aggregate(
                    total=Sum('heures_planifiees')
                )['total'] or 0

                # Compter les opérateurs disponibles
                operateurs = Operateur.objects.filter(
                    equipe=equipe,
                    statut='ACTIF'
                )
                total_ops = operateurs.count()

                # Opérateurs en absence aujourd'hui
                ops_absents = operateurs.filter(
                    absences__statut=StatutAbsence.VALIDEE,
                    absences__date_debut__lte=today,
                    absences__date_fin__gte=today
                ).distinct().count()

                ops_disponibles = total_ops - ops_absents

                # ✅ Capacité de l'équipe = opérateurs disponibles × 40h/semaine
                capacite_heures = ops_disponibles * 40 if ops_disponibles > 0 else 40  # Minimum 40h pour éviter division par 0

                # ✅ Charge % = (heures planifiées / capacité) × 100
                charge_percent = min(100, (heures_planifiees_semaine / capacite_heures * 100)) if capacite_heures > 0 else 0

                charges.append({
                    'id': equipe.id,
                    'nom': equipe.nomEquipe,
                    'charge_percent': round(charge_percent, 1),
                    'heures_planifiees': round(heures_planifiees_semaine, 1),  # ✅ NOUVEAU
                    'capacite_heures': capacite_heures,  # ✅ NOUVEAU
                    'nb_taches': nb_taches,
                    'operateurs_total': total_ops,
                    'operateurs_disponibles': ops_disponibles,
                })

            # Charge moyenne
            charge_moyenne = sum(c['charge_percent'] for c in charges) / len(charges) if charges else 0

            return {
                'total': total_equipes,
                'actives': total_equipes,
                'charge_moyenne': round(charge_moyenne, 1),
                'charges': sorted(charges, key=lambda x: x['charge_percent'], reverse=True),
            }
        except Exception as e:
            return {
                'total': 0,
                'actives': 0,
                'charge_moyenne': 0,
                'charges': [],
                'error': str(e)
            }

    def _get_inventaire_stats(self):
        """Statistiques de l'inventaire."""
        vegetation_models = [Arbre, Gazon, Palmier, Arbuste, Vivace, Cactus, Graminee]
        hydraulic_models = [Puit, Pompe, Vanne, Clapet, Canalisation, Aspersion, Goutte, Ballon]

        # Comptage végétation
        vegetation_counts = {}
        total_vegetation = 0
        for Model in vegetation_models:
            count = Model.objects.count()
            vegetation_counts[Model.__name__.lower()] = count
            total_vegetation += count

        # Comptage hydraulique
        hydraulic_counts = {}
        total_hydraulic = 0
        for Model in hydraulic_models:
            count = Model.objects.count()
            hydraulic_counts[Model.__name__.lower()] = count
            total_hydraulic += count

        # Par état (tous objets)
        par_etat = {'bon': 0, 'moyen': 0, 'mauvais': 0, 'critique': 0}
        for Model in vegetation_models + hydraulic_models:
            state_counts = Model.objects.values('etat').annotate(count=Count('id'))
            for item in state_counts:
                if item['etat'] in par_etat:
                    par_etat[item['etat']] += item['count']

        # Sites
        total_sites = Site.objects.count()
        sites_actifs = Site.objects.filter(actif=True).count()

        return {
            'total_objets': total_vegetation + total_hydraulic,
            'vegetation': {
                'total': total_vegetation,
                'par_type': vegetation_counts,
            },
            'hydraulique': {
                'total': total_hydraulic,
                'par_type': hydraulic_counts,
            },
            'par_etat': par_etat,
            'sites': {
                'total': total_sites,
                'actifs': sites_actifs,
            }
        }
