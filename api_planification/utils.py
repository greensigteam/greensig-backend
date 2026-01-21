"""
Utilitaires pour la planification
"""
from datetime import timedelta, date, datetime
from typing import Dict, List, Optional, Tuple
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Tache, DistributionCharge


def calculer_duree_tache(tache: Tache) -> int:
    """
    Calcule la durée d'une tâche en jours.

    Args:
        tache: Instance de la tâche

    Returns:
        Nombre de jours entre date_debut et date_fin (inclus)
    """
    delta = tache.date_fin_planifiee - tache.date_debut_planifiee
    return delta.days + 1  # +1 car on compte les deux jours inclus


def valider_frequence_compatible(
    tache: Tache,
    decalage_jours: int,
    raise_exception: bool = True
) -> Tuple[bool, Optional[str]]:
    """
    Valide que la fréquence de récurrence est compatible avec la durée de la tâche.

    Règles de validation :
    - Le décalage doit être supérieur ou égal à la durée de la tâche
    - Sinon, les occurrences se chevaucheraient

    Args:
        tache: Tâche source à dupliquer
        decalage_jours: Décalage en jours entre chaque occurrence
        raise_exception: Si True, lève une exception en cas d'erreur

    Returns:
        Tuple (est_valide, message_erreur)

    Raises:
        ValidationError: Si raise_exception=True et la validation échoue

    Exemples:
        >>> tache.date_debut = date(2026, 1, 1)
        >>> tache.date_fin = date(2026, 1, 5)  # 5 jours
        >>> valider_frequence_compatible(tache, decalage_jours=3)
        # Erreur : décalage trop court (3j) pour une tâche de 5j

        >>> valider_frequence_compatible(tache, decalage_jours=7)
        # OK : décalage suffisant
    """
    duree_tache = calculer_duree_tache(tache)

    # Validation : le décalage doit être >= durée de la tâche
    if decalage_jours < duree_tache:
        message = (
            f"Impossible de créer une récurrence avec un décalage de {decalage_jours} jour(s). "
            f"La tâche dure {duree_tache} jour(s) (du {tache.date_debut_planifiee.strftime('%d/%m/%Y')} "
            f"au {tache.date_fin_planifiee.strftime('%d/%m/%Y')}). "
            f"Le décalage minimum requis est de {duree_tache} jour(s) pour éviter le chevauchement des occurrences. "
            f"\n\nSuggestions :\n"
            f"  • Utilisez un décalage d'au moins {duree_tache} jours\n"
        )

        # Ajouter des suggestions de fréquence
        if duree_tache <= 1:
            message += "  • Fréquences compatibles : DAILY, WEEKLY, MONTHLY, YEARLY"
        elif duree_tache <= 7:
            message += "  • Fréquences compatibles : WEEKLY, MONTHLY, YEARLY"
        elif duree_tache <= 30:
            message += "  • Fréquences compatibles : MONTHLY, YEARLY"
        else:
            message += "  • Fréquence compatible : YEARLY uniquement"

        if raise_exception:
            raise ValidationError(message)

        return False, message

    return True, None


def obtenir_frequences_compatibles(tache: Tache) -> List[str]:
    """
    Retourne la liste des fréquences compatibles avec la durée de la tâche.

    Args:
        tache: Tâche à analyser

    Returns:
        Liste des fréquences compatibles (DAILY, WEEKLY, MONTHLY, YEARLY)

    Exemples:
        >>> tache.duree = 1 jour
        >>> obtenir_frequences_compatibles(tache)
        ['DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY']

        >>> tache.duree = 10 jours
        >>> obtenir_frequences_compatibles(tache)
        ['MONTHLY', 'YEARLY']
    """
    duree_tache = calculer_duree_tache(tache)
    frequences_disponibles = []

    # Mapping fréquence -> décalage en jours
    frequences_mapping = {
        'DAILY': 1,
        'WEEKLY': 7,
        'MONTHLY': 30,
        'YEARLY': 365,
    }

    for frequence, decalage in frequences_mapping.items():
        if decalage >= duree_tache:
            frequences_disponibles.append(frequence)

    return frequences_disponibles


def calculer_nouvelle_date(date_originale: date, decalage_jours: int) -> date:
    """
    Calcule une nouvelle date en ajoutant un décalage en jours.

    Args:
        date_originale: Date de départ
        decalage_jours: Nombre de jours à ajouter

    Returns:
        Nouvelle date calculée
    """
    return date_originale + timedelta(days=decalage_jours)


