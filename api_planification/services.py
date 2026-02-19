import datetime
import logging
from typing import Dict, Optional, Tuple
from django.db import transaction
from django.db.models import QuerySet
from .models import Tache, RatioProductivite, DistributionCharge

logger = logging.getLogger(__name__)


class WorkloadCalculationService:
    """
    Service pour calculer la charge de travail estimée d'une tâche
    basée sur les objets liés et les ratios de productivité.
    """

    # Classification des types d'objets par type de géométrie
    POINT_OBJECTS = ['Arbre', 'Palmier', 'Puit', 'Pompe', 'Vanne', 'Clapet', 'Ballon']
    POLYGON_OBJECTS = ['Gazon', 'Arbuste', 'Vivace', 'Cactus', 'Graminee']
    LINE_OBJECTS = ['Canalisation', 'Aspersion', 'Goutte']

    @staticmethod
    def _get_work_hours_for_day(equipe, date):
        """
        Retourne les heures travaillables pour une équipe à une date donnée.

        Args:
            equipe: Instance d'Equipe
            date: datetime.date ou datetime.datetime

        Returns:
            float: Nombre d'heures travaillables dans la journée (défaut: 8h si pas d'horaire)
        """
        if not equipe:
            return 8.0  # Défaut si pas d'équipe

        # Convertir en date si datetime
        if isinstance(date, datetime.datetime):
            date = date.date()

        # Mapper jour de semaine (0=lundi, 6=dimanche) vers code BDD
        jours_mapping = {
            0: 'LUN',
            1: 'MAR',
            2: 'MER',
            3: 'JEU',
            4: 'VEN',
            5: 'SAM',
            6: 'DIM',
        }
        jour_code = jours_mapping[date.weekday()]

        # Chercher l'horaire actif pour cette équipe et ce jour
        try:
            from api_users.models import HoraireTravail
            horaire = HoraireTravail.objects.get(
                equipe=equipe,
                jour_semaine=jour_code,
                actif=True
            )
            return horaire.heures_travaillables
        except Exception:
            # Pas d'horaire défini, utiliser des valeurs par défaut intelligentes
            # Samedi : 4h (08:00-12:00), Dimanche : 0h, Autres jours : 8h
            if jour_code == 'SAM':
                logger.debug(f"Pas d'horaire pour équipe {equipe.id} le samedi. Défaut: 4h (08:00-12:00)")
                return 4.0
            elif jour_code == 'DIM':
                logger.debug(f"Pas d'horaire pour équipe {equipe.id} le dimanche. Défaut: 0h (repos)")
                return 0.0
            else:
                logger.debug(f"Pas d'horaire pour équipe {equipe.id} le {jour_code}. Défaut: 8h")
                return 8.0

    @staticmethod
    def _est_weekend(date):
        """
        Vérifie si une date tombe un weekend (dimanche uniquement).

        Note: Le samedi est considéré comme jour travaillé (demi-journée jusqu'à midi).

        Args:
            date: datetime.date ou datetime.datetime

        Returns:
            bool: True si dimanche, False sinon
        """
        if isinstance(date, datetime.datetime):
            date = date.date()

        # 6 = dimanche (samedi retiré car travaillé jusqu'à midi)
        return date.weekday() == 6

    @staticmethod
    def _est_jour_ferie(date):
        """
        Vérifie si une date est un jour férié.

        Args:
            date: datetime.date ou datetime.datetime

        Returns:
            bool: True si jour férié, False sinon
        """
        try:
            from api_users.models import JourFerie
            return JourFerie.est_jour_ferie(date, actif_uniquement=True)
        except Exception:
            return False

    @staticmethod
    def _est_equipe_disponible(equipe, date):
        """
        Vérifie si une équipe a suffisamment de membres disponibles pour une date.

        Critère: Au moins 50% des membres actifs doivent être disponibles.

        Args:
            equipe: Instance d'Equipe
            date: datetime.date ou datetime.datetime

        Returns:
            bool: True si équipe disponible, False sinon
        """
        if not equipe:
            return True  # Pas d'équipe = pas de contrainte

        # Convertir en date si datetime
        if isinstance(date, datetime.datetime):
            date = date.date()

        try:
            from api_users.models import StatutOperateur, Absence, StatutAbsence

            # Compter les membres actifs
            membres_actifs = equipe.operateurs.filter(statut=StatutOperateur.ACTIF)
            nombre_membres = membres_actifs.count()

            if nombre_membres == 0:
                logger.warning(f"Équipe {equipe.id} n'a aucun membre actif")
                return False

            # Compter les membres en absence ce jour-là
            absences = Absence.objects.filter(
                operateur__in=membres_actifs,
                statut=StatutAbsence.VALIDEE,
                date_debut__lte=date,
                date_fin__gte=date
            )
            nombre_absents = absences.count()
            nombre_presents = nombre_membres - nombre_absents

            # Critère: au moins 50% des membres doivent être présents
            seuil_minimum = nombre_membres * 0.5
            disponible = nombre_presents >= seuil_minimum

            if not disponible:
                logger.info(
                    f"Équipe {equipe.id} indisponible le {date}: "
                    f"{nombre_presents}/{nombre_membres} présents (seuil: {seuil_minimum:.0f})"
                )

            return disponible
        except Exception as e:
            logger.warning(f"Erreur vérification disponibilité équipe: {e}")
            return True

    @staticmethod
    def _est_jour_travaillable(equipe, date, skip_weekends=True, skip_holidays=True, check_availability=True):
        """
        Vérifie si un jour est travaillable pour une équipe.

        Args:
            equipe: Instance d'Equipe
            date: datetime.date ou datetime.datetime
            skip_weekends: Si True, exclut les weekends
            skip_holidays: Si True, exclut les jours fériés
            check_availability: Si True, vérifie la disponibilité de l'équipe

        Returns:
            bool: True si jour travaillable, False sinon
        """
        # Vérifier weekend
        if skip_weekends and WorkloadCalculationService._est_weekend(date):
            return False

        # Vérifier jour férié
        if skip_holidays and WorkloadCalculationService._est_jour_ferie(date):
            return False

        # Vérifier disponibilité équipe
        if check_availability and not WorkloadCalculationService._est_equipe_disponible(equipe, date):
            return False

        return True

    @classmethod
    def calculate_workload(cls, tache: Tache) -> Optional[float]:
        """
        Calcule la charge estimée en heures pour une tâche.

        Args:
            tache: Instance de Tache avec objets et type_tache

        Returns:
            Charge en heures ou None si calcul impossible
        """
        if not tache.id_type_tache_id:
            logger.warning(f"Tache {tache.id}: Pas de type de tâche défini")
            return None

        objets = tache.objets.all()
        if not objets.exists():
            logger.info(f"Tache {tache.id}: Aucun objet lié, charge = 0")
            return 0.0

        # Récupérer les ratios de productivité pour ce type de tâche
        ratios = cls._get_ratios_for_task_type(tache.id_type_tache_id)
        if not ratios:
            logger.warning(f"Tache {tache.id}: Aucun ratio défini pour le type {tache.id_type_tache}")
            return None

        total_hours = 0.0
        objects_without_ratio = []

        # Grouper les objets par type
        objects_by_type = cls._group_objects_by_type(objets)

        for type_objet, objs in objects_by_type.items():
            if type_objet not in ratios:
                objects_without_ratio.append(type_objet)
                continue

            ratio_info = ratios[type_objet]
            quantity = cls._calculate_quantity(objs, type_objet, ratio_info['unite_mesure'])

            if quantity > 0 and ratio_info['ratio'] > 0:
                hours = quantity / ratio_info['ratio']
                total_hours += hours
                logger.debug(f"  {type_objet}: {quantity} {ratio_info['unite_mesure']} / {ratio_info['ratio']} = {hours:.2f}h")

        if objects_without_ratio:
            logger.warning(f"Tache {tache.id}: Types sans ratio défini: {objects_without_ratio}")

        return round(total_hours, 2)

    @classmethod
    def _get_ratios_for_task_type(cls, type_tache_id: int) -> Dict[str, dict]:
        """
        Récupère les ratios de productivité pour un type de tâche.

        Returns:
            Dict mapping type_objet -> {ratio, unite_mesure}
        """
        ratios = RatioProductivite.objects.filter(
            id_type_tache_id=type_tache_id,
            actif=True
        ).values('type_objet', 'ratio', 'unite_mesure')

        return {
            r['type_objet']: {'ratio': r['ratio'], 'unite_mesure': r['unite_mesure']}
            for r in ratios
        }

    @classmethod
    def _group_objects_by_type(cls, objets: QuerySet) -> Dict[str, list]:
        """
        Groupe les objets par leur type réel (Arbre, Gazon, etc.).

        Optimisé : 15 requêtes IN au total au lieu de N×15 requêtes lazy.
        Pour 400 objets, passe de ~6000 queries à 15.
        """
        from api.models import (
            Arbre, Palmier, Gazon, Arbuste, Vivace, Cactus, Graminee,
            Puit, Pompe, Vanne, Clapet, Canalisation, Aspersion, Goutte, Ballon
        )

        CHILD_MODELS = [
            Arbre, Palmier, Gazon, Arbuste, Vivace, Cactus, Graminee,
            Puit, Pompe, Vanne, Clapet, Canalisation, Aspersion, Goutte, Ballon
        ]

        objet_ids = set(objets.values_list('id', flat=True))
        grouped: Dict[str, list] = {}

        for Model in CHILD_MODELS:
            # Une seule requête par type : SELECT ... WHERE objet_ptr_id IN (...)
            children = Model.objects.filter(objet_ptr_id__in=objet_ids)
            child_list = list(children)
            if child_list:
                grouped[Model.__name__] = child_list

        return grouped

    @classmethod
    def _calculate_quantity(cls, objets: list, type_objet: str, unite_mesure: str) -> float:
        """
        Calcule la quantité totale pour un groupe d'objets.
        Les objets sont déjà des instances typées (Arbre, Gazon, etc.),
        pas besoin de get_type_reel().

        Args:
            objets: Liste d'instances typées (déjà résolues par _group_objects_by_type)
            type_objet: Nom du type (Arbre, Gazon, etc.)
            unite_mesure: 'm2', 'ml', ou 'unite'

        Returns:
            Quantité totale dans l'unité spécifiée
        """
        if unite_mesure == 'unite':
            return float(len(objets))

        total = 0.0
        for obj in objets:
            geometry = getattr(obj, 'geometry', None)
            if not geometry:
                continue

            try:
                if unite_mesure == 'm2':
                    if hasattr(obj, 'area_sqm') and obj.area_sqm:
                        total += obj.area_sqm
                    elif geometry.geom_type in ('Polygon', 'MultiPolygon'):
                        total += cls._calculate_area_m2(geometry)

                elif unite_mesure == 'ml':
                    if geometry.geom_type in ('LineString', 'MultiLineString'):
                        total += cls._calculate_length_m(geometry)
            except Exception as e:
                logger.error(f"Erreur calcul géométrie pour {type_objet}: {e}")
                continue

        return total

    @classmethod
    def _calculate_area_m2(cls, geometry) -> float:
        """Calcule l'aire en m² d'une géométrie polygonale."""
        import math
        area_deg = geometry.area
        centroid = geometry.centroid
        cos_lat = math.cos(math.radians(centroid.y))
        return area_deg * (111000 ** 2) * cos_lat

    @classmethod
    def _calculate_length_m(cls, geometry) -> float:
        """Calcule la longueur en mètres d'une géométrie linéaire."""
        import math
        length_deg = geometry.length
        centroid = geometry.centroid
        cos_lat = math.cos(math.radians(centroid.y))
        return length_deg * 111000 * cos_lat

    @classmethod
    def recalculate_and_save(cls, tache: Tache, force: bool = False) -> Tuple[Optional[float], bool]:
        """
        Calcule et sauvegarde la charge estimée pour une tâche.

        Args:
            tache: Instance de Tache
            force: Si True, recalcule même si charge_manuelle est activé

        Returns:
            Tuple (charge_calculee, success)
        """
        # Ne pas écraser une charge saisie manuellement (sauf si force=True)
        if tache.charge_manuelle and not force:
            logger.info(f"Tache {tache.id}: charge manuelle, calcul automatique ignoré")
            return tache.charge_estimee_heures, True

        try:
            # Calculer la charge totale
            charge = cls.calculate_workload(tache)
            tache.charge_estimee_heures = charge
            tache.save(update_fields=['charge_estimee_heures'])
            logger.info(f"Tache {tache.id}: charge estimée = {charge}h")

            return charge, True
        except Exception as e:
            logger.error(f"Erreur calcul charge tâche {tache.id}: {e}")
            return None, False

    @classmethod
    def reset_to_auto(cls, tache: Tache) -> Tuple[Optional[float], bool]:
        """
        Remet la tâche en mode calcul automatique et recalcule la charge.

        Returns:
            Tuple (charge_calculee, success)
        """
        tache.charge_manuelle = False
        tache.save(update_fields=['charge_manuelle'])
        return cls.recalculate_and_save(tache, force=True)
