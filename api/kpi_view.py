# api/kpi_view.py
"""
Vue pour les KPIs de performance.
Implémente les 5 KPIs définis:
1. Respect du planning de l'entretien (>95%, aucun retard >7 jours)
2. Taux mensuel de réalisation de réclamation
3. Temps moyen de traitement des réclamations
4. Temps de réalisation par tâche
5. Temps total de travail par site
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Avg, Sum, Q, F, ExpressionWrapper, DurationField
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import timedelta, date, datetime
from dateutil.relativedelta import relativedelta

from .models import Site


class KPIView(APIView):
    """
    Vue pour retourner les KPIs de performance.

    GET /api/kpis/
    GET /api/kpis/?site_id=1
    GET /api/kpis/?type_tache_id=5
    GET /api/kpis/?site_id=1&type_tache_id=5
    GET /api/kpis/?mois=2026-01
    GET /api/kpis/?site_id=1&type_tache_id=5&mois=2026-01

    Returns:
        {
            "periode": {
                "mois": "2026-01",
                "debut": "2026-01-01",
                "fin": "2026-01-31"
            },
            "kpis": {
                "respect_planning": {...},
                "taux_realisation_reclamations": {...},
                "temps_moyen_traitement_reclamations": {...},
                "temps_realisation_taches": {...},
                "temps_travail_par_site": {...}
            },
            "evolution": {
                "mois_precedent": {...},
                "variation": {...}
            },
            "sites_disponibles": [...],
            "types_taches_disponibles": [...]
        }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Paramètres de filtrage
        site_id = request.query_params.get('site_id')
        type_tache_id = request.query_params.get('type_tache_id')
        mois_param = request.query_params.get('mois')  # Format: YYYY-MM

        # Déterminer la période (en utilisant des dates, pas des datetimes)
        today = timezone.now().date()
        if mois_param:
            try:
                annee, mois = mois_param.split('-')
                date_debut = date(int(annee), int(mois), 1)
            except (ValueError, TypeError):
                date_debut = today.replace(day=1)
        else:
            date_debut = today.replace(day=1)

        # Date de fin du mois
        next_month = date_debut + relativedelta(months=1)
        date_fin = next_month - timedelta(days=1)

        # Mois précédent pour l'évolution
        date_debut_precedent = date_debut - relativedelta(months=1)
        date_fin_precedent = date_debut - timedelta(days=1)

        # Site filter
        site_filter = {'id': site_id} if site_id else {}

        # Construire la réponse
        periode = {
            'mois': date_debut.strftime('%Y-%m'),
            'debut': date_debut.strftime('%Y-%m-%d'),
            'fin': date_fin.strftime('%Y-%m-%d'),
        }

        kpis = {
            'respect_planning': self._get_respect_planning(date_debut, date_fin, site_id, type_tache_id),
            'taux_realisation_reclamations': self._get_taux_realisation_reclamations(date_debut, date_fin, site_id),
            'temps_moyen_traitement_reclamations': self._get_temps_moyen_traitement_reclamations(date_debut, date_fin, site_id),
            'temps_realisation_taches': self._get_temps_realisation_taches(date_debut, date_fin, site_id, type_tache_id),
            'temps_travail_par_site': self._get_temps_travail_par_site(date_debut, date_fin, site_id, type_tache_id),
        }

        # Évolution par rapport au mois précédent
        kpis_precedent = {
            'respect_planning': self._get_respect_planning(date_debut_precedent, date_fin_precedent, site_id, type_tache_id),
            'taux_realisation_reclamations': self._get_taux_realisation_reclamations(date_debut_precedent, date_fin_precedent, site_id),
            'temps_moyen_traitement_reclamations': self._get_temps_moyen_traitement_reclamations(date_debut_precedent, date_fin_precedent, site_id),
            'temps_realisation_taches': self._get_temps_realisation_taches(date_debut_precedent, date_fin_precedent, site_id, type_tache_id),
            'temps_travail_par_site': self._get_temps_travail_par_site(date_debut_precedent, date_fin_precedent, site_id, type_tache_id),
        }

        evolution = self._calculer_evolution(kpis, kpis_precedent)

        # Sites et types de tâches disponibles pour les filtres
        sites_disponibles = self._get_sites_disponibles(request.user)
        types_taches_disponibles = self._get_types_taches_disponibles()

        return Response({
            'periode': periode,
            'kpis': kpis,
            'evolution': evolution,
            'sites_disponibles': sites_disponibles,
            'types_taches_disponibles': types_taches_disponibles,
        })

    def _get_respect_planning(self, date_debut, date_fin, site_id=None, type_tache_id=None):
        """
        KPI 1: Respect du planning de l'entretien
        Objectif: >95%, aucun retard de plus de 7 jours

        ✅ CORRIGÉ: Selon le document KPI page 2 ligne 59-60:
        "au moins 95 % des tâches d'entretien PLANIFIÉES sont réalisées sans dépasser un retard de 7 jours"

        On filtre par date_fin_planifiee (tâches planifiées dans M), pas date_fin_reelle

        Formule: (Tâches planifiées et terminées sans retard > 7j / Total tâches planifiées et terminées) × 100
        """
        try:
            from api_planification.models import Tache

            # ✅ CORRECTION: Filtre de base = tâches PLANIFIÉES dans la période M
            queryset = Tache.objects.filter(
                deleted_at__isnull=True,
                date_fin_planifiee__gte=date_debut,  # ✅ PLANIFIÉES dans M
                date_fin_planifiee__lte=date_fin,
                statut='TERMINEE',  # Parmi celles terminées
                date_fin_reelle__isnull=False
            )

            # Filtre par site si spécifié
            if site_id:
                queryset = queryset.filter(
                    Q(objets__site_id=site_id) |
                    Q(reclamation__site_id=site_id)
                ).distinct()

            # ✅ NOUVEAU: Filtre par type de tâche si spécifié
            if type_tache_id:
                queryset = queryset.filter(id_type_tache_id=type_tache_id)

            total_planifiees = queryset.count()

            # ✅ CORRECTION: Vérifier DÉBUT ET FIN (dates au pluriel dans le document)
            # Selon le document: "sans dépasser un retard de 7 jours par rapport aux dates prévues"
            taches_conformes = 0
            taches_retard_critique = []
            taches_en_avance = 0
            taches_retard_1_7j = 0
            taches_distributions_incompletes = []  # ✅ NOUVEAU: Tâches avec distributions non réalisées

            for tache in queryset.prefetch_related('distributions_charge'):
                # ✅ NOUVEAU: Vérifier que TOUTES les distributions sont REALISEE
                total_distributions = tache.distributions_charge.count()
                distributions_realisees = tache.distributions_charge.filter(status='REALISEE').count()

                # Si la tâche a des distributions mais pas toutes réalisées, elle n'est pas vraiment terminée
                if total_distributions > 0 and distributions_realisees < total_distributions:
                    taches_distributions_incompletes.append({
                        'id': tache.id,
                        'titre': getattr(tache, 'titre', f'Tâche #{tache.id}'),
                        'total_distributions': total_distributions,
                        'distributions_realisees': distributions_realisees,
                        'pourcentage_realisation': round(distributions_realisees / total_distributions * 100, 1),
                    })
                    continue  # Ne pas compter cette tâche comme conforme

                if tache.date_debut_reelle and tache.date_debut_planifiee and \
                   tache.date_fin_reelle and tache.date_fin_planifiee:

                    # Calcul des retards sur DÉBUT et FIN
                    retard_debut = (tache.date_debut_reelle - tache.date_debut_planifiee).days
                    retard_fin = (tache.date_fin_reelle - tache.date_fin_planifiee).days

                    # Le retard maximum détermine la conformité
                    retard_max = max(retard_debut, retard_fin)

                    if retard_max <= 0:
                        # Tâche démarrée et terminée à l'heure ou en avance (conforme)
                        taches_en_avance += 1
                        taches_conformes += 1
                    elif retard_max <= 7:
                        # Retard acceptable ≤ 7j sur début ou fin (conforme)
                        taches_retard_1_7j += 1
                        taches_conformes += 1
                    else:
                        # Retard > 7j sur début OU fin (non conforme)
                        taches_retard_critique.append({
                            'id': tache.id,
                            'titre': getattr(tache, 'titre', f'Tâche #{tache.id}'),
                            'retard_debut_jours': retard_debut,
                            'retard_fin_jours': retard_fin,
                            'retard_max_jours': retard_max,
                            'date_debut_planifiee': tache.date_debut_planifiee.strftime('%Y-%m-%d'),
                            'date_debut_reelle': tache.date_debut_reelle.strftime('%Y-%m-%d'),
                            'date_fin_planifiee': tache.date_fin_planifiee.strftime('%Y-%m-%d'),
                            'date_fin_reelle': tache.date_fin_reelle.strftime('%Y-%m-%d'),
                        })

            # Calcul du taux (exclut les tâches avec distributions incomplètes)
            taches_evaluees = total_planifiees - len(taches_distributions_incompletes)
            taux = (taches_conformes / taches_evaluees * 100) if taches_evaluees > 0 else 0
            objectif_atteint = taux >= 95 and len(taches_retard_critique) == 0 and len(taches_distributions_incompletes) == 0

            # ✅ Messages d'alerte combinés
            alertes = []
            if taches_retard_critique:
                alertes.append(f"{len(taches_retard_critique)} tâche(s) avec retard > 7 jours")
            if taches_distributions_incompletes:
                alertes.append(f"{len(taches_distributions_incompletes)} tâche(s) marquées terminées mais distributions incomplètes")

            return {
                'valeur': round(taux, 1),
                'objectif': 95,
                'unite': '%',
                'objectif_atteint': objectif_atteint,
                'details': {
                    'total_planifiees': total_planifiees,
                    'taches_evaluees': taches_evaluees,  # ✅ Tâches réellement évaluées
                    'taches_conformes': taches_conformes,
                    'taches_en_avance': taches_en_avance,
                    'taches_retard_1_7j': taches_retard_1_7j,
                    'taches_retard_critique': len(taches_retard_critique),
                    'taches_distributions_incompletes': len(taches_distributions_incompletes),  # ✅ NOUVEAU
                    'details_retards_critiques': taches_retard_critique[:10],  # Top 10
                    'details_distributions_incompletes': taches_distributions_incompletes[:10],  # ✅ NOUVEAU: Top 10
                },
                'alerte': len(alertes) > 0,
                'message_alerte': ' | '.join(alertes) if alertes else None,
            }
        except Exception as e:
            import traceback
            return {
                'valeur': 0,
                'objectif': 95,
                'unite': '%',
                'objectif_atteint': False,
                'error': str(e),
                'traceback': traceback.format_exc(),
            }

    def _get_taux_realisation_reclamations(self, date_debut, date_fin, site_id=None):
        """
        KPI 2: Taux mensuel de réalisation de réclamation

        Selon le document:
        - Seules les réclamations ouvertes ET clôturées sur la période M sont comptabilisées comme réalisées
        - Ouverte en M et clôturée en M : comptée comme réalisée
        - Ouverte en M et clôturée en M+1 : non réalisés pour M
        - Ouverte en M-1 et clôturée en M : exclue du calcul

        Formule: (Réclamations ouvertes ET clôturées durant M) / (Total réclamations ouvertes durant M) × 100
        """
        try:
            from api_reclamations.models import Reclamation

            # Convertir les dates en datetime timezone-aware
            date_debut_dt = timezone.make_aware(datetime.combine(date_debut, datetime.min.time()))
            date_fin_dt = timezone.make_aware(datetime.combine(date_fin, datetime.max.time()))

            # Réclamations OUVERTES dans la période M
            queryset_ouvertes = Reclamation.objects.filter(
                date_creation__gte=date_debut_dt,
                date_creation__lte=date_fin_dt
            )

            if site_id:
                queryset_ouvertes = queryset_ouvertes.filter(site_id=site_id)

            total_ouvertes = queryset_ouvertes.count()

            # Réclamations ouvertes ET clôturées dans la même période M
            realisees = queryset_ouvertes.filter(
                statut='CLOTUREE',
                date_cloture_reelle__isnull=False,
                date_cloture_reelle__gte=date_debut_dt,
                date_cloture_reelle__lte=date_fin_dt
            ).count()

            # Par statut pour le détail
            par_statut = dict(
                queryset_ouvertes.values('statut')
                .annotate(count=Count('id'))
                .values_list('statut', 'count')
            )

            # Calcul du taux
            taux = (realisees / total_ouvertes * 100) if total_ouvertes > 0 else 0

            return {
                'valeur': round(taux, 1),
                'objectif': 100,
                'unite': '%',
                'objectif_atteint': taux >= 90,
                'details': {
                    'total_ouvertes': total_ouvertes,
                    'realisees': realisees,
                    'non_realisees': total_ouvertes - realisees,
                    'en_cours': par_statut.get('EN_COURS', 0),
                    'nouvelles': par_statut.get('NOUVELLE', 0),
                    'par_statut': par_statut,
                },
            }
        except Exception as e:
            return {
                'valeur': 0,
                'objectif': 100,
                'unite': '%',
                'objectif_atteint': False,
                'error': str(e),
            }

    def _get_temps_moyen_traitement_reclamations(self, date_debut, date_fin, site_id=None):
        """
        KPI 3: Temps moyen de traitement des réclamations PAR TYPE DE RÉCLAMATION

        Selon le document:
        - Mesure le délai moyen de traitement pour chaque TYPE de réclamation
        - Seules les réclamations clôturées durant le mois M sont prises en compte

        Formule: Σ(Date de clôture - date d'ouverture) / Nombre total de réclamations clôturées durant M
        """
        try:
            from api_reclamations.models import Reclamation

            # Convertir les dates en datetime timezone-aware
            date_debut_dt = timezone.make_aware(datetime.combine(date_debut, datetime.min.time()))
            date_fin_dt = timezone.make_aware(datetime.combine(date_fin, datetime.max.time()))

            # Réclamations clôturées dans la période M
            queryset = Reclamation.objects.filter(
                statut='CLOTUREE',
                date_cloture_reelle__gte=date_debut_dt,
                date_cloture_reelle__lte=date_fin_dt,
                date_cloture_reelle__isnull=False
            )

            if site_id:
                queryset = queryset.filter(site_id=site_id)

            total_cloturees = queryset.count()
            delais = []
            details_par_type = {}

            for rec in queryset.select_related('type_reclamation'):
                if rec.date_creation and rec.date_cloture_reelle:
                    delta = rec.date_cloture_reelle - rec.date_creation
                    heures = delta.total_seconds() / 3600
                    delais.append(heures)

                    # Grouper par TYPE de réclamation (conformément au document)
                    type_nom = rec.type_reclamation.nom_reclamation if rec.type_reclamation else 'Non défini'
                    if type_nom not in details_par_type:
                        details_par_type[type_nom] = {
                            'count': 0,
                            'delais': [],
                        }
                    details_par_type[type_nom]['count'] += 1
                    details_par_type[type_nom]['delais'].append(heures)

            # Calculer les moyennes par type de réclamation
            for type_rec, data in details_par_type.items():
                if data['delais']:
                    data['moyenne_heures'] = round(sum(data['delais']) / len(data['delais']), 1)
                    del data['delais']

            temps_moyen = sum(delais) / len(delais) if delais else 0

            return {
                'valeur': round(temps_moyen, 1),
                'objectif': 48,  # Objectif: 48h max
                'unite': 'heures',
                'objectif_atteint': temps_moyen <= 48 if temps_moyen > 0 else None,
                'details': {
                    'total_cloturees': total_cloturees,
                    'temps_min': round(min(delais), 1) if delais else 0,
                    'temps_max': round(max(delais), 1) if delais else 0,
                    'par_type_reclamation': details_par_type,
                },
            }
        except Exception as e:
            return {
                'valeur': 0,
                'objectif': 48,
                'unite': 'heures',
                'objectif_atteint': False,
                'error': str(e),
            }

    def _get_temps_realisation_taches(self, date_debut, date_fin, site_id=None, type_tache_id=None):
        """
        KPI 4: Temps de réalisation par tâche

        Selon le document:
        - Temps cumulé de réalisation (Tâche A, Site S) = Σ(Heure fin - Heure début) pour chaque tâche de type A dans site S
        - Groupé par TYPE de tâche ET par SITE

        ✅ CORRIGÉ: Utilise les DistributionCharge pour un calcul précis basé sur les heures réelles
        Formule: Σ(heures_reelles) de toutes les distributions de charge
        """
        try:
            from api_planification.models import Tache, ParticipationTache

            # Tâches terminées dans la période
            queryset = Tache.objects.filter(
                deleted_at__isnull=True,
                statut='TERMINEE',
                date_fin_reelle__isnull=False,
                date_debut_reelle__isnull=False,
                date_fin_reelle__gte=date_debut,
                date_fin_reelle__lte=date_fin
            )

            if site_id:
                queryset = queryset.filter(
                    Q(objets__site_id=site_id) |
                    Q(reclamation__site_id=site_id)
                ).distinct()

            # ✅ NOUVEAU: Filtre par type de tâche si spécifié
            if type_tache_id:
                queryset = queryset.filter(id_type_tache_id=type_tache_id)

            total_taches = queryset.count()
            durees = []
            details_par_type = {}
            details_par_site = {}  # ✅ NOUVEAU: Groupement par site uniquement
            details_par_site_type = {}  # Groupement par site ET type

            for tache in queryset.select_related('id_type_tache').prefetch_related('objets', 'reclamation', 'distributions_charge', 'participations'):
                # ✅ NOUVEAU: Utiliser temps_travail_total (Option 2: Approche Hybride)
                temps_travail = tache.temps_travail_total
                heures = temps_travail['heures']
                durees.append(heures)

                # Type de tâche
                type_nom = tache.id_type_tache.nom_tache if tache.id_type_tache else 'Non défini'

                # Identifier le site
                site_nom = "Non attribué"
                site_obj = None
                for objet in tache.objets.all():
                    if objet.site:
                        site_obj = objet.site
                        site_nom = site_obj.nom_site
                        break
                if not site_obj and tache.reclamation and tache.reclamation.site:
                    site_obj = tache.reclamation.site
                    site_nom = site_obj.nom_site

                # Grouper par type de tâche (global)
                if type_nom not in details_par_type:
                    details_par_type[type_nom] = {
                        'count': 0,
                        'total_heures': 0,
                        'durees': [],  # ✅ Pour calculer écart-type
                    }
                details_par_type[type_nom]['count'] += 1
                details_par_type[type_nom]['total_heures'] += heures
                details_par_type[type_nom]['durees'].append(heures)

                # ✅ NOUVEAU: Grouper par site uniquement
                if site_nom not in details_par_site:
                    details_par_site[site_nom] = {
                        'count': 0,
                        'total_heures': 0,
                        'durees': [],
                    }
                details_par_site[site_nom]['count'] += 1
                details_par_site[site_nom]['total_heures'] += heures
                details_par_site[site_nom]['durees'].append(heures)

                # Grouper par site ET type (conformément au document)
                if site_nom not in details_par_site_type:
                    details_par_site_type[site_nom] = {}
                if type_nom not in details_par_site_type[site_nom]:
                    details_par_site_type[site_nom][type_nom] = {
                        'count': 0,
                        'total_heures': 0,
                        'durees': [],
                    }
                details_par_site_type[site_nom][type_nom]['count'] += 1
                details_par_site_type[site_nom][type_nom]['total_heures'] += heures
                details_par_site_type[site_nom][type_nom]['durees'].append(heures)

            # Calcul de la moyenne globale pour comparaisons
            temps_total = sum(durees) if durees else 0
            temps_moyen_global = temps_total / total_taches if total_taches > 0 else 0

            # ✅ Calculer écart-type pour identifier inefficacités
            import statistics

            # Calculer moyennes et écart-types par type
            par_type_array = []
            for type_tache, data in details_par_type.items():
                moyenne = data['total_heures'] / data['count'] if data['count'] > 0 else 0
                ecart_type = round(statistics.stdev(data['durees']), 1) if len(data['durees']) > 1 else 0
                ecart_moyenne = round(((moyenne - temps_moyen_global) / temps_moyen_global * 100), 1) if temps_moyen_global > 0 else 0

                par_type_array.append({
                    'type_tache': type_tache,
                    'count': data['count'],
                    'total_heures': round(data['total_heures'], 1),
                    'moyenne_heures': round(moyenne, 1),
                    'ecart_type': ecart_type,
                    'ecart_moyenne_global': ecart_moyenne,  # ✅ % écart vs moyenne globale
                    'inefficace': moyenne > temps_moyen_global * 1.2,  # ✅ +20% = inefficace
                })

            # Trier par moyenne décroissante (les plus lentes en premier)
            par_type_array.sort(key=lambda x: x['moyenne_heures'], reverse=True)

            # ✅ Calculer moyennes par site
            par_site_array = []
            for site_nom, data in details_par_site.items():
                moyenne = data['total_heures'] / data['count'] if data['count'] > 0 else 0
                ecart_type = round(statistics.stdev(data['durees']), 1) if len(data['durees']) > 1 else 0
                ecart_moyenne = round(((moyenne - temps_moyen_global) / temps_moyen_global * 100), 1) if temps_moyen_global > 0 else 0

                par_site_array.append({
                    'site_nom': site_nom,
                    'count': data['count'],
                    'total_heures': round(data['total_heures'], 1),
                    'moyenne_heures': round(moyenne, 1),
                    'ecart_type': ecart_type,
                    'ecart_moyenne_global': ecart_moyenne,
                    'inefficace': moyenne > temps_moyen_global * 1.2,
                })

            # Trier par moyenne décroissante
            par_site_array.sort(key=lambda x: x['moyenne_heures'], reverse=True)

            # ✅ Convertir site ET type en array
            par_site_et_type_array = []
            for site_nom, types in details_par_site_type.items():
                for type_nom, data in types.items():
                    moyenne = data['total_heures'] / data['count'] if data['count'] > 0 else 0
                    ecart_type = round(statistics.stdev(data['durees']), 1) if len(data['durees']) > 1 else 0

                    par_site_et_type_array.append({
                        'site_nom': site_nom,
                        'type_tache': type_nom,
                        'count': data['count'],
                        'total_heures': round(data['total_heures'], 1),
                        'moyenne_heures': round(moyenne, 1),
                        'ecart_type': ecart_type,
                    })

            # Trier par moyenne décroissante
            par_site_et_type_array.sort(key=lambda x: x['moyenne_heures'], reverse=True)

            return {
                'valeur': round(temps_moyen_global, 1),
                'objectif': None,
                'unite': 'heures/tâche',
                'objectif_atteint': None,
                'details': {
                    'total_taches': total_taches,
                    'total_heures': round(temps_total, 1),
                    'moyenne_globale': round(temps_moyen_global, 1),  # ✅ Pour comparaisons
                    'par_type': par_type_array,  # ✅ Array avec écart-types et inefficacités
                    'par_site': par_site_array,  # ✅ NOUVEAU: Groupement par site
                    'par_site_et_type': par_site_et_type_array,
                },
            }
        except Exception as e:
            return {
                'valeur': 0,
                'objectif': None,
                'unite': 'heures',
                'objectif_atteint': None,
                'error': str(e),
            }

    def _get_temps_travail_par_site(self, date_debut, date_fin, site_id=None, type_tache_id=None):
        """
        KPI 5: Temps total de travail par site

        ✅ CORRIGÉ: Utilise les DistributionCharge pour un calcul précis basé sur les heures réelles
        Formule: Σ(heures_reelles) de toutes les distributions de charge par site
        """
        try:
            from api_planification.models import Tache, ParticipationTache
            from django.db.models import Sum

            # Tâches terminées dans la période
            queryset = Tache.objects.filter(
                deleted_at__isnull=True,
                statut='TERMINEE',
                date_fin_reelle__isnull=False,
                date_fin_reelle__gte=date_debut,
                date_fin_reelle__lte=date_fin
            )

            if site_id:
                queryset = queryset.filter(
                    Q(objets__site_id=site_id) |
                    Q(reclamation__site_id=site_id)
                ).distinct()

            # ✅ NOUVEAU: Filtre par type de tâche si spécifié
            if type_tache_id:
                queryset = queryset.filter(id_type_tache_id=type_tache_id)

            sites_heures = {}
            total_heures = 0

            for tache in queryset.prefetch_related('objets', 'reclamation', 'distributions_charge', 'participations'):
                # ✅ NOUVEAU: Utiliser temps_travail_total (Option 2: Approche Hybride)
                temps_travail = tache.temps_travail_total
                heures = temps_travail['heures']

                # Si aucune donnée, passer cette tâche
                if heures == 0:
                    continue

                # Identifier le site
                site = None
                site_nom = "Non attribué"

                # Via les objets liés
                for objet in tache.objets.all():
                    if objet.site:
                        site = objet.site
                        site_nom = site.nom_site
                        break

                # Via la réclamation
                if not site and tache.reclamation and tache.reclamation.site:
                    site = tache.reclamation.site
                    site_nom = site.nom_site

                site_key = site.id if site else 0

                if site_key not in sites_heures:
                    sites_heures[site_key] = {
                        'site_id': site_key,
                        'site_nom': site_nom,
                        'heures': 0,
                        'nb_taches': 0,
                    }

                sites_heures[site_key]['heures'] += heures
                sites_heures[site_key]['nb_taches'] += 1
                total_heures += heures

            # Convertir en liste et trier
            sites_list = sorted(
                sites_heures.values(),
                key=lambda x: x['heures'],
                reverse=True
            )

            # Arrondir les heures
            for site_data in sites_list:
                site_data['heures'] = round(site_data['heures'], 1)

            return {
                'valeur': round(total_heures, 1),
                'objectif': None,
                'unite': 'heures',
                'objectif_atteint': None,
                'details': {
                    'nb_sites': len(sites_list),
                    'par_site': sites_list[:10],  # Top 10
                },
            }
        except Exception as e:
            return {
                'valeur': 0,
                'objectif': None,
                'unite': 'heures',
                'objectif_atteint': None,
                'error': str(e),
            }

    def _calculer_evolution(self, kpis_actuel, kpis_precedent):
        """Calculer l'évolution par rapport au mois précédent."""
        evolution = {}

        for kpi_name in kpis_actuel.keys():
            valeur_actuelle = kpis_actuel[kpi_name].get('valeur', 0)
            valeur_precedente = kpis_precedent[kpi_name].get('valeur', 0)

            if valeur_precedente and valeur_precedente != 0:
                variation_pct = ((valeur_actuelle - valeur_precedente) / valeur_precedente) * 100
            else:
                variation_pct = 0 if valeur_actuelle == 0 else 100

            evolution[kpi_name] = {
                'valeur_precedente': round(valeur_precedente, 1),
                'variation': round(valeur_actuelle - valeur_precedente, 1),
                'variation_pct': round(variation_pct, 1),
                'tendance': 'hausse' if variation_pct > 0 else ('baisse' if variation_pct < 0 else 'stable'),
            }

        return evolution

    def _get_sites_disponibles(self, user):
        """
        Récupérer tous les sites actifs.
        Les KPIs sont gérés uniquement par les admins, donc on retourne tous les sites.
        """
        from .models import Site

        queryset = Site.objects.filter(actif=True).order_by('nom_site')
        return [{'id': site.id, 'nom': site.nom_site} for site in queryset]

    def _get_types_taches_disponibles(self):
        """
        Récupérer tous les types de tâches actifs pour le filtre.
        """
        from api_planification.models import TypeTache

        queryset = TypeTache.objects.all().order_by('nom_tache')
        return [{'id': type_tache.id, 'nom': type_tache.nom_tache} for type_tache in queryset]