def dupliquer_tache_avec_distributions(
    tache_id: int,
    decalage_jours: int,
    nombre_occurrences: Optional[int] = None,
    date_fin_recurrence: Optional[date] = None,
    conserver_equipes: bool = True,
    conserver_objets: bool = True,
    nouveau_statut: Optional[str] = 'PLANIFIEE',
    skip_validation: bool = False
) -> List[Tache]:
    """
    Duplique une tâche et ses distributions de charge avec un décalage temporel.

    Cette fonction crée de nouvelles tâches indépendantes basées sur une tâche source.
    Chaque nouvelle tâche possède :
    - Toutes les caractéristiques de la tâche source
    - Ses propres distributions de charge (copiées et décalées dans le temps)
    - Une référence unique
    - Un statut réinitialisé (par défaut : PLANIFIEE)

    Args:
        tache_id: ID de la tâche source à dupliquer
        decalage_jours: Décalage en jours entre chaque occurrence
        nombre_occurrences: Nombre max de tâches à créer (optionnel, max: 100)
        date_fin_recurrence: Date limite pour créer des occurrences (optionnel)
        conserver_equipes: Conserver les équipes assignées (défaut: True)
        conserver_objets: Conserver les objets liés (défaut: True)
        nouveau_statut: Statut des nouvelles tâches (défaut: 'PLANIFIEE')
        skip_validation: Désactiver la validation de compatibilité (défaut: False)
                        Utilisé quand la validation a déjà été faite en amont

    Returns:
        Liste des nouvelles tâches créées

    Raises:
        Tache.DoesNotExist: Si la tâche source n'existe pas
        ValueError: Si les paramètres sont invalides

    Règles de génération:
        - Si nombre_occurrences ET date_fin_recurrence: utilise le plus restrictif
        - Si seulement nombre_occurrences: crée exactement N tâches
        - Si seulement date_fin_recurrence: crée jusqu'à cette date (max 100)
        - Si aucun des deux: crée jusqu'au 31/12 de l'année en cours (max 100)

    Exemples:
        # Créer des tâches jusqu'au 31/12/2026
        >>> nouvelles_taches = dupliquer_tache_avec_distributions(
        ...     tache_id=123,
        ...     decalage_jours=7,
        ...     date_fin_recurrence=date(2026, 12, 31)
        ... )

        # Créer 4 occurrences hebdomadaires
        >>> nouvelles_taches = dupliquer_tache_avec_distributions(
        ...     tache_id=123,
        ...     decalage_jours=7,
        ...     nombre_occurrences=4
        ... )

        # Créer jusqu'à fin d'année (par défaut)
        >>> nouvelles_taches = dupliquer_tache_avec_distributions(
        ...     tache_id=123,
        ...     decalage_jours=30
        ... )
    """

    # Validation des paramètres
    if decalage_jours < 1:
        raise ValueError("Le décalage doit être au moins 1 jour")

    if nombre_occurrences is not None and nombre_occurrences < 1:
        raise ValueError("Le nombre d'occurrences doit être au moins 1")

    if nombre_occurrences is not None and nombre_occurrences > 100:
        raise ValueError("Maximum 100 occurrences autorisées")

    # Récupérer la tâche source avec les relations
    try:
        tache_source = Tache.objects.select_related(
            'id_type_tache',
            'id_structure_client',
            'id_client',
            'id_equipe'
        ).prefetch_related(
            'equipes',
            'objets',
            'distributions_charge'
        ).get(id=tache_id, deleted_at__isnull=True)

        print(f"[RECURRENCE] Tâche source #{tache_id} chargée")
        print(f"[RECURRENCE] Date début: {tache_source.date_debut_planifiee}")
        print(f"[RECURRENCE] Date fin: {tache_source.date_fin_planifiee}")
        print(f"[RECURRENCE] Nombre de distributions: {tache_source.distributions_charge.count()}")

    except Tache.DoesNotExist:
        raise Tache.DoesNotExist(f"Tâche {tache_id} introuvable")

    # ✅ VALIDATION : Vérifier la compatibilité de la fréquence (sauf si skip_validation=True)
    duree_tache = calculer_duree_tache(tache_source)
    print(f"[RECURRENCE] Durée tâche: {duree_tache} jours, Décalage: {decalage_jours} jours")

    if not skip_validation:
        valider_frequence_compatible(tache_source, decalage_jours, raise_exception=True)
        print(f"[RECURRENCE] Validation de compatibilité OK")
    else:
        print(f"[RECURRENCE] Validation de compatibilité SKIP (déjà validée en amont)")

    # Déterminer le nombre d'occurrences à créer
    if date_fin_recurrence is None and nombre_occurrences is None:
        # Par défaut : jusqu'au 31/12 de l'année en cours
        from datetime import datetime
        annee_courante = datetime.now().year
        date_fin_recurrence = date(annee_courante, 12, 31)

    # Calculer le nombre d'occurrences basé sur la date de fin
    if date_fin_recurrence is not None:
        # Calculer combien d'occurrences peuvent tenir jusqu'à la date de fin
        date_debut_source = tache_source.date_debut_planifiee
        occurrences_calculees = 0
        occurrence = 1

        while True:
            decalage_total = decalage_jours * occurrence
            nouvelle_date_debut = calculer_nouvelle_date(date_debut_source, decalage_total)

            if nouvelle_date_debut > date_fin_recurrence:
                break

            occurrences_calculees += 1
            occurrence += 1

            # Sécurité : limiter à 100 occurrences
            if occurrences_calculees >= 100:
                break

        # Si nombre_occurrences est aussi fourni, prendre le minimum
        if nombre_occurrences is not None:
            nombre_occurrences_final = min(nombre_occurrences, occurrences_calculees)
        else:
            nombre_occurrences_final = occurrences_calculees
    else:
        # Seulement nombre_occurrences fourni
        nombre_occurrences_final = nombre_occurrences

    # Validation finale
    if nombre_occurrences_final < 1:
        if date_fin_recurrence:
            raise ValueError(
                f"Impossible de créer des occurrences avant le {date_fin_recurrence.strftime('%d/%m/%Y')}. "
                f"La première occurrence serait le {calculer_nouvelle_date(tache_source.date_debut_planifiee, decalage_jours).strftime('%d/%m/%Y')}."
            )
        else:
            raise ValueError("Aucune occurrence à créer")

    print(f"[RECURRENCE] Nombre d'occurrences à créer: {nombre_occurrences_final}")

    nouvelles_taches = []

    # Transaction atomique pour garantir la cohérence
    with transaction.atomic():
        print(f"[RECURRENCE] Début de la transaction atomique")
        for occurrence in range(1, nombre_occurrences_final + 1):
            print(f"[RECURRENCE] === Création occurrence #{occurrence} ===")
            # Calculer le décalage total pour cette occurrence
            decalage_total = decalage_jours * occurrence
            print(f"[RECURRENCE] Décalage total: {decalage_total} jours")

            # Créer la nouvelle tâche (copie)
            nouvelle_tache = Tache(
                # Relations
                id_structure_client=tache_source.id_structure_client,
                id_client=tache_source.id_client,
                id_type_tache=tache_source.id_type_tache,
                id_equipe=tache_source.id_equipe if conserver_equipes else None,
                reclamation=None,  # Ne pas dupliquer le lien réclamation

                # Dates (décalées)
                date_debut_planifiee=calculer_nouvelle_date(
                    tache_source.date_debut_planifiee,
                    decalage_total
                ),
                date_fin_planifiee=calculer_nouvelle_date(
                    tache_source.date_fin_planifiee,
                    decalage_total
                ),
                date_echeance=calculer_nouvelle_date(
                    tache_source.date_echeance,
                    decalage_total
                ) if tache_source.date_echeance else None,

                # Données métier
                priorite=tache_source.priorite,
                commentaires=tache_source.commentaires,
                charge_estimee_heures=tache_source.charge_estimee_heures,
                charge_manuelle=tache_source.charge_manuelle,
                description_travaux=tache_source.description_travaux,

                # Statut réinitialisé
                statut=nouveau_statut,
                etat_validation='EN_ATTENTE',
                note_qualite=None,

                # Dates réelles vides (nouvelle tâche)
                date_affectation=None,
                date_debut_reelle=None,
                date_fin_reelle=None,
                duree_reelle_minutes=None,
                date_validation=None,
                validee_par=None,
                commentaire_validation='',

                # Notifications
                notifiee=False,
                confirmee=False,

                # Référence sera générée automatiquement par save()
                reference=None
            )

            # Sauvegarder pour obtenir un ID
            nouvelle_tache.save()
            print(f"[RECURRENCE] Nouvelle tâche #{nouvelle_tache.id} créée (occurrence #{occurrence})")
            print(f"[RECURRENCE] Dates: {nouvelle_tache.date_debut_planifiee} -> {nouvelle_tache.date_fin_planifiee}")

            # Copier les relations ManyToMany
            if conserver_equipes:
                nouvelle_tache.equipes.set(tache_source.equipes.all())
                print(f"[RECURRENCE] {tache_source.equipes.count()} équipe(s) copiée(s)")

            if conserver_objets:
                nouvelle_tache.objets.set(tache_source.objets.all())
                print(f"[RECURRENCE] {tache_source.objets.count()} objet(s) copié(s)")

            # Dupliquer les distributions de charge
            distributions_source = tache_source.distributions_charge.all()
            print(f"[RECURRENCE] Duplication de {distributions_source.count()} distribution(s)")

            for idx, dist_source in enumerate(distributions_source, 1):
                nouvelle_distribution = DistributionCharge(
                    tache=nouvelle_tache,
                    date=calculer_nouvelle_date(dist_source.date, decalage_total),
                    heures_planifiees=dist_source.heures_planifiees,
                    heures_reelles=None,  # Réinitialiser les heures réelles
                    commentaire=dist_source.commentaire,
                    heure_debut=dist_source.heure_debut,
                    heure_fin=dist_source.heure_fin,
                    status='NON_REALISEE',  # Réinitialiser le statut
                    reference=None  # Sera généré automatiquement
                )
                nouvelle_distribution.save()
                print(f"[RECURRENCE]   Distribution #{idx} créée: date={nouvelle_distribution.date}, "
                      f"heures={dist_source.heure_debut}-{dist_source.heure_fin}")

            nouvelles_taches.append(nouvelle_tache)

        print(f"[RECURRENCE] Transaction terminée. {len(nouvelles_taches)} tâche(s) créée(s)")

    return nouvelles_taches


