import datetime
from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY, MO, TU, WE, TH, FR, SA, SU
from django.db import transaction
from .models import Tache

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
