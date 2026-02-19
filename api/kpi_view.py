"""
KPI (Key Performance Indicators) views for GreenSIG.

6 KPIs:
  1. Respect du planning (>95%) — Global
  2. Qualité de service (>95%) — Global
  3. Taux de réalisation des réclamations — Global
  4. Temps moyen de traitement des réclamations — Par TypeReclamation
  5. Temps de réalisation par tâche — Par TypeTache, par Site
  6. Temps total de travail par site — Par Site

Endpoints:
  GET /api/kpis/?mois=YYYY-MM&site_id=N
  GET /api/kpis/historique/?site_id=N&nb_mois=6
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status as drf_status
from django.db.models import (
    Count, Avg, Sum, Q, F, ExpressionWrapper, DurationField, FloatField
)
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import datetime, timedelta, timezone as dt_timezone
from dateutil.relativedelta import relativedelta

from greensig_web.cache_utils import cache_get, cache_set


# ==============================================================================
# HELPERS
# ==============================================================================

def _calc_evolution(current, previous):
    """Calcule le % d'évolution entre deux valeurs. Positif = amélioration."""
    if current is None or previous is None or previous == 0:
        return None
    return round(((current - previous) / previous) * 100, 1)


def _calc_evolution_inverse(current, previous):
    """Pour les métriques où une baisse est positive (ex: temps de traitement)."""
    if current is None or previous is None or previous == 0:
        return None
    return round(((previous - current) / previous) * 100, 1)


def _get_status(value, threshold):
    """Retourne le statut couleur: vert si >= seuil, orange si proche, rouge sinon."""
    if value is None:
        return 'gris'
    if value >= threshold:
        return 'vert'
    elif value >= threshold * 0.9:
        return 'orange'
    else:
        return 'rouge'


def _get_status_inverse(value, threshold):
    """Pour les métriques où plus bas est mieux (ex: temps en heures)."""
    if value is None:
        return 'gris'
    if value <= threshold:
        return 'vert'
    elif value <= threshold * 1.2:
        return 'orange'
    else:
        return 'rouge'


# ==============================================================================
# FILTRAGE PAR RÔLE
# ==============================================================================

def _get_role_filters(user):
    """
    Retourne (structure_filter, superviseur_filter) selon le rôle de l'utilisateur.
    - ADMIN: (None, None) → voit tout
    - CLIENT: (structure, None) → voit sa structure
    - SUPERVISEUR: (None, superviseur) → voit ses sites affectés
    """
    structure_filter = None
    superviseur_filter = None

    if not user or not user.is_authenticated:
        return structure_filter, superviseur_filter

    roles = [ur.role.nom_role for ur in user.roles_utilisateur.all()]

    if 'ADMIN' in roles:
        pass  # Voit tout
    elif 'CLIENT' in roles and hasattr(user, 'client_profile'):
        if user.client_profile and user.client_profile.structure:
            structure_filter = user.client_profile.structure
    elif 'SUPERVISEUR' in roles and hasattr(user, 'superviseur_profile'):
        if user.superviseur_profile:
            superviseur_filter = user.superviseur_profile

    return structure_filter, superviseur_filter


def _apply_tache_filters(taches_qs, site_id, structure_filter, superviseur_filter):
    """Applique les filtres site + rôle sur un queryset de Tache."""
    if site_id:
        taches_qs = taches_qs.filter(objets__site_id=site_id)
    if structure_filter:
        taches_qs = taches_qs.filter(objets__site__structure_client=structure_filter)
    elif superviseur_filter:
        taches_qs = taches_qs.filter(objets__site__superviseur=superviseur_filter)
    return taches_qs.distinct()


def _apply_reclamation_filters(reclamations_qs, site_id, structure_filter, superviseur_filter):
    """Applique les filtres site + rôle sur un queryset de Reclamation."""
    if site_id:
        reclamations_qs = reclamations_qs.filter(site_id=site_id)
    if structure_filter:
        reclamations_qs = reclamations_qs.filter(
            Q(structure_client=structure_filter) |
            Q(site__structure_client=structure_filter)
        )
    elif superviseur_filter:
        reclamations_qs = reclamations_qs.filter(site__superviseur=superviseur_filter)
    return reclamations_qs