def dupliquer_tache_recurrence_multiple(
    tache_id: int,
    frequence: str,
    nombre_occurrences: Optional[int] = None,
    date_fin_recurrence: Optional[date] = None,
    **kwargs
) -> List[Tache]:
    """
    Duplique une tâche selon une fréquence prédéfinie.

    Args:
        tache_id: ID de la tâche à dupliquer
        frequence: 'DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY'
        nombre_occurrences: Nombre max d'occurrences (optionnel)
        date_fin_recurrence: Date limite pour créer des occurrences (optionnel)
        **kwargs: Arguments additionnels pour dupliquer_tache_avec_distributions

    Returns:
        Liste des nouvelles tâches créées

    Règles:
        - Si aucun paramètre: jusqu'au 31/12 de l'année en cours
        - Si nombre_occurrences: crée exactement N tâches
        - Si date_fin_recurrence: crée jusqu'à cette date
        - Si les deux: prend le plus restrictif

    Exemples:
        # Créer des tâches hebdomadaires jusqu'au 31/12/2026
        >>> taches = dupliquer_tache_recurrence_multiple(
        ...     tache_id=123,
        ...     frequence='WEEKLY',
        ...     date_fin_recurrence=date(2026, 12, 31)
        ... )

        # Créer 12 tâches mensuelles
        >>> taches = dupliquer_tache_recurrence_multiple(
        ...     tache_id=123,
        ...     frequence='MONTHLY',
        ...     nombre_occurrences=12
        ... )

        # Par défaut: jusqu'à fin d'année
        >>> taches = dupliquer_tache_recurrence_multiple(
        ...     tache_id=123,
        ...     frequence='WEEKLY'
        ... )
    """

    # Mapping fréquence -> décalage en jours
    frequences = {
        'DAILY': 1,
        'WEEKLY': 7,
        'MONTHLY': 30,  # Approximation
        'YEARLY': 365,
    }

    if frequence not in frequences:
        raise ValueError(
            f"Fréquence invalide. Valeurs acceptées : {list(frequences.keys())}"
        )

    decalage_jours = frequences[frequence]

    # ✅ Vérifier la compatibilité de la fréquence AVANT de créer les tâches
    # Récupérer la tâche pour validation
    try:
        tache_source = Tache.objects.get(id=tache_id, deleted_at__isnull=True)
    except Tache.DoesNotExist:
        raise Tache.DoesNotExist(f"Tâche {tache_id} introuvable")

    # Obtenir les fréquences compatibles
    frequences_compatibles = obtenir_frequences_compatibles(tache_source)

    if frequence not in frequences_compatibles:
        duree_tache = calculer_duree_tache(tache_source)
        raise ValidationError(
            f"La fréquence '{frequence}' n'est pas compatible avec cette tâche. "
            f"\n\nLa tâche dure {duree_tache} jour(s) "
            f"(du {tache_source.date_debut_planifiee.strftime('%d/%m/%Y')} "
            f"au {tache_source.date_fin_planifiee.strftime('%d/%m/%Y')}). "
            f"\n\nFréquences compatibles pour cette tâche : {', '.join(frequences_compatibles)}"
            f"\n\nExplication : "
            f"Le décalage de la fréquence '{frequence}' ({decalage_jours} jour(s)) "
            f"est inférieur à la durée de la tâche ({duree_tache} jour(s)), "
            f"ce qui provoquerait un chevauchement des occurrences."
        )

    # Tout est OK, on peut dupliquer
    return dupliquer_tache_avec_distributions(
        tache_id=tache_id,
        decalage_jours=decalage_jours,
        nombre_occurrences=nombre_occurrences,
        date_fin_recurrence=date_fin_recurrence,
        **kwargs
    )


