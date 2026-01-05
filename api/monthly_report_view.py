# api/monthly_report_view.py
"""
Vue pour la génération du rapport de site.
Agrège toutes les données nécessaires pour le rapport PDF sur une période personnalisée.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
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
    permission_classes = [IsAuthenticated]

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

        return {
            'id': site.id,
            'nom': site.nom_site,
            'adresse': site.adresse,
            'superficie': site.superficie_totale,
            'centroid': centroid,
        }

    def _get_travaux_effectues(self, site_id, date_debut, date_fin):
        """Liste des travaux effectués sur la période (tâches terminées ET validées par l'admin)."""
        try:
            from api_planification.models import Tache

            # Filtrer les tâches liées au site via les objets
            taches = Tache.objects.filter(
                deleted_at__isnull=True,
                statut='TERMINEE',
                etat_validation='VALIDEE',
                date_fin_reelle__gte=date_debut,
                date_fin_reelle__lte=date_fin,
                objets__site_id=site_id
            ).distinct().select_related('id_type_tache')

            # Grouper par type de tâche
            types_count = {}
            for tache in taches:
                type_nom = tache.id_type_tache.nom_tache if tache.id_type_tache else 'Autre'
                if type_nom not in types_count:
                    types_count[type_nom] = {
                        'nom': type_nom,
                        'description': tache.id_type_tache.description if tache.id_type_tache else '',
                        'count': 0,
                    }
                types_count[type_nom]['count'] += 1

            # Convertir en liste
            result = []
            for type_nom, data in types_count.items():
                result.append({
                    'type': data['nom'],
                    'description': data['description'],
                    'count': data['count'],
                })

            return sorted(result, key=lambda x: x['count'], reverse=True)

        except Exception as e:
            return [{'error': str(e)}]

    def _get_travaux_planifies(self, site_id, date_fin):
        """Liste des travaux planifiés pour les 30 jours suivant la période."""
        try:
            from api_planification.models import Tache

            # Période suivante (30 jours après la date de fin)
            next_period_start = date_fin + timedelta(days=1)
            next_period_end = next_period_start + timedelta(days=30)

            taches = Tache.objects.filter(
                deleted_at__isnull=True,
                statut__in=['PLANIFIEE', 'NON_DEBUTEE'],
                date_debut_planifiee__gte=next_period_start,
                date_debut_planifiee__lte=next_period_end,
                objets__site_id=site_id
            ).distinct().select_related('id_type_tache')

            # Grouper par type
            types_list = {}
            for tache in taches:
                type_nom = tache.id_type_tache.nom_tache if tache.id_type_tache else 'Autre'
                if type_nom not in types_list:
                    types_list[type_nom] = 0
                types_list[type_nom] += 1

            return [{'type': k, 'count': v} for k, v in sorted(types_list.items(), key=lambda x: -x[1])]

        except Exception as e:
            return [{'error': str(e)}]

    def _get_equipes(self, site_id, date_debut, date_fin):
        """Équipes du site avec tous leurs membres et heures travaillées si disponibles."""
        try:
            from api_planification.models import ParticipationTache
            from api_users.models import Operateur, Equipe, StatutOperateur
            from django.db.models import Sum

            # 1. Récupérer les équipes - d'abord celles du site, sinon toutes les équipes actives
            equipes = Equipe.objects.filter(
                site_id=site_id,
                actif=True
            ).select_related('chef_equipe').prefetch_related('operateurs')

            # Si aucune équipe n'est affectée au site, récupérer toutes les équipes actives
            if not equipes.exists():
                print(f"[DEBUG] Aucune équipe affectée au site {site_id}, récupération de toutes les équipes actives")
                equipes = Equipe.objects.filter(
                    actif=True
                ).select_related('chef_equipe').prefetch_related('operateurs')

            print(f"[DEBUG] Nombre d'équipes trouvées: {equipes.count()}")

            # 2. Récupérer les heures travaillées par opérateur sur la période (si disponibles)
            heures_par_operateur = {}
            participations = ParticipationTache.objects.filter(
                id_tache__date_fin_reelle__gte=date_debut,
                id_tache__date_fin_reelle__lte=date_fin,
                id_tache__statut='TERMINEE',
                id_tache__etat_validation='VALIDEE',
                id_tache__objets__site_id=site_id
            ).values('id_operateur_id').annotate(
                total_heures=Sum('heures_travaillees')
            )

            for p in participations:
                if p['id_operateur_id']:
                    heures_par_operateur[p['id_operateur_id']] = float(p['total_heures'] or 0)

            print(f"[DEBUG] Heures par opérateur: {heures_par_operateur}")

            # 3. Construire le résultat avec toutes les équipes et tous leurs membres
            result = []
            for equipe in equipes:
                # Nom du chef d'équipe
                chef_nom = None
                if equipe.chef_equipe:
                    chef_nom = f"{equipe.chef_equipe.prenom} {equipe.chef_equipe.nom}".strip()

                # Liste des opérateurs de l'équipe (utiliser l'enum StatutOperateur)
                operateurs_list = []
                heures_totales = 0

                for op in equipe.operateurs.filter(statut=StatutOperateur.ACTIF):
                    op_nom = f"{op.prenom} {op.nom}".strip() or f"Opérateur {op.id}"
                    heures = heures_par_operateur.get(op.id, 0)
                    operateurs_list.append({
                        'id': op.id,
                        'nom': op_nom,
                        'heures': heures,
                    })
                    heures_totales += heures

                # Trier les opérateurs par heures (ceux avec des heures en premier)
                operateurs_list.sort(key=lambda x: -x['heures'])

                # Ajouter l'équipe avec son nom
                equipe_nom = equipe.nom_equipe or f"Équipe {equipe.id}"
                print(f"[DEBUG] Équipe: {equipe_nom}, {len(operateurs_list)} opérateurs")

                result.append({
                    'id': equipe.id,
                    'nom': equipe_nom,
                    'chef': chef_nom,
                    'operateurs': operateurs_list,
                    'heures_totales': heures_totales,
                })

            # 4. Ajouter les opérateurs sans équipe qui ont travaillé sur le site
            operateurs_sans_equipe = Operateur.objects.filter(
                equipe__isnull=True,
                statut=StatutOperateur.ACTIF,
                id__in=heures_par_operateur.keys()
            )

            if operateurs_sans_equipe.exists():
                ops_list = []
                heures_totales = 0
                for op in operateurs_sans_equipe:
                    op_nom = f"{op.prenom} {op.nom}".strip() or f"Opérateur {op.id}"
                    heures = heures_par_operateur.get(op.id, 0)
                    ops_list.append({
                        'id': op.id,
                        'nom': op_nom,
                        'heures': heures,
                    })
                    heures_totales += heures

                ops_list.sort(key=lambda x: -x['heures'])
                result.append({
                    'id': None,
                    'nom': 'Sans équipe',
                    'chef': None,
                    'operateurs': ops_list,
                    'heures_totales': heures_totales,
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
                zone__site_id=site_id
            ).select_related('zone', 'type_reclamation', 'urgence')

            result = []
            for rec in reclamations:
                result.append({
                    'id': rec.id,
                    'numero': rec.numero_reclamation,
                    'type': rec.type_reclamation.nom_reclamation if rec.type_reclamation else None,
                    'description': rec.description,
                    'statut': rec.statut,
                    'urgence': rec.urgence.nom_urgence if rec.urgence else None,
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
                deleted_at__isnull=True,
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

            # Réclamations sur le site
            reclamations_base = Reclamation.objects.filter(zone__site_id=site_id)

            reclamations_creees = reclamations_base.filter(
                date_creation__gte=date_debut,
                date_creation__lte=date_fin
            ).count()

            reclamations_resolues = reclamations_base.filter(
                statut__in=['RESOLUE', 'CLOTUREE'],
                date_cloture_reelle__gte=date_debut,
                date_cloture_reelle__lte=date_fin
            ).count()

            # Heures travaillées (uniquement des tâches validées sur ce site)
            participations = ParticipationTache.objects.filter(
                id_tache__date_fin_reelle__gte=date_debut,
                id_tache__date_fin_reelle__lte=date_fin,
                id_tache__statut='TERMINEE',
                id_tache__etat_validation='VALIDEE',
                id_tache__objets__site_id=site_id
            ).distinct()

            heures_totales = participations.aggregate(
                total=Sum('heures_travaillees')
            )['total'] or 0

            return {
                'taches_planifiees': taches_planifiees,
                'taches_terminees': taches_terminees,
                'taux_realisation': taux_realisation,
                'reclamations_creees': reclamations_creees,
                'reclamations_resolues': reclamations_resolues,
                'heures_travaillees': round(heures_totales, 1),
            }

        except Exception as e:
            import traceback
            print(f"[ERROR] _get_statistiques: {str(e)}")
            print(traceback.format_exc())
            return {'error': str(e)}