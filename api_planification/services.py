import datetime
import logging
from typing import Dict, Optional, Tuple
from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY, MO, TU, WE, TH, FR, SA, SU
from django.db import transaction
from django.db.models import QuerySet
from .models import Tache, RatioProductivite

logger = logging.getLogger(__name__)

class RecurrenceService:
    """
    Service dédié à la gestion de la récurrence des tâches.
    Gère la génération, la mise à jour et la suppression des occurrences.
    """

    WEEKDAYS_MAP = {
        "MO": MO, "TU": TU, "WE": WE, "TH": TH, "FR": FR, "SA": SA, "SU": SU
    }

    FREQ_MAP = {
        "daily": DAILY,
        "weekly": WEEKLY,
        "monthly": MONTHLY
    }

    @staticmethod
    def _parse_params(tache):
        """Valide et extrait les paramètres de récurrence"""
        params = tache.parametres_recurrence
        if not params:
            return None
        
        freq_str = params.get('frequence')
        interval = params.get('interval', 1)
        jours = params.get('jours', []) # e.g. ["MO", "WE"]
        count = params.get('nombre_occurrences')
        until_date_str = params.get('date_fin')

        if freq_str not in RecurrenceService.FREQ_MAP:
            return None # Fréquence invalide ou absente

        freq = RecurrenceService.FREQ_MAP[freq_str]
        
        # Mapping des jours pour rrule (pour WEEKLY)
        byweekday = None
        if freq == WEEKLY and jours:
            byweekday = [RecurrenceService.WEEKDAYS_MAP[d] for d in jours if d in RecurrenceService.WEEKDAYS_MAP]

        return {
            'freq': freq,
            'interval': interval,
            'byweekday': byweekday,
            'count': count,
            'until_date_str': until_date_str
        }

    @staticmethod
    @transaction.atomic
    def generate_occurrences(tache_mere):
        """
        Génère les tâches filles basées sur la récurrence de la tâche mère.
        Supprime les anciennes occurrences futures non commencées avant de régénérer.
        """
        params = RecurrenceService._parse_params(tache_mere)
        if not params:
            return 0

        # Nettoyage des occurrences futures existantes (si mise à jour)
        # On ne supprime que celles qui sont "PLANIFIEE" pour ne pas perdre d'historique de réalisation
        Tache.objects.filter(
            id_recurrence_parent=tache_mere,
            date_debut_planifiee__gt=tache_mere.date_debut_planifiee,
            statut='PLANIFIEE'
        ).delete()

        # Configuration rrule
        start_dt = tache_mere.date_debut_planifiee
        duration = tache_mere.date_fin_planifiee - start_dt
        
        rule_kwargs = {
            'freq': params['freq'],
            'interval': params['interval'],
            'dtstart': start_dt,
            'byweekday': params['byweekday']
        }

        if params['until_date_str']:
            try:
                until_date = datetime.datetime.strptime(params['until_date_str'], "%Y-%m-%d").date()
                # On ajuste pour inclure toute la journée de fin
                rule_kwargs['until'] = datetime.datetime.combine(until_date, datetime.time.max).replace(tzinfo=start_dt.tzinfo)
            except ValueError:
                pass # Date invalide, on ignore ou on log
        elif params['count']:
            rule_kwargs['count'] = int(params['count'])
        else:
            # Sécurité : si ni date fin ni nombre occurences, on limite par défaut (ex: 1 an ou 50 occurences)
            rule_kwargs['count'] = 52 # Par exemple 1 an de weekly

        # Génération des dates
        dates = list(rrule(**rule_kwargs))
        
        # Création des instances
        occurrences_to_create = []
        
        # On ignore la première date si elle correspond exactement à la tâche mère
        # rrule inclut souvent le start_dt
        for dt in dates:
            if dt == start_dt:
                continue
                
            new_start = dt
            new_end = dt + duration
            
            # Création de l'objet (sans save pour le moment)
            occurrence = Tache(
                id_client=tache_mere.id_client,
                id_type_tache=tache_mere.id_type_tache,
                id_equipe=tache_mere.id_equipe,
                date_debut_planifiee=new_start,
                date_fin_planifiee=new_end,
                priorite=tache_mere.priorite,
                commentaires=tache_mere.commentaires,
                description_travaux=tache_mere.description_travaux,
                statut='PLANIFIEE', # Toujours planifiée au début
                id_recurrence_parent=tache_mere,
                parametres_recurrence=None, # Les filles ne portent pas la règle de récurrence pour éviter la récursion
            )
            occurrences_to_create.append(occurrence)

        # Bulk create pour la performance
        created_tasks = Tache.objects.bulk_create(occurrences_to_create)
        
        # Gestion des relations ManyToMany (Objets Inventaire)
        # bulk_create ne gère pas les M2M, il faut les ajouter après
        if created_tasks and tache_mere.objets.exists():
            objets = list(tache_mere.objets.all())
            for task in created_tasks:
                task.objets.set(objets)

        return len(created_tasks)


class WorkloadCalculationService:
    """
    Service pour calculer la charge de travail estimée d'une tâche
    basée sur les objets liés et les ratios de productivité.
    """

    # Classification des types d'objets par type de géométrie
    POINT_OBJECTS = ['Arbre', 'Palmier', 'Puit', 'Pompe', 'Vanne', 'Clapet', 'Ballon']
    POLYGON_OBJECTS = ['Gazon', 'Arbuste', 'Vivace', 'Cactus', 'Graminee']
    LINE_OBJECTS = ['Canalisation', 'Aspersion', 'Goutte']

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
        """
        grouped = {}
        for obj in objets:
            type_name = obj.get_nom_type()
            if type_name not in grouped:
                grouped[type_name] = []
            grouped[type_name].append(obj)
        return grouped

    @classmethod
    def _calculate_quantity(cls, objets: list, type_objet: str, unite_mesure: str) -> float:
        """
        Calcule la quantité totale pour un groupe d'objets.

        Args:
            objets: Liste d'objets du même type
            type_objet: Nom du type (Arbre, Gazon, etc.)
            unite_mesure: 'm2', 'ml', ou 'unite'

        Returns:
            Quantité totale dans l'unité spécifiée
        """
        if unite_mesure == 'unite':
            return float(len(objets))

        total = 0.0
        for obj in objets:
            real_obj = obj.get_type_reel()
            if not real_obj:
                continue

            geometry = getattr(real_obj, 'geometry', None)
            if not geometry:
                continue

            try:
                if unite_mesure == 'm2':
                    # Pour polygones: utiliser area_sqm si disponible, sinon calculer
                    if hasattr(real_obj, 'area_sqm') and real_obj.area_sqm:
                        total += real_obj.area_sqm
                    elif geometry.geom_type in ('Polygon', 'MultiPolygon'):
                        total += cls._calculate_area_m2(geometry)

                elif unite_mesure == 'ml':
                    # Pour lignes: calculer la longueur
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