def dupliquer_tache_dates_specifiques(
    tache_id: int,
    dates_cibles: List[date],
    **kwargs
) -> List[Tache]:
    """
    Duplique une tâche pour des dates spécifiques.

    Calcule automatiquement le décalage pour chaque date cible par rapport
    à la date de début de la tâche source.

    Args:
        tache_id: ID de la tâche à dupliquer
        dates_cibles: Liste des dates de début pour les nouvelles tâches
        **kwargs: Arguments additionnels pour la duplication

    Returns:
        Liste des nouvelles tâches créées

    Exemple:
        >>> from datetime import date
        >>> dates = [date(2026, 2, 15), date(2026, 3, 15), date(2026, 4, 15)]
        >>> taches = dupliquer_tache_dates_specifiques(
        ...     tache_id=123,
        ...     dates_cibles=dates
        ... )
    """

    if not dates_cibles:
        raise ValueError("Au moins une date cible est requise")

    if len(dates_cibles) > 100:
        raise ValueError("Maximum 100 dates cibles autorisées")

    # Récupérer la tâche source pour connaître sa date de début
    try:
        tache_source = Tache.objects.get(id=tache_id, deleted_at__isnull=True)
    except Tache.DoesNotExist:
        raise Tache.DoesNotExist(f"Tâche {tache_id} introuvable")

    date_debut_source = tache_source.date_debut_planifiee
    nouvelles_taches = []

    with transaction.atomic():
        for date_cible in sorted(dates_cibles):
            # Calculer le décalage en jours
            decalage = (date_cible - date_debut_source).days

            if decalage < 1:
                raise ValueError(
                    f"Date cible {date_cible} doit être postérieure à {date_debut_source}"
                )

            # Créer une seule occurrence avec ce décalage
            taches_creees = dupliquer_tache_avec_distributions(
                tache_id=tache_id,
                decalage_jours=decalage,
                nombre_occurrences=1,
                **kwargs
            )

            nouvelles_taches.extend(taches_creees)

    return nouvelles_taches


# ==============================================================================
# FONCTIONS POUR LA SÉLECTION DE JOURS DU MOIS (MONTHLY)
# ==============================================================================

def calculer_intervalle_minimum_jours_mois(jours_mois: List[int]) -> int:
    """
    Calcule l'intervalle minimum (en jours) entre deux jours consécutifs du mois sélectionnés.

    Args:
        jours_mois: Liste triée des jours du mois (1-31)

    Returns:
        int: Nombre de jours minimum entre deux occurrences

    Exemples:
        >>> calculer_intervalle_minimum_jours_mois([1, 15])
        14  # 1er et 15 du mois : intervalle minimum = 14 jours

        >>> calculer_intervalle_minimum_jours_mois([5, 10, 20])
        5  # 5-10-20 : intervalle minimum = 5 jours

        >>> calculer_intervalle_minimum_jours_mois([28, 1])
        3  # 28 → 1er du mois suivant (approximation 28 jours) = 3 jours

        >>> calculer_intervalle_minimum_jours_mois([15])
        28  # Un seul jour = intervalle minimum de 28 jours (mois le plus court)
    """
    if not jours_mois or len(jours_mois) == 0:
        return 30  # Par défaut, mensuel

    if len(jours_mois) == 1:
        return 28  # Un seul jour = répétition mensuelle (28 jours minimum)

    jours_tries = sorted(jours_mois)
    intervalles = []

    # Calculer les intervalles entre jours consécutifs du même mois
    for i in range(len(jours_tries) - 1):
        intervalle = jours_tries[i + 1] - jours_tries[i]
        intervalles.append(intervalle)

    # Calculer l'intervalle de retour (dernier jour du mois → premier jour du mois suivant)
    # Approximation : mois le plus court = 28 jours (février non bissextile)
    intervalle_retour = 28 - jours_tries[-1] + jours_tries[0]
    intervalles.append(intervalle_retour)

    return min(intervalles)