class KPIHistoriqueView(APIView):
    """
    Vue pour l'historique des KPIs sur plusieurs mois.

    GET /api/kpis/historique/
    GET /api/kpis/historique/?site_id=1&type_tache_id=5&nb_mois=6

    Returns:
        {
            "historique": [
                {"mois": "2025-12", "kpis": {...}},
                {"mois": "2026-01", "kpis": {...}},
                ...
            ]
        }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        site_id = request.query_params.get('site_id')
        type_tache_id = request.query_params.get('type_tache_id')
        nb_mois = int(request.query_params.get('nb_mois', 6))
        nb_mois = min(nb_mois, 12)  # Maximum 12 mois

        kpi_view = KPIView()
        historique = []

        today = timezone.now().date()

        for i in range(nb_mois - 1, -1, -1):
            # Calculer le premier jour du mois (date object, not datetime)
            target_date = today - relativedelta(months=i)
            date_debut = date(target_date.year, target_date.month, 1)
            # Dernier jour du mois
            next_month = date_debut + relativedelta(months=1)
            date_fin = next_month - timedelta(days=1)

            mois_data = {
                'mois': date_debut.strftime('%Y-%m'),
                'kpis': {
                    'respect_planning': kpi_view._get_respect_planning(date_debut, date_fin, site_id, type_tache_id)['valeur'],
                    'taux_realisation_reclamations': kpi_view._get_taux_realisation_reclamations(date_debut, date_fin, site_id)['valeur'],
                    'temps_moyen_traitement_reclamations': kpi_view._get_temps_moyen_traitement_reclamations(date_debut, date_fin, site_id)['valeur'],
                    'temps_realisation_taches': kpi_view._get_temps_realisation_taches(date_debut, date_fin, site_id, type_tache_id)['valeur'],
                    'temps_travail_par_site': kpi_view._get_temps_travail_par_site(date_debut, date_fin, site_id, type_tache_id)['valeur'],
                }
            }
            historique.append(mois_data)

        return Response({'historique': historique})
