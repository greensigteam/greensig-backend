# api/monthly_report_view.py
"""
Vue pour la génération du rapport de site.
Agrège toutes les données nécessaires pour le rapport PDF sur une période personnalisée.
"""
import json

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from api_users.permissions import IsAdminOrSuperviseur
from rest_framework import status
from django.db.models import Count, Q, Sum
from django.utils import timezone
from datetime import datetime, timedelta, timezone as dt_timezone
from dateutil.parser import parse as parse_date

from .models import Site, SousSite


class MonthlyReportView(APIView):
    """
    Vue pour retourner les données du rapport de site sur une période personnalisée.

    GET /api/monthly-report/?site_id=1&date_debut=2025-12-01&date_fin=2025-12-31

    Paramètres:
        - site_id (int, requis): ID du site
        - date_debut (str, requis): Date de début au format YYYY-MM-DD
        - date_fin (str, requis): Date de fin au format YYYY-MM-DD

    Returns:
        {
            "periode": {"date_debut": "...", "date_fin": "...", "nb_jours": 31},
            "site": {...},
            "travaux_effectues": [...],
            "travaux_planifies": [...],
            "photos": [...],
            "reclamations": [...],
            "statistiques": {...}
        }
    """
    permission_classes = [IsAuthenticated, IsAdminOrSuperviseur]

    def get(self, request):
        # Paramètres obligatoires
        site_id = request.query_params.get('site_id')
        date_debut_str = request.query_params.get('date_debut')
        date_fin_str = request.query_params.get('date_fin')

        # Validation des paramètres
        if not site_id:
            return Response(
                {'error': 'Le paramètre site_id est obligatoire'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not date_debut_str or not date_fin_str:
            return Response(
                {'error': 'Les paramètres date_debut et date_fin sont obligatoires'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Parser les dates
        try:
            date_debut = datetime.strptime(date_debut_str, '%Y-%m-%d')
            date_debut = date_debut.replace(hour=0, minute=0, second=0, tzinfo=dt_timezone.utc)

            date_fin = datetime.strptime(date_fin_str, '%Y-%m-%d')
            date_fin = date_fin.replace(hour=23, minute=59, second=59, tzinfo=dt_timezone.utc)
        except ValueError:
            return Response(
                {'error': 'Format de date invalide. Utilisez YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Vérifier que date_fin >= date_debut
        if date_fin < date_debut:
            return Response(
                {'error': 'La date de fin doit être postérieure ou égale à la date de début'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Vérifier que le site existe
        try:
            site = Site.objects.get(id=site_id)
        except Site.DoesNotExist:
            return Response(
                {'error': 'Site non trouvé'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Calculer le nombre de jours
        nb_jours = (date_fin.date() - date_debut.date()).days + 1

        # Structure du rapport
        report = {
            'periode': {
                'date_debut': date_debut.isoformat(),
                'date_fin': date_fin.isoformat(),
                'nb_jours': nb_jours,
            },
            'site': self._get_site_info(site),
            'travaux_effectues': self._get_travaux_effectues(site_id, date_debut, date_fin),
            'travaux_planifies': self._get_travaux_planifies(site_id, date_fin),
            'equipes': self._get_equipes(site_id, date_debut, date_fin),
            'photos': self._get_photos(site_id, date_debut, date_fin),
            'reclamations': self._get_reclamations(site_id, date_debut, date_fin),
            'statistiques': self._get_statistiques(site_id, date_debut, date_fin),
        }

        return Response(report)

    def _get_site_info(self, site):
        """Informations du site avec coordonnées pour la carte."""
        # Récupérer les coordonnées du centroid si disponible
        centroid = None
        if site.centroid:
            centroid = {
                'lng': site.centroid.x,
                'lat': site.centroid.y
            }
        elif site.geometrie_emprise:
            # Calculer le centroid à partir de l'emprise
            center = site.geometrie_emprise.centroid
            centroid = {
                'lng': center.x,
                'lat': center.y
            }

        geometry = None
        if site.geometrie_emprise:
            geometry = json.loads(site.geometrie_emprise.geojson)

        return {
            'id': site.id,
            'nom': site.nom_site,
            'adresse': site.adresse,
            'superficie': site.superficie_totale,
            'centroid': centroid,
            'geometry': geometry,
        }

    def _get_travaux_effectues(self, site_id, date_debut, date_fin):
        """
        Planning des travaux effectués sur la période (distributions réalisées).

        Retourne le format planning style export:
        - planning: Liste des distributions avec date, reference, type, equipes, horaires, charge, statut, priorite
        - statistiques: Total, heures, répartition par statut
        """
        try:
            from api_planification.models import DistributionCharge

            # Mapping statut vers labels
            STATUT_LABELS = {
                'NON_REALISEE': 'A faire',
                'EN_COURS': 'En cours',
                'REALISEE': 'Réalisée',
                'REPORTEE': 'Reportée',
                'ANNULEE': 'Annulée',
            }

            PRIORITE_LABELS = {
                1: 'P1 - Très basse',
                2: 'P2 - Basse',
                3: 'P3 - Moyenne',
                4: 'P4 - Haute',
                5: 'P5 - Urgent',
            }

            # Filtrer les distributions réalisées liées au site via les objets de la tâche
            distributions = DistributionCharge.objects.filter(
                date__gte=date_debut,
                date__lte=date_fin,
                status='REALISEE',
                tache__objets__site_id=site_id
            ).distinct().select_related(
                'tache',
                'tache__id_type_tache'
            ).prefetch_related(
                'tache__equipes'
            ).order_by('date', 'heure_debut')

            # Construire le planning
            planning = []
            statuts_count = {}
            total_heures = 0

            for dist in distributions:
                tache = dist.tache

                # Date
                date_str = dist.date.strftime('%Y-%m-%d') if dist.date else None

                # Reference
                ref_str = tache.reference or f'T-{tache.id}'

                # Type de tâche
                type_str = tache.id_type_tache.nom_tache if tache.id_type_tache else 'Autre'

                # Équipes
                equipes_list = list(tache.equipes.all())
                equipes_str = ', '.join([eq.nom_equipe for eq in equipes_list]) if equipes_list else 'Non assignée'

                # Horaires
                horaires_str = None
                if dist.heure_debut and dist.heure_fin:
                    horaires_str = f"{dist.heure_debut.strftime('%H:%M')} - {dist.heure_fin.strftime('%H:%M')}"

                # Charge (heures réelles si disponibles, sinon planifiées)
                charge = dist.heures_reelles if dist.heures_reelles else dist.heures_planifiees
                total_heures += charge or 0

                # Statut
                statut = dist.status
                statut_label = STATUT_LABELS.get(statut, statut)
                statuts_count[statut] = statuts_count.get(statut, 0) + 1

                # Priorité
                priorite = tache.priorite or 3
                priorite_label = PRIORITE_LABELS.get(priorite, f'P{priorite}')

                planning.append({
                    'id': dist.id,
                    'tache_id': tache.id,
                    'date': date_str,
                    'reference': ref_str,
                    'type': type_str,
                    'equipes': equipes_str,
                    'horaires': horaires_str,
                    'charge': round(charge, 1) if charge else 0,
                    'statut': statut,
                    'statut_label': statut_label,
                    'priorite': priorite,
                    'priorite_label': priorite_label,
                })

            return {
                'planning': planning,
                'statistiques': {
                    'total': len(distributions),
                    'total_heures': round(total_heures, 1),
                    'par_statut': statuts_count,
                },
            }

        except Exception as e:
            import traceback
            print(f"[ERROR] _get_travaux_effectues: {str(e)}")
            print(traceback.format_exc())
            return {'planning': [], 'statistiques': {'total': 0, 'total_heures': 0, 'par_statut': {}}, 'error': str(e)}

    def _get_travaux_planifies(self, site_id, date_fin):
        """
        Planning des travaux planifiés pour les 30 jours suivant la période.

        Retourne le format planning style export:
        - planning: Liste des distributions avec date, reference, type, equipes, horaires, charge, statut, priorite
        - statistiques: Total, heures, répartition par statut
        """
        try:
            from api_planification.models import DistributionCharge

            # Mapping statut vers labels
            STATUT_LABELS = {
                'NON_REALISEE': 'A faire',
                'EN_COURS': 'En cours',
                'REALISEE': 'Réalisée',
                'REPORTEE': 'Reportée',
                'ANNULEE': 'Annulée',
            }

            PRIORITE_LABELS = {
                1: 'P1 - Très basse',
                2: 'P2 - Basse',
                3: 'P3 - Moyenne',
                4: 'P4 - Haute',
                5: 'P5 - Urgent',
            }

            # Période suivante (30 jours après la date de fin)
            next_period_start = date_fin + timedelta(days=1)
            next_period_end = next_period_start + timedelta(days=30)

            # Filtrer les distributions à venir (non réalisées, non annulées)
            distributions = DistributionCharge.objects.filter(
                date__gte=next_period_start,
                date__lte=next_period_end,
                status__in=['NON_REALISEE', 'EN_COURS'],
                tache__objets__site_id=site_id
            ).distinct().select_related(
                'tache',
                'tache__id_type_tache'
            ).prefetch_related(
                'tache__equipes'
            ).order_by('date', 'heure_debut')

            # Construire le planning
            planning = []
            statuts_count = {}
            total_heures = 0

            for dist in distributions:
                tache = dist.tache

                # Date
                date_str = dist.date.strftime('%Y-%m-%d') if dist.date else None

                # Reference
                ref_str = tache.reference or f'T-{tache.id}'

                # Type de tâche
                type_str = tache.id_type_tache.nom_tache if tache.id_type_tache else 'Autre'

                # Équipes
                equipes_list = list(tache.equipes.all())
                equipes_str = ', '.join([eq.nom_equipe for eq in equipes_list]) if equipes_list else 'Non assignée'

                # Horaires
                horaires_str = None
                if dist.heure_debut and dist.heure_fin:
                    horaires_str = f"{dist.heure_debut.strftime('%H:%M')} - {dist.heure_fin.strftime('%H:%M')}"

                # Charge planifiée
                charge = dist.heures_planifiees or 0
                total_heures += charge

                # Statut
                statut = dist.status
                statut_label = STATUT_LABELS.get(statut, statut)
                statuts_count[statut] = statuts_count.get(statut, 0) + 1

                # Priorité
                priorite = tache.priorite or 3
                priorite_label = PRIORITE_LABELS.get(priorite, f'P{priorite}')

                planning.append({
                    'id': dist.id,
                    'tache_id': tache.id,
                    'date': date_str,
                    'reference': ref_str,
                    'type': type_str,
                    'equipes': equipes_str,
                    'horaires': horaires_str,
                    'charge': round(charge, 1) if charge else 0,
                    'statut': statut,
                    'statut_label': statut_label,
                    'priorite': priorite,
                    'priorite_label': priorite_label,
                })

            return {
                'planning': planning,
                'statistiques': {
                    'total': len(distributions),
                    'total_heures': round(total_heures, 1),
                    'par_statut': statuts_count,
                },
            }

        except Exception as e:
            import traceback
            print(f"[ERROR] _get_travaux_planifies: {str(e)}")
            print(traceback.format_exc())
            return {'planning': [], 'statistiques': {'total': 0, 'total_heures': 0, 'par_statut': {}}, 'error': str(e)}

    def _get_equipes(self, site_id, date_debut, date_fin):
        """Équipes du site avec tous leurs membres et heures travaillées si disponibles."""
        try:
            from api_planification.models import ParticipationTache, Tache
            from api_users.models import Operateur, Equipe, StatutOperateur
            from django.db.models import Sum

            # 1. Récupérer les tâches terminées et validées sur la période FIRST
            #    pour identifier les équipes qui ont RÉELLEMENT travaillé
            taches_periode = Tache.objects.filter(
                statut='TERMINEE',
                etat_validation='VALIDEE',
                date_fin_reelle__gte=date_debut,
                date_fin_reelle__lte=date_fin,
                objets__site_id=site_id
            ).distinct().prefetch_related(
                'participations__id_operateur',
                'distributions_charge',
                'equipes'
            )

            # Récupérer les IDs de toutes les équipes qui ont travaillé sur ces tâches
            equipes_ids_actives = set()
            for tache in taches_periode:
                for equipe in tache.equipes.all():
                    equipes_ids_actives.add(equipe.id)

            print(f"[DEBUG] Équipes qui ont travaillé sur le site (IDs): {equipes_ids_actives}")

            # Récupérer TOUTES les équipes qui ont travaillé (même si non assignées au site)
            if equipes_ids_actives:
                equipes = Equipe.objects.filter(
                    id__in=equipes_ids_actives
                ).select_related('chef_equipe').prefetch_related('operateurs')
            else:
                # Fallback: équipes assignées au site
                equipes = Equipe.objects.filter(
                    site_id=site_id,
                    actif=True
                ).select_related('chef_equipe').prefetch_related('operateurs')

            print(f"[DEBUG] Nombre d'équipes trouvées: {equipes.count()}")
            print(f"[DEBUG] Équipes récupérées: {[eq.nom_equipe or f'Équipe {eq.id}' for eq in equipes]}")

            # 2. Calculer les heures RÉELLES par équipe (sans multiplication)
            # Les heures d'une équipe = somme des heures des tâches qu'elle a effectuées
            heures_par_equipe = {}
            for tache in taches_periode:
                temps_travail = tache.temps_travail_total
                heures_tache = temps_travail['heures']

                # Chaque équipe qui a travaillé sur la tâche compte les heures UNE SEULE FOIS
                equipes_tache = tache.equipes.all()
                if equipes_tache:
                    # Répartir les heures entre les équipes assignées
                    heures_par_equipe_tache = heures_tache / len(equipes_tache)
                    equipes_noms = [eq.nom_equipe or f'Équipe {eq.id}' for eq in equipes_tache]
                    print(f"[DEBUG] Tâche #{tache.id} ({heures_tache}h) → {len(equipes_tache)} équipe(s): {equipes_noms}")
                    for eq in equipes_tache:
                        heures_par_equipe[eq.id] = heures_par_equipe.get(eq.id, 0) + heures_par_equipe_tache
                else:
                    print(f"[DEBUG] Tâche #{tache.id} ({heures_tache}h) → AUCUNE ÉQUIPE")

            print(f"[DEBUG] Heures RÉELLES par équipe: {heures_par_equipe}")
            print(f"[DEBUG] Somme des heures par équipe: {sum(heures_par_equipe.values())}h")

            # Calculer le total de TOUTES les tâches (pour comparaison)
            total_heures_taches = sum(tache.temps_travail_total['heures'] for tache in taches_periode)
            print(f"[DEBUG] Total heures de toutes les tâches: {total_heures_taches}h")

            # Compter les tâches avec et sans équipes
            taches_avec_equipes = sum(1 for tache in taches_periode if tache.equipes.exists())
            taches_sans_equipes = len(taches_periode) - taches_avec_equipes
            print(f"[DEBUG] Tâches avec équipes: {taches_avec_equipes}, sans équipes: {taches_sans_equipes}")

            # 4. Construire le résultat avec toutes les équipes et tous leurs membres
            result = []
            for equipe in equipes:
                # Nom du chef d'équipe
                chef_nom = None
                if equipe.chef_equipe:
                    chef_nom = f"{equipe.chef_equipe.prenom} {equipe.chef_equipe.nom}".strip()

                # IMPORTANT: heures_totales = heures RÉELLES de l'équipe (pas la somme des opérateurs)
                heures_totales_equipe = heures_par_equipe.get(equipe.id, 0)

                # Calculer les heures INDIVIDUELLES par opérateur en tenant compte des absences
                # Priorité 1: Utiliser les participations si disponibles (heures réelles enregistrées)
                # Priorité 2: Répartir équitablement entre opérateurs NON ABSENTS
                from api_users.models import Absence

                heures_par_operateur_dict = {}
                operateurs_actifs = equipe.operateurs.filter(statut=StatutOperateur.ACTIF)

                # Récupérer les absences sur la période
                absences = Absence.objects.filter(
                    operateur__in=operateurs_actifs,
                    date_debut__lte=date_fin,
                    date_fin__gte=date_debut,
                    statut='VALIDEE'
                ).select_related('operateur')

                # Set des IDs d'opérateurs absents
                operateurs_absents_ids = set(abs.operateur_id for abs in absences)

                # Compter les opérateurs PRÉSENTS (non absents)
                operateurs_presents = [op for op in operateurs_actifs if op.id not in operateurs_absents_ids]
                nb_operateurs_presents = len(operateurs_presents)

                # Calculer les heures par opérateur en excluant les absents
                heures_par_operateur_equipe = heures_totales_equipe / nb_operateurs_presents if nb_operateurs_presents > 0 else 0

                print(f"[DEBUG] Équipe {equipe.nom_equipe}: {len(operateurs_actifs)} opérateurs, {len(operateurs_absents_ids)} absents, {nb_operateurs_presents} présents")

                # Liste des opérateurs de l'équipe
                operateurs_list = []

                for op in operateurs_actifs:
                    op_nom = f"{op.prenom} {op.nom}".strip() or f"Opérateur {op.id}"

                    # Si opérateur absent sur la période → 0h
                    if op.id in operateurs_absents_ids:
                        heures = 0.0
                    else:
                        # Répartition équitable entre présents
                        heures = heures_par_operateur_equipe

                    operateurs_list.append({
                        'id': op.id,
                        'nom': op_nom,
                        'heures': round(heures, 1),
                        'absent': op.id in operateurs_absents_ids,  # Flag pour l'affichage
                    })

                # Trier: présents en premier (par heures desc), puis absents
                operateurs_list.sort(key=lambda x: (-x['heures'], x['nom']))

                # Ajouter l'équipe avec son nom
                equipe_nom = equipe.nom_equipe or f"Équipe {equipe.id}"
                print(f"[DEBUG] Équipe: {equipe_nom}, {len(operateurs_list)} opérateurs, {heures_totales_equipe}h ({heures_par_operateur_equipe}h/op)")

                result.append({
                    'id': equipe.id,
                    'nom': equipe_nom,
                    'chef': chef_nom,
                    'operateurs': operateurs_list,
                    'heures_totales': round(heures_totales_equipe, 1),
                })

            # 5. Ajouter les tâches sans équipe (si elles existent)
            # Calculer les heures RÉELLES pour les tâches sans équipe
            heures_totales_sans_equipe = 0
            for tache in taches_periode:
                # Vérifier si cette tâche n'a pas d'équipe assignée
                if not tache.equipes.exists():
                    temps_travail = tache.temps_travail_total
                    heures_totales_sans_equipe += temps_travail['heures']

            # Si des tâches sans équipe existent, les ajouter au résultat
            if heures_totales_sans_equipe > 0:
                # Chercher les opérateurs sans équipe qui ont travaillé (via participations)
                operateurs_sans_equipe = []
                heures_par_op_sans_equipe = {}

                for tache in taches_periode:
                    if not tache.equipes.exists():
                        participations = tache.participations.all()
                        if participations:
                            for part in participations:
                                if part.id_operateur:
                                    op = part.id_operateur
                                    if op.equipe is None:  # Opérateur sans équipe
                                        heures_par_op_sans_equipe[op.id] = heures_par_op_sans_equipe.get(op.id, 0) + part.heures_travaillees
                                        if op not in operateurs_sans_equipe:
                                            operateurs_sans_equipe.append(op)

                ops_list = []
                for op in operateurs_sans_equipe:
                    op_nom = f"{op.prenom} {op.nom}".strip() or f"Opérateur {op.id}"
                    heures = heures_par_op_sans_equipe.get(op.id, 0)
                    ops_list.append({
                        'id': op.id,
                        'nom': op_nom,
                        'heures': round(heures, 1),
                    })

                ops_list.sort(key=lambda x: -x['heures'])

                result.append({
                    'id': None,
                    'nom': 'Sans équipe',
                    'chef': None,
                    'operateurs': ops_list,
                    'heures_totales': round(heures_totales_sans_equipe, 1),
                })

            print(f"[DEBUG] Résultat final: {len(result)} équipes")
            return result

        except Exception as e:
            import traceback
            print(f"[ERROR] _get_equipes: {str(e)}")
            print(traceback.format_exc())
            return []

    def _get_photos(self, site_id, date_debut, date_fin):
        """Photos avant/après sur le site pour la période."""
        try:
            from api_suivi_taches.models import Photo

            # Récupérer toutes les photos AVANT/APRES liées au site
            # Via objet.site OU via tache.objets.site
            photos = Photo.objects.filter(
                date_prise__gte=date_debut,
                date_prise__lte=date_fin,
                type_photo__in=['AVANT', 'APRES']
            ).filter(
                Q(objet__site_id=site_id) | Q(tache__objets__site_id=site_id)
            ).distinct().select_related('tache', 'tache__id_type_tache', 'objet')

            # Grouper par tâche
            photos_by_task = {}
            for photo in photos:
                task_id = photo.tache_id if photo.tache else f"obj_{photo.objet_id}"
                if task_id not in photos_by_task:
                    tache_nom = None
                    if photo.tache and photo.tache.id_type_tache:
                        tache_nom = photo.tache.id_type_tache.nom_tache
                    photos_by_task[task_id] = {
                        'tache_id': photo.tache_id,
                        'tache_nom': tache_nom,
                        'avant': [],
                        'apres': [],
                    }

                photo_data = {
                    'id': photo.id,
                    'url': photo.fichier.url if photo.fichier else None,
                    'date': photo.date_prise.isoformat() if photo.date_prise else None,
                    'commentaire': photo.legende,
                }

                if photo.type_photo == 'AVANT':
                    photos_by_task[task_id]['avant'].append(photo_data)
                else:
                    photos_by_task[task_id]['apres'].append(photo_data)

            # Retourner toutes les photos groupées (pas besoin de paires obligatoires)
            result = list(photos_by_task.values())

            return result[:20]  # Limiter à 20 groupes

        except Exception as e:
            return [{'error': str(e)}]

    def _get_reclamations(self, site_id, date_debut, date_fin):
        """Réclamations et points d'attention sur le site."""
        try:
            from api_reclamations.models import Reclamation

            reclamations = Reclamation.objects.filter(
                date_creation__gte=date_debut,
                date_creation__lte=date_fin,
                site_id=site_id,
                actif=True  # Exclure les réclamations supprimées
            ).select_related('zone', 'type_reclamation', 'urgence')

            result = []
            for rec in reclamations:
                result.append({
                    'id': rec.id,
                    'numero': rec.numero_reclamation,
                    'type': rec.type_reclamation.nom_reclamation if rec.type_reclamation else None,
                    'description': rec.description,
                    'statut': rec.statut,
                    'urgence': rec.urgence.niveau_urgence if rec.urgence else None,
                    'date': rec.date_creation.isoformat(),
                    'zone': rec.zone.nom if rec.zone else None,
                })

            return result

        except Exception as e:
            return [{'error': str(e)}]

    def _get_statistiques(self, site_id, date_debut, date_fin):
        """
        Statistiques globales de la période.

        Logique métier:
        - Tâches planifiées: tâches dont la date de début OU de fin planifiée tombe dans la période
        - Tâches terminées: tâches terminées ET validées avec date_fin_reelle dans la période
        - Taux de réalisation: parmi les tâches planifiées pour cette période, combien sont terminées+validées
        """
        try:
            from api_planification.models import Tache, ParticipationTache
            from api_reclamations.models import Reclamation

            # Tâches liées au site
            taches_base = Tache.objects.filter(
                objets__site_id=site_id
            ).distinct()

            # Tâches PLANIFIÉES pour cette période
            # = tâches dont date_debut_planifiee OU date_fin_planifiee tombe dans la période
            taches_planifiees_qs = taches_base.filter(
                Q(date_debut_planifiee__gte=date_debut, date_debut_planifiee__lte=date_fin) |
                Q(date_fin_planifiee__gte=date_debut, date_fin_planifiee__lte=date_fin) |
                Q(date_debut_planifiee__lte=date_debut, date_fin_planifiee__gte=date_fin)  # Tâche qui englobe la période
            )
            taches_planifiees = taches_planifiees_qs.count()

            # Tâches TERMINÉES sur cette période (validées par l'admin)
            taches_terminees = taches_base.filter(
                statut='TERMINEE',
                etat_validation='VALIDEE',
                date_fin_reelle__gte=date_debut,
                date_fin_reelle__lte=date_fin
            ).count()

            # TAUX DE RÉALISATION: parmi les tâches planifiées, combien sont terminées+validées
            # = tâches planifiées pour cette période ET qui sont maintenant TERMINEE+VALIDEE
            taches_planifiees_et_terminees = taches_planifiees_qs.filter(
                statut='TERMINEE',
                etat_validation='VALIDEE'
            ).count()

            taux_realisation = round(
                taches_planifiees_et_terminees / taches_planifiees * 100, 1
            ) if taches_planifiees > 0 else 0

            # Réclamations sur le site (utiliser le champ site direct, zone peut être NULL)
            reclamations_base = Reclamation.objects.filter(site_id=site_id, actif=True)

            reclamations_creees = reclamations_base.filter(
                date_creation__gte=date_debut,
                date_creation__lte=date_fin
            ).count()

            reclamations_resolues = reclamations_base.filter(
                statut='CLOTUREE',
                date_cloture_reelle__gte=date_debut,
                date_cloture_reelle__lte=date_fin
            ).count()

            # Heures travaillées (uniquement des tâches validées sur ce site)
            # ✅ LOGIQUE CORRIGÉE: Simple somme des heures de toutes les tâches
            # Une tâche = ses heures (pas multiplication par nombre d'opérateurs)
            taches_terminees_periode = Tache.objects.filter(
                statut='TERMINEE',
                etat_validation='VALIDEE',
                date_fin_reelle__gte=date_debut,
                date_fin_reelle__lte=date_fin,
                objets__site_id=site_id
            ).distinct().prefetch_related('distributions_charge', 'participations')

            # Calculer le total et le ratio de productivité
            heures_totales = 0
            heures_theoriques_totales = 0

            for tache in taches_terminees_periode:
                temps_travail = tache.temps_travail_total
                heures_reelles = temps_travail['heures']
                heures_totales += heures_reelles

                # Ajouter les heures théoriques (charge estimée)
                if tache.charge_estimee_heures and tache.charge_estimee_heures > 0:
                    heures_theoriques_totales += tache.charge_estimee_heures

            # Ratio de productivité: heures réelles / heures théoriques * 100
            # < 100% = plus efficace (moins de temps que prévu)
            # > 100% = moins efficace (plus de temps que prévu)
            # = 100% = conforme à la norme
            ratio_productivite = None
            if heures_theoriques_totales > 0 and heures_totales > 0:
                ratio_productivite = round((heures_totales / heures_theoriques_totales) * 100, 1)

            return {
                'taches_planifiees': taches_planifiees,
                'taches_terminees': taches_terminees,
                'taux_realisation': taux_realisation,
                'reclamations_creees': reclamations_creees,
                'reclamations_resolues': reclamations_resolues,
                'heures_travaillees': round(heures_totales, 1),
                'heures_theoriques': round(heures_theoriques_totales, 1),
                'ratio_productivite': ratio_productivite,
            }

        except Exception as e:
            import traceback
            print(f"[ERROR] _get_statistiques: {str(e)}")
            print(traceback.format_exc())
            return {'error': str(e)}