def generer_dates_jours_mois(
    date_debut: date,
    jours_mois: List[int],
    nombre_occurrences: Optional[int] = None,
    date_fin_recurrence: Optional[date] = None
) -> List[date]:
    """
    Génère une liste de dates selon les jours du mois sélectionnés.

    Args:
        date_debut: Date de début (première occurrence)
        jours_mois: Liste des jours du mois (1-31)
        nombre_occurrences: Nombre max d'occurrences (optionnel)
        date_fin_recurrence: Date limite (optionnel)

    Returns:
        List[date]: Liste des dates d'occurrences

    Exemples:
        >>> date_debut = date(2026, 1, 15)  # 15 janvier
        >>> jours_mois = [1, 15]  # 1er et 15 de chaque mois
        >>> generer_dates_jours_mois(date_debut, jours_mois, nombre_occurrences=5)
        [
            date(2026, 2, 1),   # 1er février
            date(2026, 2, 15),  # 15 février
            date(2026, 3, 1),   # 1er mars
            date(2026, 3, 15),  # 15 mars
            date(2026, 4, 1)    # 1er avril
        ]

    Note:
        - Si un jour n'existe pas dans un mois (ex: 31 février), il est ignoré
        - Les dates sont générées chronologiquement
    """
    if not jours_mois:
        raise ValueError("jours_mois ne peut pas être vide")

    jours_tries = sorted(jours_mois)
    dates = []

    # Déterminer la date limite
    if date_fin_recurrence:
        date_limite = date_fin_recurrence
    else:
        # Par défaut: jusqu'au 31/12 de l'année en cours
        date_limite = date(date_debut.year, 12, 31)

    # Déterminer le nombre max d'occurrences
    max_occurrences = nombre_occurrences if nombre_occurrences else 100

    # Commencer à partir du lendemain de la date de début
    # (la tâche source existe déjà)
    date_courante = date_debut + timedelta(days=1)

    while len(dates) < max_occurrences:
        # Vérifier si on dépasse la date limite
        if date_courante > date_limite:
            break

        # Jour du mois (1-31)
        jour_mois = date_courante.day

        # Si ce jour est dans la sélection, ajouter à la liste
        if jour_mois in jours_tries:
            dates.append(date_courante)

        # Passer au jour suivant
        date_courante += timedelta(days=1)

    return dates


def dupliquer_tache_recurrence_jours_mois(
    tache_id: int,
    jours_mois: List[int],
    nombre_occurrences: Optional[int] = None,
    date_fin_recurrence: Optional[date] = None,
    conserver_equipes: bool = True,
    conserver_objets: bool = True,
    nouveau_statut: str = 'PLANIFIEE'
) -> List[Tache]:
    """
    Duplique une tâche selon les jours du mois sélectionnés.

    Args:
        tache_id: ID de la tâche source
        jours_mois: Liste des jours du mois (1-31)
        nombre_occurrences: Nombre max d'occurrences (optionnel)
        date_fin_recurrence: Date limite (optionnel)
        conserver_equipes: Conserver les équipes assignées
        conserver_objets: Conserver les objets liés
        nouveau_statut: Statut des nouvelles tâches

    Returns:
        List[Tache]: Liste des nouvelles tâches créées

    Raises:
        ValidationError: Si intervalle < durée tâche (chevauchement)

    Exemples:
        >>> # Tâche source : 15/01/2026 (1 jour)
        >>> # Créer des occurrences 1er et 15 de chaque mois
        >>> dupliquer_tache_recurrence_jours_mois(
        ...     tache_id=123,
        ...     jours_mois=[1, 15],
        ...     nombre_occurrences=10
        ... )
        # Résultat : 10 tâches aux dates : 1er fév, 15 fév, 1er mars, ...
    """
    # Récupérer la tâche source
    try:
        tache_source = Tache.objects.get(id=tache_id, deleted_at__isnull=True)
    except Tache.DoesNotExist:
        raise ValidationError(f"Tâche #{tache_id} introuvable")

    # Calculer la durée de la tâche
    duree_tache = calculer_duree_tache(tache_source)

    # Calculer l'intervalle minimum entre les jours sélectionnés
    intervalle_min = calculer_intervalle_minimum_jours_mois(jours_mois)

    # ⚠️ VALIDATION CRITIQUE: intervalle >= durée tâche
    if intervalle_min < duree_tache:
        jours_selectionnes_str = ', '.join([str(j) for j in sorted(jours_mois)])

        raise ValidationError(
            f"Impossible de créer une récurrence avec les jours du mois sélectionnés.\n\n"
            f"La tâche dure {duree_tache} jour(s) "
            f"(du {tache_source.date_debut_planifiee.strftime('%d/%m/%Y')} "
            f"au {tache_source.date_fin_planifiee.strftime('%d/%m/%Y')}).\n\n"
            f"Jours du mois sélectionnés : {jours_selectionnes_str}\n"
            f"Intervalle minimum : {intervalle_min} jour(s)\n\n"
            f"❌ L'intervalle minimum ({intervalle_min} jour(s)) est inférieur à la durée "
            f"de la tâche ({duree_tache} jour(s)), ce qui provoquerait un chevauchement.\n\n"
            f"💡 Suggestions :\n"
            f"  • Sélectionnez des jours plus espacés (minimum {duree_tache} jours d'intervalle)\n"
            f"  • Réduisez la durée de la tâche\n"
            f"  • Utilisez un décalage personnalisé au lieu de jours spécifiques"
        )

    # Générer les dates selon les jours du mois sélectionnés
    dates_occurrences = generer_dates_jours_mois(
        date_debut=tache_source.date_debut_planifiee,
        jours_mois=jours_mois,
        nombre_occurrences=nombre_occurrences,
        date_fin_recurrence=date_fin_recurrence
    )

    if len(dates_occurrences) == 0:
        raise ValidationError(
            "Aucune occurrence ne peut être créée avec les paramètres fournis. "
            "Vérifiez la date de fin de récurrence."
        )

    # Créer les tâches avec transaction atomique
    nouvelles_taches = []

    with transaction.atomic():
        for date_occurrence in dates_occurrences:
            # Calculer le décalage (en jours) par rapport à la tâche source
            decalage = (date_occurrence - tache_source.date_debut_planifiee).days

            # Dupliquer la tâche avec ce décalage (réutilise la fonction existante)
            # ✅ skip_validation=True car l'intervalle minimum a déjà été validé en amont
            taches_creees = dupliquer_tache_avec_distributions(
                tache_id=tache_id,
                decalage_jours=decalage,
                nombre_occurrences=1,
                date_fin_recurrence=None,
                conserver_equipes=conserver_equipes,
                conserver_objets=conserver_objets,
                nouveau_statut=nouveau_statut,
                skip_validation=True  # ✅ Skip validation car déjà faite
            )

            nouvelles_taches.extend(taches_creees)

    return nouvelles_taches


