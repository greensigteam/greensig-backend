import datetime
import logging
from typing import Dict, Optional, Tuple
from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY, MO, TU, WE, TH, FR, SA, SU
from django.db import transaction
from django.db.models import QuerySet
from .models import Tache, RatioProductivite, DistributionCharge
from api_users.models import HoraireTravail, JourFerie, Absence, StatutAbsence

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
    def _get_work_hours_for_day(equipe, date):
        """
        ✅ PHASE 2: Retourne les heures travaillables pour une équipe à une date donnée.

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
            horaire = HoraireTravail.objects.get(
                equipe=equipe,
                jour_semaine=jour_code,
                actif=True
            )
            return horaire.heures_travaillables
        except HoraireTravail.DoesNotExist:
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
        except HoraireTravail.MultipleObjectsReturned:
            # Plusieurs horaires actifs (ne devrait pas arriver avec validation)
            logger.error(
                f"Plusieurs horaires actifs pour équipe {equipe.id} le {jour_code}. "
                f"Utilisation du premier."
            )
            horaire = HoraireTravail.objects.filter(
                equipe=equipe,
                jour_semaine=jour_code,
                actif=True
            ).first()
            return horaire.heures_travaillables if horaire else 8.0

    @staticmethod
    def _est_weekend(date):
        """
        ✅ PHASE 3: Vérifie si une date tombe un weekend (dimanche uniquement).

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
        ✅ PHASE 3: Vérifie si une date est un jour férié.

        Args:
            date: datetime.date ou datetime.datetime

        Returns:
            bool: True si jour férié, False sinon
        """
        return JourFerie.est_jour_ferie(date, actif_uniquement=True)

    @staticmethod
    def _est_equipe_disponible(equipe, date):
        """
        ✅ PHASE 3: Vérifie si une équipe a suffisamment de membres disponibles pour une date.

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

        # Compter les membres actifs
        from api_users.models import StatutOperateur
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

    @staticmethod
    def _est_jour_travaillable(equipe, date, skip_weekends=True, skip_holidays=True, check_availability=True):
        """
        ✅ PHASE 3: Vérifie si un jour est travaillable pour une équipe.

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
        if skip_weekends and RecurrenceService._est_weekend(date):
            return False

        # Vérifier jour férié
        if skip_holidays and RecurrenceService._est_jour_ferie(date):
            return False

        # Vérifier disponibilité équipe
        if check_availability and not RecurrenceService._est_equipe_disponible(equipe, date):
            return False

        return True

    @staticmethod
    def calculate_recommended_occurrences(equipe, charge_totale_heures, date_debut, frequence='daily'):
        """
        ✅ PHASE 2: Calcule le nombre de jours recommandés pour une charge donnée.

        Args:
            equipe: Instance d'Equipe
            charge_totale_heures: Charge totale en heures
            date_debut: Date de début (datetime.date ou datetime.datetime)
            frequence: 'daily', 'weekly', ou 'monthly'

        Returns:
            int: Nombre d'occurrences recommandé
        """
        if not charge_totale_heures or charge_totale_heures <= 0:
            return 1

        if not equipe:
            # Pas d'équipe, utiliser défaut 8h/jour
            return max(1, int(round(charge_totale_heures / 8.0)))

        # Convertir en date si datetime
        if isinstance(date_debut, datetime.datetime):
            date_debut = date_debut.date()

        # Calculer les heures moyennes par occurrence selon la fréquence
        if frequence == 'daily':
            # Pour daily, calculer la moyenne sur 7 jours
            total_heures_semaine = 0
            for i in range(7):
                jour_test = date_debut + datetime.timedelta(days=i)
                heures = RecurrenceService._get_work_hours_for_day(equipe, jour_test)
                total_heures_semaine += heures
            heures_par_occurrence = total_heures_semaine / 7
        elif frequence == 'weekly':
            # Pour weekly, utiliser les heures du jour de la semaine de début
            heures_par_occurrence = RecurrenceService._get_work_hours_for_day(equipe, date_debut)
        elif frequence == 'monthly':
            # Pour monthly, utiliser les heures du jour de la semaine de début
            heures_par_occurrence = RecurrenceService._get_work_hours_for_day(equipe, date_debut)
        else:
            heures_par_occurrence = 8.0

        # Calculer le nombre d'occurrences nécessaires
        if heures_par_occurrence <= 0:
            return 1

        nombre_occurrences = int(round(charge_totale_heures / heures_par_occurrence))
        return max(1, nombre_occurrences)

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

        # ✅ PHASE 3: Filtrer les dates non-travaillables (weekends, jours fériés, équipe indisponible)
        # Récupérer l'équipe (support legacy id_equipe + nouveau equipes)
        equipe = tache_mere.id_equipe
        if not equipe and hasattr(tache_mere, 'equipes') and tache_mere.equipes.exists():
            equipe = tache_mere.equipes.first()

        dates_travaillables = []
        dates_skippees = []
        for dt in dates:
            if dt == start_dt:
                # Garder la date de la tâche mère
                dates_travaillables.append(dt)
                continue

            # Vérifier si jour travaillable
            if RecurrenceService._est_jour_travaillable(
                equipe=equipe,
                date=dt,
                skip_weekends=True,
                skip_holidays=True,
                check_availability=True
            ):
                dates_travaillables.append(dt)
            else:
                dates_skippees.append(dt)
                logger.debug(f"⏭️ Date skippée (non-travaillable): {dt.date()}")

        # Si on a skippé des dates et qu'on a un count, générer plus de dates pour compenser
        if dates_skippees and params['count']:
            count_original = int(params['count'])
            count_manquant = len(dates_skippees)
            logger.info(f"🔄 {count_manquant} dates skippées, génération de dates supplémentaires...")

            # Réajuster la règle pour générer plus de dates
            rule_kwargs_extended = rule_kwargs.copy()
            rule_kwargs_extended['count'] = count_original + count_manquant * 2  # *2 pour marge

            dates_extended = list(rrule(**rule_kwargs_extended))

            # Filtrer à nouveau
            for dt in dates_extended:
                if dt not in dates_travaillables and dt != start_dt:
                    if RecurrenceService._est_jour_travaillable(equipe, dt, True, True, True):
                        dates_travaillables.append(dt)
                        if len(dates_travaillables) >= count_original + 1:  # +1 pour la tâche mère
                            break

        dates = dates_travaillables
        logger.info(f"✅ {len(dates)} dates travaillables après filtrage (dont {len(dates_skippees)} skippées)")

        # ✅ PHASE 1.2: Calculate charge per occurrence (divide total by number of occurrences)
        charge_mere = tache_mere.charge_estimee_heures
        nombre_occurrences_total = len([d for d in dates if d != start_dt])  # Exclude mother task
        charge_par_occurrence = None

        if charge_mere and nombre_occurrences_total > 0:
            # Répartir la charge totale sur toutes les occurrences (mère incluse)
            charge_par_occurrence = charge_mere / (nombre_occurrences_total + 1)  # +1 for mother task

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
                charge_estimee_heures=charge_par_occurrence,  # ✅ Répartir la charge
            )
            occurrences_to_create.append(occurrence)

        # Bulk create pour la performance
        created_tasks = Tache.objects.bulk_create(occurrences_to_create)

        # Gestion des relations ManyToMany (Objets Inventaire + Équipes)
        # bulk_create ne gère pas les M2M, il faut les ajouter après
        if created_tasks:
            # Copier les objets
            if tache_mere.objets.exists():
                objets = list(tache_mere.objets.all())
                for task in created_tasks:
                    task.objets.set(objets)

            # ✅ FIX: Copier les équipes (M2M moderne)
            if tache_mere.equipes.exists():
                equipes = list(tache_mere.equipes.all())
                for task in created_tasks:
                    task.equipes.set(equipes)

        # ✅ PHASE 1.2: Update mother task with distributed charge
        if charge_par_occurrence is not None:
            tache_mere.charge_estimee_heures = charge_par_occurrence
            tache_mere.save(update_fields=['charge_estimee_heures'])

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
    def create_default_distributions(cls, tache: Tache, charge_totale: float) -> int:
        """
        ✅ NOUVEAU: Crée des distributions de charge par défaut pour une tâche multi-jours.

        Distribue la charge totale uniformément sur les jours travaillables dans la période de la tâche.

        Args:
            tache: Instance de Tache
            charge_totale: Charge totale en heures à distribuer

        Returns:
            int: Nombre de distributions créées
        """
        if not tache.date_debut_planifiee or not tache.date_fin_planifiee:
            logger.warning(f"Tache {tache.id}: dates manquantes, distributions non créées")
            return 0

        if charge_totale <= 0:
            logger.info(f"Tache {tache.id}: charge nulle, distributions non créées")
            return 0

        # Convertir en dates
        date_debut = tache.date_debut_planifiee.date()
        date_fin = tache.date_fin_planifiee.date()

        # Récupérer l'équipe pour vérifier jours travaillables
        equipe = tache.id_equipe
        if not equipe and hasattr(tache, 'equipes') and tache.equipes.exists():
            equipe = tache.equipes.first()

        # Lister tous les jours travaillables dans la période
        jours_travaillables = []
        current_date = date_debut

        while current_date <= date_fin:
            # Vérifier si jour travaillable
            if RecurrenceService._est_jour_travaillable(
                equipe=equipe,
                date=current_date,
                skip_weekends=True,
                skip_holidays=True,
                check_availability=False  # Pas de check disponibilité pour distribution par défaut
            ):
                heures_jour = RecurrenceService._get_work_hours_for_day(equipe, current_date)
                if heures_jour > 0:
                    jours_travaillables.append(current_date)

            current_date += datetime.timedelta(days=1)

        if not jours_travaillables:
            logger.warning(f"Tache {tache.id}: aucun jour travaillable trouvé dans la période")
            return 0

        # Distribuer uniformément la charge
        nombre_jours = len(jours_travaillables)
        heures_par_jour = charge_totale / nombre_jours

        # Supprimer anciennes distributions si elles existent
        tache.distributions_charge.all().delete()

        # Créer les distributions
        distributions_to_create = []
        for jour in jours_travaillables:
            distributions_to_create.append(
                DistributionCharge(
                    tache=tache,
                    date=jour,
                    heures_planifiees=round(heures_par_jour, 2),
                    commentaire="Distribution automatique basée sur objets GIS"
                )
            )

        # Bulk create
        DistributionCharge.objects.bulk_create(distributions_to_create)

        logger.info(
            f"✅ Tache {tache.id}: {len(distributions_to_create)} distributions créées "
            f"({heures_par_jour:.2f}h/jour × {nombre_jours} jours = {charge_totale}h total)"
        )

        return len(distributions_to_create)

    @classmethod
    def recalculate_and_save(cls, tache: Tache, force: bool = False) -> Tuple[Optional[float], bool]:
        """
        Calcule et sauvegarde la charge estimée pour une tâche.

        ✅ MODIFIÉ: Crée aussi des distributions de charge par défaut si la tâche a des objets GIS.

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

            # ✅ NOUVEAU: Créer distributions par défaut si objets GIS
            if charge and charge > 0 and tache.objets.exists():
                cls.create_default_distributions(tache, charge)

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