def _apply_distribution_filters(dist_qs, site_id, structure_filter, superviseur_filter):
    """Applique les filtres site + rôle sur un queryset de DistributionCharge."""
    if site_id:
        dist_qs = dist_qs.filter(tache__objets__site_id=site_id)
    if structure_filter:
        dist_qs = dist_qs.filter(tache__objets__site__structure_client=structure_filter)
    elif superviseur_filter:
        dist_qs = dist_qs.filter(tache__objets__site__superviseur=superviseur_filter)
    return dist_qs.distinct()


# ==============================================================================
# CALCUL DES KPIs
# ==============================================================================

def _calc_respect_planning(taches_qs, month_start, month_end):
    """
    KPI 1: Respect du planning (>95%) — Global
    Taux = (tâches terminées avec retard ≤ 7j / total terminées du mois) × 100
    """
    completed = taches_qs.filter(
        statut='TERMINEE',
        date_fin_reelle__gte=month_start,
        date_fin_reelle__lte=month_end,
    )

    stats = completed.aggregate(
        total=Count('id'),
        dans_delais=Count('id', filter=Q(
            date_fin_reelle__lte=F('date_fin_planifiee') + timedelta(days=7)
        )),
    )

    total = stats['total']
    dans_delais = stats['dans_delais']
    valeur = round((dans_delais / total * 100), 1) if total > 0 else None

    return valeur, {
        'total_terminees': total,
        'dans_delais': dans_delais,
        'en_retard': total - dans_delais if total else 0,
    }


def _calc_qualite_service(reclamations_qs, month_start, month_end):
    """
    KPI 2: Qualité de service (>95%) — Global
    Taux = (notes SatisfactionClient ≥ 4 / total notes du mois) × 100
    """
    from api_reclamations.models import SatisfactionClient

    satisfaction_qs = SatisfactionClient.objects.filter(
        date_evaluation__gte=month_start,
        date_evaluation__lte=month_end,
        reclamation__in=reclamations_qs,
    )

    stats = satisfaction_qs.aggregate(
        total=Count('id'),
        satisfaits=Count('id', filter=Q(note__gte=4)),
        note_moyenne=Avg('note'),
    )

    total = stats['total']
    satisfaits = stats['satisfaits']
    valeur = round((satisfaits / total * 100), 1) if total > 0 else None

    return valeur, {
        'total_evaluations': total,
        'satisfaits': satisfaits,
        'insatisfaits': total - satisfaits if total else 0,
        'note_moyenne': round(stats['note_moyenne'], 2) if stats['note_moyenne'] else None,
    }


def _calc_taux_realisation_reclamations(reclamations_qs, month_start, month_end):
    """
    KPI 3: Taux de réalisation des réclamations — Global
    Taux = (ouvertes en M ET clôturées en M / total ouvertes en M) × 100
    """
    opened_in_month = reclamations_qs.filter(
        date_creation__gte=month_start,
        date_creation__lte=month_end,
    )

    stats = opened_in_month.aggregate(
        total_ouvertes=Count('id'),
        ouvertes_et_fermees=Count('id', filter=Q(
            statut__in=['CLOTUREE', 'RESOLUE'],
            date_cloture_reelle__gte=month_start,
            date_cloture_reelle__lte=month_end,
        )),
    )

    total = stats['total_ouvertes']
    fermees = stats['ouvertes_et_fermees']
    valeur = round((fermees / total * 100), 1) if total > 0 else None

    return valeur, {
        'total_ouvertes': total,
        'ouvertes_et_fermees': fermees,
        'non_realisees': total - fermees if total else 0,
    }