# ==============================================================================
# FONCTIONS POUR LA SÉLECTION DE JOURS DE LA SEMAINE (DAILY/WEEKLY)
# ==============================================================================

def calculer_intervalle_minimum_jours_semaine(jours_semaine: List[int]) -> int:
    """
    Calcule l'intervalle minimum (en jours) entre deux jours consécutifs sélectionnés.

    Args:
        jours_semaine: Liste triée des jours (0=Lundi, 6=Dimanche)

    Returns:
        int: Nombre de jours minimum entre deux occurrences

    Exemples:
        >>> calculer_intervalle_minimum_jours_semaine([0, 2, 4])
        2  # Lun-Mer-Ven : intervalle minimum = 2 jours

        >>> calculer_intervalle_minimum_jours_semaine([0, 1])
        1  # Lun-Mar : intervalle minimum = 1 jour

        >>> calculer_intervalle_minimum_jours_semaine([0, 6])
        1  # Lun-Dim : intervalle minimum = 1 jour (Dim → Lun)

        >>> calculer_intervalle_minimum_jours_semaine([1])
        7  # Mar seulement : intervalle minimum = 7 jours
    """
    if not jours_semaine or len(jours_semaine) == 0:
        return 7  # Par défaut, hebdomadaire

    if len(jours_semaine) == 1:
        return 7  # Un seul jour = répétition hebdomadaire

    jours_tries = sorted(jours_semaine)
    intervalles = []

    # Calculer les intervalles entre jours consécutifs
    for i in range(len(jours_tries) - 1):
        intervalle = jours_tries[i + 1] - jours_tries[i]
        intervalles.append(intervalle)

    # Calculer l'intervalle de retour (dernier jour → premier jour de la semaine suivante)
    intervalle_retour = 7 - jours_tries[-1] + jours_tries[0]
    intervalles.append(intervalle_retour)

    return min(intervalles)


def generer_dates_jours_semaine(
    date_debut: date,
    jours_semaine: List[int],
    nombre_occurrences: Optional[int] = None,
    date_fin_recurrence: Optional[date] = None
) -> List[date]:
    """
    Génère une liste de dates selon les jours de la semaine sélectionnés.

    Args:
        date_debut: Date de début (première occurrence)
        jours_semaine: Liste des jours (0=Lundi, 6=Dimanche)
        nombre_occurrences: Nombre max d'occurrences (optionnel)
        date_fin_recurrence: Date limite (optionnel)

    Returns:
        List[date]: Liste des dates d'occurrences

    Exemples:
        >>> date_debut = date(2026, 1, 13)  # Mardi
        >>> jours_semaine = [0, 2, 4]  # Lun, Mer, Ven
        >>> generer_dates_jours_semaine(date_debut, jours_semaine, nombre_occurrences=5)
        [
            date(2026, 1, 15),  # Mer
            date(2026, 1, 17),  # Ven
            date(2026, 1, 20),  # Lun
            date(2026, 1, 22),  # Mer
            date(2026, 1, 24)   # Ven
        ]
    """
    if not jours_semaine:
        raise ValueError("jours_semaine ne peut pas être vide")

    jours_tries = sorted(jours_semaine)
    dates = []

    # Déterminer la date limite
    if date_fin_recurrence:
        date_limite = date_fin_recurrence
    else:
        # Par défaut: jusqu'au 31/12 de l'année en cours
        date_limite = date(date_debut.year, 12, 31)

    # Déterminer le nombre max d'occurrences
    max_occurrences = nombre_occurrences if nombre_occurrences else 100

    # Commencer à partir du lendemain de la date de début
    # (la tâche source existe déjà)
    date_courante = date_debut + timedelta(days=1)

    while len(dates) < max_occurrences:
        # Vérifier si on dépasse la date limite
        if date_courante > date_limite:
            break

        # Jour de la semaine (0=Lundi, 6=Dimanche)
        jour_semaine = date_courante.weekday()

        # Si ce jour est dans la sélection, ajouter à la liste
        if jour_semaine in jours_tries:
            dates.append(date_courante)

        # Passer au jour suivant
        date_courante += timedelta(days=1)

    return dates


