# api/reporting_view.py
"""
Vue pour le dashboard de reporting global.
Agrège les statistiques de toutes les sources (tâches, réclamations, équipes, inventaire).
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from greensig_web.cache_utils import cache_get, cache_set
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
        structure_filter = None
        user = request.user
        if user.roles_utilisateur.filter(role__nom_role='CLIENT').exists():
            if hasattr(user, 'client_profile') and user.client_profile.structure:
                structure_filter = user.client_profile.structure

        # Cache Redis versionné (invalidé automatiquement après mutations)
        structure_key = structure_filter.id if structure_filter else 'all'
        cached = cache_get('REPORTING', structure_key)
        if cached:
            cached['cached'] = True
            return Response(cached)

        stats = {
            'taches': self._get_taches_stats(now, seven_days_ago, structure_filter),
            'reclamations': self._get_reclamations_stats(now, seven_days_ago, structure_filter),
            'equipes': self._get_equipes_stats(structure_filter),
            'inventaire': self._get_inventaire_stats(structure_filter),
        }

        cache_set('REPORTING', structure_key, data=stats)
        stats['cached'] = False
        return Response(stats)

    def _get_taches_stats(self, now, seven_days_ago, structure_filter=None):
        """Statistiques des tâches. Optimisé : 1 seul aggregate au lieu de 8 count()."""
        try:
            from api_planification.models import Tache

            # Toutes les tâches
            taches = Tache.objects.all()

            # Filtrer par structure pour les utilisateurs CLIENT
            if structure_filter:
                taches = taches.filter(site__structure_client=structure_filter)

            # Un seul aggregate avec Count conditionnel (8 requêtes → 1)
            stats = taches.aggregate(
                total=Count('id'),
                terminees=Count('id', filter=Q(statut='TERMINEE')),
                en_cours=Count('id', filter=Q(statut='EN_COURS')),
                planifiees=Count('id', filter=Q(statut='PLANIFIEE')),
                en_retard=Count('id', filter=Q(
                    statut__in=['PLANIFIEE', 'EN_COURS'],
                    date_fin_planifiee__lt=now
                )),
                terminees_dans_delais=Count('id', filter=Q(
                    statut='TERMINEE',
                    date_fin_reelle__isnull=False,
                    date_fin_reelle__lte=F('date_fin_planifiee')
                )),
                terminees_7j=Count('id', filter=Q(
                    statut='TERMINEE',
                    date_fin_reelle__gte=seven_days_ago
                )),
                creees_7j=Count('id', filter=Q(
                    date_creation__gte=seven_days_ago
                )),
            )

            total = stats['total']
            terminees = stats['terminees']
            terminees_dans_delais = stats['terminees_dans_delais']

            # Calculs des taux
            taux_realisation = (terminees / total * 100) if total > 0 else 0
            taux_respect_delais = (terminees_dans_delais / terminees * 100) if terminees > 0 else 0

            return {
                'total': total,
                'terminees': terminees,
                'en_cours': stats['en_cours'],
                'planifiees': stats['planifiees'],
                'en_retard': stats['en_retard'],
                'taux_realisation': round(taux_realisation, 1),
                'taux_respect_delais': round(taux_respect_delais, 1),
                'terminees_7j': stats['terminees_7j'],
                'creees_7j': stats['creees_7j'],
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

    def _get_reclamations_stats(self, now, seven_days_ago, structure_filter=None):
        """Statistiques des réclamations. Optimisé : counts fusionnés + délai moyen DB-side."""
        try:
            from api_reclamations.models import Reclamation, SatisfactionClient
            from django.db.models import ExpressionWrapper, DurationField

            # Exclure les supprimées et les réclamations internes (cohérent avec les KPIs)
            reclamations = Reclamation.objects.filter(
                actif=True,
                visible_client=True  # Exclure les réclamations internes
            )

            # Filtrer par structure pour les utilisateurs CLIENT
            if structure_filter:
                reclamations = reclamations.filter(
                    Q(structure_client=structure_filter) |
                    Q(site__structure_client=structure_filter)
                )

            # Fusionner les counts en un seul aggregate (4 requêtes → 1)
            counts = reclamations.aggregate(
                total=Count('id'),
                nouvelles_7j=Count('id', filter=Q(
                    date_creation__gte=seven_days_ago
                )),
                resolues_7j=Count('id', filter=Q(
                    statut='CLOTUREE',
                    date_cloture_reelle__gte=seven_days_ago
                )),
            )

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

            # Délai moyen de traitement DB-side (boucle Python → 1 requête aggregate)
            delai_stats = reclamations.filter(
                statut='CLOTUREE',
                date_cloture_reelle__isnull=False,
                date_creation__isnull=False,
            ).annotate(
                delai=ExpressionWrapper(
                    F('date_cloture_reelle') - F('date_creation'),
                    output_field=DurationField()
                )
            ).aggregate(
                avg_delai=Avg('delai'),
            )

            delai_moyen = None
            if delai_stats['avg_delai'] is not None:
                delai_moyen = round(delai_stats['avg_delai'].total_seconds() / 3600, 1)

            # Satisfaction moyenne
            satisfaction = SatisfactionClient.objects.aggregate(
                moyenne=Avg('note'),
                count=Count('id')
            )

            return {
                'total': counts['total'],
                'nouvelles_7j': counts['nouvelles_7j'],
                'resolues_7j': counts['resolues_7j'],
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
                'resolues_7j': 0,
                'error': str(e)
            }

    def _get_equipes_stats(self, structure_filter=None):
        """Statistiques des équipes. Optimisé : batch queries au lieu de N+1."""
        try:
            from api_users.models import Equipe, Operateur, Absence, StatutAbsence
            from api_planification.models import Tache, DistributionCharge
            from django.db.models import Subquery, OuterRef, IntegerField, DecimalField
            from django.db.models.functions import Coalesce

            today = timezone.now().date()
            # Période de la semaine en cours (lundi à dimanche)
            week_start = today - timedelta(days=today.weekday())
            week_end = week_start + timedelta(days=6)

            equipes = Equipe.objects.filter(actif=True)

            # Filtrer par structure pour les utilisateurs CLIENT
            if structure_filter:
                equipes = equipes.filter(site__structure_client=structure_filter)

            # Batch 1: Annoter opérateurs actifs et absents par équipe
            equipes = equipes.annotate(
                total_ops=Count(
                    'operateurs',
                    filter=Q(operateurs__statut='ACTIF')
                ),
                ops_absents=Count(
                    'operateurs',
                    filter=Q(
                        operateurs__statut='ACTIF',
                        operateurs__absences__statut=StatutAbsence.VALIDEE,
                        operateurs__absences__date_debut__lte=today,
                        operateurs__absences__date_fin__gte=today,
                    ),
                    distinct=True
                ),
            )

            equipe_ids = list(equipes.values_list('id', flat=True))
            total_equipes = len(equipe_ids)

            # Batch 2: Compter les tâches actives par équipe (via equipes M2M ou id_equipe FK)
            # Tâches via id_equipe (FK directe)
            taches_fk = (
                Tache.objects.filter(
                    statut__in=['PLANIFIEE', 'EN_COURS'],
                    id_equipe__in=equipe_ids,
                )
                .values('id_equipe')
                .annotate(nb=Count('id', distinct=True))
            )
            nb_taches_fk = {item['id_equipe']: item['nb'] for item in taches_fk}

            # Tâches via equipes M2M
            taches_m2m = (
                Tache.objects.filter(
                    statut__in=['PLANIFIEE', 'EN_COURS'],
                    equipes__in=equipe_ids,
                )
                .values('equipes')
                .annotate(nb=Count('id', distinct=True))
            )
            nb_taches_m2m = {item['equipes']: item['nb'] for item in taches_m2m}

            # Batch 3: Heures planifiées semaine par équipe
            # Collect all active tache IDs per equipe for distribution query
            tache_ids_fk = set(
                Tache.objects.filter(
                    statut__in=['PLANIFIEE', 'EN_COURS'],
                    id_equipe__in=equipe_ids,
                ).values_list('id', flat=True)
            )
            tache_ids_m2m = set(
                Tache.objects.filter(
                    statut__in=['PLANIFIEE', 'EN_COURS'],
                    equipes__in=equipe_ids,
                ).values_list('id', flat=True)
            )
            all_active_tache_ids = tache_ids_fk | tache_ids_m2m

            # Heures via id_equipe
            heures_fk = (
                DistributionCharge.objects.filter(
                    tache__in=all_active_tache_ids,
                    tache__id_equipe__in=equipe_ids,
                    date__gte=week_start,
                    date__lte=week_end,
                    status='NON_REALISEE',
                )
                .values('tache__id_equipe')
                .annotate(total=Sum('heures_planifiees'))
            )
            heures_fk_dict = {item['tache__id_equipe']: float(item['total'] or 0) for item in heures_fk}

            # Heures via equipes M2M
            heures_m2m = (
                DistributionCharge.objects.filter(
                    tache__in=all_active_tache_ids,
                    tache__equipes__in=equipe_ids,
                    date__gte=week_start,
                    date__lte=week_end,
                    status='NON_REALISEE',
                )
                .values('tache__equipes')
                .annotate(total=Sum('heures_planifiees'))
            )
            heures_m2m_dict = {item['tache__equipes']: float(item['total'] or 0) for item in heures_m2m}

            # Build results from annotated equipes
            charges = []
            for equipe in equipes:
                eid = equipe.id
                total_ops = equipe.total_ops
                ops_absents = equipe.ops_absents
                ops_disponibles = total_ops - ops_absents

                # Merge FK + M2M tache counts (avoid double-counting is acceptable as approximation)
                nb_taches = (nb_taches_fk.get(eid, 0) + nb_taches_m2m.get(eid, 0))

                # Merge FK + M2M heures (take max to avoid double-counting)
                heures_planifiees_semaine = max(
                    heures_fk_dict.get(eid, 0),
                    heures_m2m_dict.get(eid, 0)
                )

                capacite_heures = ops_disponibles * 40 if ops_disponibles > 0 else 40
                charge_percent = min(100, (heures_planifiees_semaine / capacite_heures * 100)) if capacite_heures > 0 else 0

                charges.append({
                    'id': eid,
                    'nom': equipe.nom_equipe,
                    'charge_percent': round(charge_percent, 1),
                    'heures_planifiees': round(heures_planifiees_semaine, 1),
                    'capacite_heures': capacite_heures,
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

    def _get_inventaire_stats(self, structure_filter=None):
        """Statistiques de l'inventaire. Optimisé : 1 aggregate par modèle (count + états fusionnés)."""
        vegetation_models = [Arbre, Gazon, Palmier, Arbuste, Vivace, Cactus, Graminee]
        hydraulic_models = [Puit, Pompe, Vanne, Clapet, Canalisation, Aspersion, Goutte, Ballon]

        par_etat = {'bon': 0, 'moyen': 0, 'mauvais': 0, 'critique': 0}

        def _aggregate_model(Model, structure_filter):
            """Un seul aggregate par modèle: total + états (2 requêtes → 1)."""
            qs = Model.objects.all()
            if structure_filter:
                qs = qs.filter(site__structure_client=structure_filter)
            return qs.aggregate(
                total=Count('id'),
                bon=Count('id', filter=Q(etat='bon')),
                moyen=Count('id', filter=Q(etat='moyen')),
                mauvais=Count('id', filter=Q(etat='mauvais')),
                critique=Count('id', filter=Q(etat='critique')),
            )

        # Comptage végétation + états en un seul passage
        vegetation_counts = {}
        total_vegetation = 0
        for Model in vegetation_models:
            result = _aggregate_model(Model, structure_filter)
            count = result['total']
            vegetation_counts[Model.__name__.lower()] = count
            total_vegetation += count
            for etat_key in par_etat:
                par_etat[etat_key] += result[etat_key]

        # Comptage hydraulique + états en un seul passage
        hydraulic_counts = {}
        total_hydraulic = 0
        for Model in hydraulic_models:
            result = _aggregate_model(Model, structure_filter)
            count = result['total']
            hydraulic_counts[Model.__name__.lower()] = count
            total_hydraulic += count
            for etat_key in par_etat:
                par_etat[etat_key] += result[etat_key]

        # Sites (2 counts → 1 aggregate)
        sites_qs = Site.objects.all()
        if structure_filter:
            sites_qs = sites_qs.filter(structure_client=structure_filter)
        sites_stats = sites_qs.aggregate(
            total=Count('id'),
            actifs=Count('id', filter=Q(actif=True)),
        )

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
                'total': sites_stats['total'],
                'actifs': sites_stats['actifs'],
            }
        }