def _calc_temps_moyen_traitement(reclamations_qs, month_start, month_end):
    """
    KPI 4: Temps moyen de traitement des réclamations — Par TypeReclamation
    Temps = moyenne(date_cloture_reelle - date_creation) en heures
    Retourne un global + ventilation par type.
    """
    closed_in_month = reclamations_qs.filter(
        statut__in=['CLOTUREE', 'RESOLUE'],
        date_cloture_reelle__gte=month_start,
        date_cloture_reelle__lte=month_end,
        date_creation__isnull=False,
    ).annotate(
        delai=ExpressionWrapper(
            F('date_cloture_reelle') - F('date_creation'),
            output_field=DurationField()
        )
    )

    # Global
    stats_global = closed_in_month.aggregate(
        avg_delai=Avg('delai'),
        total_cloturees=Count('id'),
    )

    avg_global = None
    if stats_global['avg_delai'] is not None:
        avg_global = round(stats_global['avg_delai'].total_seconds() / 3600, 1)

    # Par type de réclamation
    par_type_qs = closed_in_month.values(
        'type_reclamation__nom_reclamation',
        'type_reclamation__categorie',
        'type_reclamation__id',
    ).annotate(
        avg_delai=Avg('delai'),
        total=Count('id'),
    ).order_by('type_reclamation__categorie')

    par_type = []
    for item in par_type_qs:
        avg_h = None
        if item['avg_delai'] is not None:
            avg_h = round(item['avg_delai'].total_seconds() / 3600, 1)
        par_type.append({
            'type_id': item['type_reclamation__id'],
            'nom': item['type_reclamation__nom_reclamation'] or 'Non défini',
            'categorie': item['type_reclamation__categorie'] or 'AUTRE',
            'valeur': avg_h,
            'total': item['total'],
        })

    return {
        'global': {
            'valeur': avg_global,
            'total_cloturees': stats_global['total_cloturees'],
        },
        'par_type': par_type,
    }


def _calc_temps_realisation_tache(dist_qs, month_start, month_end):
    """
    KPI 5: Temps de réalisation par tâche — Par TypeTache, par Site
    Temps cumulé(Type A, Site S) = Σ(heure_fin_reelle_i - heure_debut_reelle_i)
    Utilise les horaires réels de chaque DistributionCharge.
    """
    distributions = dist_qs.filter(
        date__gte=month_start,
        date__lte=month_end,
        status='REALISEE',
        heure_debut_reelle__isnull=False,
        heure_fin_reelle__isnull=False,
    )

    # Annoter avec la durée réelle en heures
    # heure_fin_reelle - heure_debut_reelle donne un timedelta
    # On agrège par (type_tache, site)
    par_type_site = list(
        distributions.values(
            'tache__id_type_tache__nom_tache',
            'tache__id_type_tache__id',
            'tache__objets__site__nom_site',
            'tache__objets__site__id',
        ).annotate(
            nb_interventions=Count('id'),
        ).order_by('tache__objets__site__nom_site', 'tache__id_type_tache__nom_tache')
    )

    # Calculer les heures manuellement car TimeField diff n'est pas
    # directement agrégeable en Django ORM. On récupère les données brutes.
    from api_planification.models import DistributionCharge as DC
    result = []
    seen = set()

    for item in par_type_site:
        type_id = item['tache__id_type_tache__id']
        site_id = item['tache__objets__site__id']
        key = (type_id, site_id)

        if key in seen:
            continue
        seen.add(key)

        # Récupérer les distributions pour ce type+site et calculer les heures
        dists = distributions.filter(
            tache__id_type_tache__id=type_id,
            tache__objets__site__id=site_id,
        ).distinct()

        total_seconds = 0
        nb = 0
        for d in dists.only('heure_debut_reelle', 'heure_fin_reelle'):
            h_debut = d.heure_debut_reelle
            h_fin = d.heure_fin_reelle
            if h_debut and h_fin:
                delta = datetime.combine(datetime.min, h_fin) - datetime.combine(datetime.min, h_debut)
                if delta.total_seconds() > 0:
                    total_seconds += delta.total_seconds()
                    nb += 1

        heures = round(total_seconds / 3600, 1) if total_seconds > 0 else 0

        result.append({
            'type_tache_id': type_id,
            'type_tache': item['tache__id_type_tache__nom_tache'] or 'Non défini',
            'site_id': site_id,
            'site_nom': item['tache__objets__site__nom_site'] or 'Non défini',
            'heures': heures,
            'nb_interventions': nb,
        })

    return result