def dupliquer_tache_recurrence_jours_semaine(
    tache_id: int,
    jours_semaine: List[int],
    nombre_occurrences: Optional[int] = None,
    date_fin_recurrence: Optional[date] = None,
    conserver_equipes: bool = True,
    conserver_objets: bool = True,
    nouveau_statut: str = 'PLANIFIEE'
) -> List[Tache]:
    """
    Duplique une tâche selon les jours de la semaine sélectionnés.

    Args:
        tache_id: ID de la tâche source
        jours_semaine: Liste des jours (0=Lundi, 6=Dimanche)
        nombre_occurrences: Nombre max d'occurrences (optionnel)
        date_fin_recurrence: Date limite (optionnel)
        conserver_equipes: Conserver les équipes assignées
        conserver_objets: Conserver les objets liés
        nouveau_statut: Statut des nouvelles tâches

    Returns:
        List[Tache]: Liste des nouvelles tâches créées

    Raises:
        ValidationError: Si intervalle < durée tâche (chevauchement)

    Exemples:
        >>> # Tâche source : Lun 13/01/2026 (1 jour)
        >>> # Créer des occurrences Lun-Mer-Ven
        >>> dupliquer_tache_recurrence_jours_semaine(
        ...     tache_id=123,
        ...     jours_semaine=[0, 2, 4],
        ...     nombre_occurrences=10
        ... )
        # Résultat : 10 tâches aux dates : Mer 15/01, Ven 17/01, Lun 20/01, ...
    """
    # Récupérer la tâche source
    try:
        tache_source = Tache.objects.get(id=tache_id, deleted_at__isnull=True)
    except Tache.DoesNotExist:
        raise ValidationError(f"Tâche #{tache_id} introuvable")

    # Calculer la durée de la tâche
    duree_tache = calculer_duree_tache(tache_source)

    # Calculer l'intervalle minimum entre les jours sélectionnés
    intervalle_min = calculer_intervalle_minimum_jours_semaine(jours_semaine)

    # ⚠️ VALIDATION CRITIQUE: intervalle >= durée tâche
    if intervalle_min < duree_tache:
        jours_labels = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
        jours_selectionnes_str = ', '.join([jours_labels[j] for j in sorted(jours_semaine)])

        raise ValidationError(
            f"Impossible de créer une récurrence avec les jours sélectionnés.\n\n"
            f"La tâche dure {duree_tache} jour(s) "
            f"(du {tache_source.date_debut_planifiee.strftime('%d/%m/%Y')} "
            f"au {tache_source.date_fin_planifiee.strftime('%d/%m/%Y')}).\n\n"
            f"Jours sélectionnés : {jours_selectionnes_str}\n"
            f"Intervalle minimum : {intervalle_min} jour(s)\n\n"
            f"❌ L'intervalle minimum ({intervalle_min} jour(s)) est inférieur à la durée "
            f"de la tâche ({duree_tache} jour(s)), ce qui provoquerait un chevauchement.\n\n"
            f"💡 Suggestions :\n"
            f"  • Sélectionnez des jours plus espacés (minimum {duree_tache} jours d'intervalle)\n"
            f"  • Réduisez la durée de la tâche\n"
            f"  • Utilisez un décalage personnalisé au lieu de jours spécifiques"
        )

    # Générer les dates selon les jours sélectionnés
    dates_occurrences = generer_dates_jours_semaine(
        date_debut=tache_source.date_debut_planifiee,
        jours_semaine=jours_semaine,
        nombre_occurrences=nombre_occurrences,
        date_fin_recurrence=date_fin_recurrence
    )

    if len(dates_occurrences) == 0:
        raise ValidationError(
            "Aucune occurrence ne peut être créée avec les paramètres fournis. "
            "Vérifiez la date de fin de récurrence."
        )

    # Créer les tâches avec transaction atomique
    nouvelles_taches = []

    with transaction.atomic():
        for date_occurrence in dates_occurrences:
            # Calculer le décalage (en jours) par rapport à la tâche source
            decalage = (date_occurrence - tache_source.date_debut_planifiee).days

            # Dupliquer la tâche avec ce décalage (réutilise la fonction existante)
            # ✅ skip_validation=True car l'intervalle minimum a déjà été validé en amont
            taches_creees = dupliquer_tache_avec_distributions(
                tache_id=tache_id,
                decalage_jours=decalage,
                nombre_occurrences=1,
                date_fin_recurrence=None,
                conserver_equipes=conserver_equipes,
                conserver_objets=conserver_objets,
                nouveau_statut=nouveau_statut,
                skip_validation=True  # ✅ NOUVEAU: Skip validation car déjà faite
            )

            nouvelles_taches.extend(taches_creees)

    return nouvelles_taches


# ==============================================================================
# FONCTIONS POUR LA SÉLECTION DE JOURS DU MOIS (MONTHLY)
# ==============================================================================

def calculer_intervalle_minimum_jours_mois(jours_mois: List[int]) -> int:
    """
    Calcule l'intervalle minimum (en jours) entre deux jours consécutifs du mois sélectionnés.

    Args:
        jours_mois: Liste triée des jours du mois (1-31)

    Returns:
        int: Nombre de jours minimum entre deux occurrences

    Exemples:
        >>> calculer_intervalle_minimum_jours_mois([1, 15])
        14  # 1er et 15 du mois : intervalle minimum = 14 jours

        >>> calculer_intervalle_minimum_jours_mois([5, 10, 20])
        5  # 5-10-20 : intervalle minimum = 5 jours

        >>> calculer_intervalle_minimum_jours_mois([28, 1])
        3  # 28 → 1er du mois suivant (approximation 28 jours) = 3 jours

        >>> calculer_intervalle_minimum_jours_mois([15])
        28  # Un seul jour = intervalle minimum de 28 jours (mois le plus court)
    """
    if not jours_mois or len(jours_mois) == 0:
        return 30  # Par défaut, mensuel

    if len(jours_mois) == 1:
        return 28  # Un seul jour = répétition mensuelle (28 jours minimum)

    jours_tries = sorted(jours_mois)
    intervalles = []

    # Calculer les intervalles entre jours consécutifs du même mois
    for i in range(len(jours_tries) - 1):
        intervalle = jours_tries[i + 1] - jours_tries[i]
        intervalles.append(intervalle)

    # Calculer l'intervalle de retour (dernier jour du mois → premier jour du mois suivant)
    # Approximation : mois le plus court = 28 jours (février non bissextile)
    intervalle_retour = 28 - jours_tries[-1] + jours_tries[0]
    intervalles.append(intervalle_retour)

    return min(intervalles)


def generer_dates_jours_mois(
    date_debut: date,
    jours_mois: List[int],
    nombre_occurrences: Optional[int] = None,
    date_fin_recurrence: Optional[date] = None
) -> List[date]:
    """
    Génère une liste de dates selon les jours du mois sélectionnés.

    Args:
        date_debut: Date de début (première occurrence)
        jours_mois: Liste des jours du mois (1-31)
        nombre_occurrences: Nombre max d'occurrences (optionnel)
        date_fin_recurrence: Date limite (optionnel)

    Returns:
        List[date]: Liste des dates d'occurrences

    Exemples:
        >>> date_debut = date(2026, 1, 15)  # 15 janvier
        >>> jours_mois = [1, 15]  # 1er et 15 de chaque mois
        >>> generer_dates_jours_mois(date_debut, jours_mois, nombre_occurrences=5)
        [
            date(2026, 2, 1),   # 1er février
            date(2026, 2, 15),  # 15 février
            date(2026, 3, 1),   # 1er mars
            date(2026, 3, 15),  # 15 mars
            date(2026, 4, 1)    # 1er avril
        ]

    Note:
        - Si un jour n'existe pas dans un mois (ex: 31 février), il est ignoré
        - Les dates sont générées chronologiquement
    """
    if not jours_mois:
        raise ValueError("jours_mois ne peut pas être vide")

    jours_tries = sorted(jours_mois)
    dates = []

    # Déterminer la date limite
    if date_fin_recurrence:
        date_limite = date_fin_recurrence
    else:
        # Par défaut: jusqu'au 31/12 de l'année en cours
        date_limite = date(date_debut.year, 12, 31)

    # Déterminer le nombre max d'occurrences
    max_occurrences = nombre_occurrences if nombre_occurrences else 100

    # Commencer à partir du lendemain de la date de début
    # (la tâche source existe déjà)
    date_courante = date_debut + timedelta(days=1)

    while len(dates) < max_occurrences:
        # Vérifier si on dépasse la date limite
        if date_courante > date_limite:
            break

        # Jour du mois (1-31)
        jour_mois = date_courante.day

        # Si ce jour est dans la sélection, ajouter à la liste
        if jour_mois in jours_tries:
            dates.append(date_courante)

        # Passer au jour suivant
        date_courante += timedelta(days=1)

    return dates


def dupliquer_tache_recurrence_jours_mois(
    tache_id: int,
    jours_mois: List[int],
    nombre_occurrences: Optional[int] = None,
    date_fin_recurrence: Optional[date] = None,
    conserver_equipes: bool = True,
    conserver_objets: bool = True,
    nouveau_statut: str = 'PLANIFIEE'
) -> List[Tache]:
    """
    Duplique une tâche selon les jours du mois sélectionnés.

    Args:
        tache_id: ID de la tâche source
        jours_mois: Liste des jours du mois (1-31)
        nombre_occurrences: Nombre max d'occurrences (optionnel)
        date_fin_recurrence: Date limite (optionnel)
        conserver_equipes: Conserver les équipes assignées
        conserver_objets: Conserver les objets liés
        nouveau_statut: Statut des nouvelles tâches

    Returns:
        List[Tache]: Liste des nouvelles tâches créées

    Raises:
        ValidationError: Si intervalle < durée tâche (chevauchement)

    Exemples:
        >>> # Tâche source : 15/01/2026 (1 jour)
        >>> # Créer des occurrences 1er et 15 de chaque mois
        >>> dupliquer_tache_recurrence_jours_mois(
        ...     tache_id=123,
        ...     jours_mois=[1, 15],
        ...     nombre_occurrences=10
        ... )
        # Résultat : 10 tâches aux dates : 1er fév, 15 fév, 1er mars, ...
    """
    # Récupérer la tâche source
    try:
        tache_source = Tache.objects.get(id=tache_id, deleted_at__isnull=True)
    except Tache.DoesNotExist:
        raise ValidationError(f"Tâche #{tache_id} introuvable")

    # Calculer la durée de la tâche
    duree_tache = calculer_duree_tache(tache_source)

    # Calculer l'intervalle minimum entre les jours sélectionnés
    intervalle_min = calculer_intervalle_minimum_jours_mois(jours_mois)

    # ⚠️ VALIDATION CRITIQUE: intervalle >= durée tâche
    if intervalle_min < duree_tache:
        jours_selectionnes_str = ', '.join([str(j) for j in sorted(jours_mois)])

        raise ValidationError(
            f"Impossible de créer une récurrence avec les jours du mois sélectionnés.\n\n"
            f"La tâche dure {duree_tache} jour(s) "
            f"(du {tache_source.date_debut_planifiee.strftime('%d/%m/%Y')} "
            f"au {tache_source.date_fin_planifiee.strftime('%d/%m/%Y')}).\n\n"
            f"Jours du mois sélectionnés : {jours_selectionnes_str}\n"
            f"Intervalle minimum : {intervalle_min} jour(s)\n\n"
            f"❌ L'intervalle minimum ({intervalle_min} jour(s)) est inférieur à la durée "
            f"de la tâche ({duree_tache} jour(s)), ce qui provoquerait un chevauchement.\n\n"
            f"💡 Suggestions :\n"
            f"  • Sélectionnez des jours plus espacés (minimum {duree_tache} jours d'intervalle)\n"
            f"  • Réduisez la durée de la tâche\n"
            f"  • Utilisez un décalage personnalisé au lieu de jours spécifiques"
        )

    # Générer les dates selon les jours du mois sélectionnés
    dates_occurrences = generer_dates_jours_mois(
        date_debut=tache_source.date_debut_planifiee,
        jours_mois=jours_mois,
        nombre_occurrences=nombre_occurrences,
        date_fin_recurrence=date_fin_recurrence
    )

    if len(dates_occurrences) == 0:
        raise ValidationError(
            "Aucune occurrence ne peut être créée avec les paramètres fournis. "
            "Vérifiez la date de fin de récurrence."
        )

    # Créer les tâches avec transaction atomique
    nouvelles_taches = []

    with transaction.atomic():
        for date_occurrence in dates_occurrences:
            # Calculer le décalage (en jours) par rapport à la tâche source
            decalage = (date_occurrence - tache_source.date_debut_planifiee).days

            # Dupliquer la tâche avec ce décalage (réutilise la fonction existante)
            # ✅ skip_validation=True car l'intervalle minimum a déjà été validé en amont
            taches_creees = dupliquer_tache_avec_distributions(
                tache_id=tache_id,
                decalage_jours=decalage,
                nombre_occurrences=1,
                date_fin_recurrence=None,
                conserver_equipes=conserver_equipes,
                conserver_objets=conserver_objets,
                nouveau_statut=nouveau_statut,
                skip_validation=True  # ✅ Skip validation car déjà faite
            )

            nouvelles_taches.extend(taches_creees)

    return nouvelles_taches