def _calc_temps_total_par_site(dist_qs, month_start, month_end):
    """
    KPI 6: Temps total de travail par site — Par Site
    Heures totales(Site S) = Σ toutes les heures travaillées sur S durant le mois
    """
    distributions = dist_qs.filter(
        date__gte=month_start,
        date__lte=month_end,
        status='REALISEE',
    )

    # Utiliser heures_reelles en priorité, sinon heures_planifiees
    par_site = list(
        distributions.values(
            'tache__objets__site__id',
            'tache__objets__site__nom_site',
        ).annotate(
            total_heures=Sum(Coalesce('heures_reelles', 'heures_planifiees', output_field=FloatField())),
            nb_interventions=Count('id'),
        ).order_by('-total_heures')
    )

    total_global = 0
    result = []
    for item in par_site:
        heures = round(float(item['total_heures'] or 0), 1)
        total_global += heures
        result.append({
            'site_id': item['tache__objets__site__id'],
            'site_nom': item['tache__objets__site__nom_site'] or 'Non défini',
            'heures': heures,
            'nb_interventions': item['nb_interventions'],
        })

    return result, round(total_global, 1)


# ==============================================================================
# ORCHESTRATION
# ==============================================================================

def _calculate_all_kpis(month_start, month_end, site_id,
                        structure_filter, superviseur_filter):
    """Calcule les 6 KPIs pour une période donnée."""
    from api_planification.models import Tache, DistributionCharge
    from api_reclamations.models import Reclamation

    # Querysets de base
    taches_qs = _apply_tache_filters(
        Tache.objects.all(), site_id, structure_filter, superviseur_filter
    )
    reclamations_qs = _apply_reclamation_filters(
        Reclamation.objects.filter(actif=True), site_id, structure_filter, superviseur_filter
    )
    dist_qs = _apply_distribution_filters(
        DistributionCharge.objects.all(), site_id, structure_filter, superviseur_filter
    )

    # Dates au format date pour les champs DateField
    m_start_date = month_start.date() if hasattr(month_start, 'date') else month_start
    m_end_date = month_end.date() if hasattr(month_end, 'date') else month_end

    # KPI 1: Respect du planning
    kpi1_val, kpi1_details = _calc_respect_planning(taches_qs, m_start_date, m_end_date)

    # KPI 2: Qualité de service
    kpi2_val, kpi2_details = _calc_qualite_service(reclamations_qs, month_start, month_end)

    # KPI 3: Taux de réalisation des réclamations
    kpi3_val, kpi3_details = _calc_taux_realisation_reclamations(
        reclamations_qs, month_start, month_end
    )

    # KPI 4: Temps moyen de traitement (par type réclamation)
    kpi4_data = _calc_temps_moyen_traitement(reclamations_qs, month_start, month_end)

    # KPI 5: Temps de réalisation par tâche (par type tâche × site)
    kpi5_data = _calc_temps_realisation_tache(dist_qs, m_start_date, m_end_date)

    # KPI 6: Temps total par site
    kpi6_data, kpi6_total = _calc_temps_total_par_site(dist_qs, m_start_date, m_end_date)

    return {
        'respect_planning': kpi1_val,
        'respect_planning_details': kpi1_details,
        'qualite_service': kpi2_val,
        'qualite_service_details': kpi2_details,
        'taux_realisation_reclamations': kpi3_val,
        'taux_realisation_reclamations_details': kpi3_details,
        'temps_moyen_traitement': kpi4_data,
        'temps_realisation_tache': kpi5_data,
        'temps_total_par_site': kpi6_data,
        'temps_total_par_site_total': kpi6_total,
    }


# ==============================================================================
# VUE PRINCIPALE
# ==============================================================================

class KPIView(APIView):
    """
    GET /api/kpis/?mois=YYYY-MM&site_id=N

    Retourne les 6 KPIs pour le mois demandé + comparaison M-1.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # 1. Parse des paramètres
        mois_str = request.query_params.get('mois')
        site_id = request.query_params.get('site_id')

        if site_id:
            try:
                site_id = int(site_id)
            except (ValueError, TypeError):
                return Response(
                    {'error': 'site_id doit être un entier'},
                    status=drf_status.HTTP_400_BAD_REQUEST
                )

        # Mois cible (défaut : mois courant)
        now = timezone.now()
        if mois_str:
            try:
                target_date = datetime.strptime(mois_str, '%Y-%m')
            except ValueError:
                return Response(
                    {'error': 'Format invalide. Utilisez YYYY-MM'},
                    status=drf_status.HTTP_400_BAD_REQUEST
                )
        else:
            target_date = now
            mois_str = now.strftime('%Y-%m')

        # Date ranges
        month_start = target_date.replace(
            day=1, hour=0, minute=0, second=0,
            tzinfo=dt_timezone.utc
        ) if target_date.tzinfo is None else target_date.replace(day=1, hour=0, minute=0, second=0)
        month_end = (month_start + relativedelta(months=1)) - timedelta(seconds=1)
        prev_month_start = month_start - relativedelta(months=1)
        prev_month_end = month_start - timedelta(seconds=1)

        # 2. Filtres de rôle
        structure_filter, superviseur_filter = _get_role_filters(request.user)

        # 3. Cache
        cache_site_key = str(site_id or 'all')
        cache_role_key = 'admin'
        if structure_filter:
            cache_role_key = f'client_{structure_filter.id}'
        elif superviseur_filter:
            cache_role_key = f'sup_{superviseur_filter.utilisateur_id}'

        cached = cache_get('KPIS', mois_str, cache_site_key, cache_role_key)
        if cached:
            cached['cached'] = True
            return Response(cached)

        # 4. Calcul des KPIs pour M et M-1
        current = _calculate_all_kpis(
            month_start, month_end, site_id,
            structure_filter, superviseur_filter
        )
        previous = _calculate_all_kpis(
            prev_month_start, prev_month_end, site_id,
            structure_filter, superviseur_filter
        )

        # 5. Construction de la réponse
        result = {
            'mois': mois_str,
            'mois_precedent': prev_month_start.strftime('%Y-%m'),
            'kpis': {
                # KPI 1: Respect du planning — Global
                'respect_planning': {
                    'valeur': current['respect_planning'],
                    'valeur_m1': previous['respect_planning'],
                    'evolution': _calc_evolution(
                        current['respect_planning'],
                        previous['respect_planning']
                    ),
                    'seuil': 95.0,
                    'statut': _get_status(current['respect_planning'], 95.0),
                    'unite': '%',
                    'details': current['respect_planning_details'],
                },
                # KPI 2: Qualité de service — Global
                'qualite_service': {
                    'valeur': current['qualite_service'],
                    'valeur_m1': previous['qualite_service'],
                    'evolution': _calc_evolution(
                        current['qualite_service'],
                        previous['qualite_service']
                    ),
                    'seuil': 95.0,
                    'statut': _get_status(current['qualite_service'], 95.0),
                    'unite': '%',
                    'details': current['qualite_service_details'],
                },
                # KPI 3: Taux de réalisation des réclamations — Global
                'taux_realisation_reclamations': {
                    'valeur': current['taux_realisation_reclamations'],
                    'valeur_m1': previous['taux_realisation_reclamations'],
                    'evolution': _calc_evolution(
                        current['taux_realisation_reclamations'],
                        previous['taux_realisation_reclamations']
                    ),
                    'seuil': None,
                    'statut': _get_status(
                        current['taux_realisation_reclamations'], 80.0
                    ) if current['taux_realisation_reclamations'] is not None else 'gris',
                    'unite': '%',
                    'details': current['taux_realisation_reclamations_details'],
                },
                # KPI 4: Temps moyen traitement — Par TypeReclamation
                'temps_moyen_traitement': {
                    'global': {
                        'valeur': current['temps_moyen_traitement']['global']['valeur'],
                        'valeur_m1': previous['temps_moyen_traitement']['global']['valeur'],
                        'evolution': _calc_evolution_inverse(
                            current['temps_moyen_traitement']['global']['valeur'],
                            previous['temps_moyen_traitement']['global']['valeur']
                        ),
                        'seuil': 168,
                        'statut': _get_status_inverse(
                            current['temps_moyen_traitement']['global']['valeur'], 168.0
                        ),
                        'unite': 'h',
                        'total_cloturees': current['temps_moyen_traitement']['global']['total_cloturees'],
                    },
                    'par_type': current['temps_moyen_traitement']['par_type'],
                },
                # KPI 5: Temps de réalisation par tâche — Par TypeTache × Site
                'temps_realisation_tache': current['temps_realisation_tache'],
                # KPI 6: Temps total par site — Par Site
                'temps_total_par_site': {
                    'par_site': current['temps_total_par_site'],
                    'total_heures': current['temps_total_par_site_total'],
                    'total_heures_m1': previous['temps_total_par_site_total'],
                    'evolution': _calc_evolution(
                        current['temps_total_par_site_total'],
                        previous['temps_total_par_site_total']
                    ),
                },
            },
        }

        # 6. Cache
        is_current_month = (
            month_start.year == now.year and month_start.month == now.month
        )
        ttl = 300 if is_current_month else 3600
        cache_set('KPIS', mois_str, cache_site_key, cache_role_key, data=result, ttl=ttl)
        result['cached'] = False
        return Response(result)


# ==============================================================================
# VUE HISTORIQUE
# ==============================================================================

class KPIHistoriqueView(APIView):
    """
    GET /api/kpis/historique/?site_id=N&nb_mois=6

    Retourne les valeurs des KPIs globaux pour les N derniers mois.
    Utilisé pour les graphiques d'évolution.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        site_id = request.query_params.get('site_id')
        nb_mois = min(int(request.query_params.get('nb_mois', 6)), 12)

        if site_id:
            try:
                site_id = int(site_id)
            except (ValueError, TypeError):
                return Response(
                    {'error': 'site_id doit être un entier'},
                    status=drf_status.HTTP_400_BAD_REQUEST
                )

        structure_filter, superviseur_filter = _get_role_filters(request.user)

        # Cache
        cache_site_key = str(site_id or 'all')
        cache_role_key = 'admin'
        if structure_filter:
            cache_role_key = f'client_{structure_filter.id}'
        elif superviseur_filter:
            cache_role_key = f'sup_{superviseur_filter.utilisateur_id}'

        cached = cache_get('KPIS', 'historique', cache_site_key, cache_role_key, str(nb_mois))
        if cached:
            cached['cached'] = True
            return Response(cached)

        now = timezone.now()
        historique = []

        for i in range(nb_mois):
            target = now - relativedelta(months=i)
            m_start = target.replace(
                day=1, hour=0, minute=0, second=0, tzinfo=dt_timezone.utc
            )
            m_end = (m_start + relativedelta(months=1)) - timedelta(seconds=1)

            kpis = _calculate_all_kpis(
                m_start, m_end, site_id,
                structure_filter, superviseur_filter
            )

            historique.append({
                'mois': m_start.strftime('%Y-%m'),
                'mois_label': m_start.strftime('%b %Y'),
                'respect_planning': kpis['respect_planning'],
                'qualite_service': kpis['qualite_service'],
                'taux_realisation_reclamations': kpis['taux_realisation_reclamations'],
                'temps_moyen_traitement': kpis['temps_moyen_traitement']['global']['valeur'],
                'temps_total_heures': kpis['temps_total_par_site_total'],
            })

        # Ordre chronologique (plus ancien en premier)
        historique.reverse()

        result = {'historique': historique, 'nb_mois': nb_mois}

        cache_set(
            'KPIS', 'historique', cache_site_key, cache_role_key, str(nb_mois),
            data=result, ttl=300
        )
        result['cached'] = False
        return Response(result)
