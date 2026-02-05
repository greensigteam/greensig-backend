# ==============================================================================
# RÈGLES MÉTIER POUR LES DISTRIBUTIONS DE CHARGE
# ==============================================================================
"""
Ce module contient toutes les règles métier pour la gestion des statuts
des distributions de charge et leur synchronisation avec les tâches mères.

Architecture: State Machine Pattern
"""

from django.core.exceptions import ValidationError
from django.utils import timezone

from .constants import (
    MAX_REPORTS_CHAIN,
    ALLOWED_TRANSITIONS,
    MOTIFS_VALIDES,
    TOUS_MOTIFS,
    STATUTS_ACTIFS,
    STATUTS_GERES,
    ERROR_MESSAGES,
)


# ==============================================================================
# VALIDATION DES TRANSITIONS
# ==============================================================================

def valider_transition(ancien_statut: str, nouveau_statut: str) -> bool:
    """
    Vérifie si une transition de statut est autorisée.

    Args:
        ancien_statut: Statut actuel de la distribution
        nouveau_statut: Statut cible

    Returns:
        True si la transition est autorisée

    Raises:
        ValidationError: Si la transition n'est pas autorisée
    """
    if ancien_statut == nouveau_statut:
        return True  # Pas de changement

    transitions_autorisees = ALLOWED_TRANSITIONS.get(ancien_statut, [])

    if nouveau_statut not in transitions_autorisees:
        raise ValidationError(
            ERROR_MESSAGES['invalid_transition'].format(
                from_status=ancien_statut,
                to_status=nouveau_statut
            )
        )

    return True


def valider_motif(motif: str, obligatoire: bool = True) -> bool:
    """
    Valide un motif de report/annulation.

    Args:
        motif: Le motif à valider
        obligatoire: Si True, un motif vide lève une erreur

    Returns:
        True si le motif est valide

    Raises:
        ValidationError: Si le motif est invalide ou manquant
    """
    if not motif:
        if obligatoire:
            raise ValidationError(ERROR_MESSAGES['motif_required'])
        return True

    if motif not in MOTIFS_VALIDES:
        raise ValidationError(
            ERROR_MESSAGES['motif_invalid'].format(motif=motif)
        )

    return True


# ==============================================================================
# VALIDATION DE SUPPRESSION DES DISTRIBUTIONS
# ==============================================================================

def valider_suppression_distribution(distribution, force: bool = False) -> dict:
    """
    Valide si une distribution peut être supprimée.

    Args:
        distribution: Instance de DistributionCharge à supprimer
        force: Si True, ignore certaines validations (pour suppression en cascade)

    Returns:
        dict: {'peut_supprimer': bool, 'erreur': str|None, 'avertissement': str|None}

    Raises:
        ValidationError: Si la suppression n'est pas autorisée
    """
    tache = distribution.tache
    erreurs = []

    # 1. Vérifier que la tâche n'est pas terminée
    if tache.statut == 'TERMINEE':
        erreurs.append("Impossible de supprimer une distribution d'une tâche terminée")

    # 2. Vérifier que la distribution n'a pas été reportée (a un remplacement)
    if distribution.distribution_remplacement is not None:
        erreurs.append(
            f"Cette distribution a été reportée au {distribution.distribution_remplacement.date.strftime('%d/%m/%Y')}. "
            f"Supprimez d'abord la distribution de remplacement (ID: {distribution.distribution_remplacement.id})."
        )

    # 3. Vérifier que ce n'est pas la dernière distribution (sauf si force=True)
    if not force:
        nombre_distributions = tache.distributions_charge.count()
        if nombre_distributions <= 1:
            erreurs.append(
                "Impossible de supprimer la dernière distribution d'une tâche. "
                "Une tâche doit avoir au moins une distribution."
            )

    if erreurs:
        raise ValidationError(" | ".join(erreurs))

    return {'peut_supprimer': True, 'erreur': None}


def valider_suppression_distributions_bulk(tache, distributions_a_supprimer, distributions_a_conserver) -> dict:
    """
    Valide la suppression en masse de distributions (update_distributions, serializer update).

    Args:
        tache: Instance de Tache
        distributions_a_supprimer: QuerySet des distributions à supprimer
        distributions_a_conserver: Nombre de distributions qui seront conservées

    Returns:
        dict: {
            'peut_supprimer': bool,
            'erreurs': list,
            'distributions_bloquees': list[dict]  # [{id, date, raison}]
        }

    Raises:
        ValidationError: Si la suppression n'est pas autorisée
    """
    erreurs = []
    distributions_bloquees = []

    # 1. Vérifier que la tâche n'est pas terminée
    if tache.statut == 'TERMINEE':
        raise ValidationError("Impossible de modifier les distributions d'une tâche terminée")

    # 2. Vérifier qu'au moins une distribution sera conservée
    if distributions_a_conserver < 1:
        raise ValidationError(
            "Une tâche doit avoir au moins une distribution. "
            "Impossible de supprimer toutes les distributions."
        )

    # 3. Vérifier chaque distribution à supprimer
    for dist in distributions_a_supprimer:
        # Vérifier si elle a été reportée
        if dist.distribution_remplacement is not None:
            distributions_bloquees.append({
                'id': dist.id,
                'date': dist.date.strftime('%d/%m/%Y'),
                'raison': f"Reportée vers le {dist.distribution_remplacement.date.strftime('%d/%m/%Y')}"
            })

    if distributions_bloquees:
        dates = ", ".join([d['date'] for d in distributions_bloquees])
        raise ValidationError(
            f"Impossible de supprimer les distributions suivantes car elles ont été reportées: {dates}. "
            f"Supprimez d'abord les distributions de remplacement."
        )

    return {
        'peut_supprimer': True,
        'erreurs': [],
        'distributions_bloquees': []
    }


def synchroniser_tache_apres_suppression_distribution(tache, distribution_supprimee_etait_en_cours: bool):
    """
    Synchronise le statut de la tâche après suppression d'une distribution.

    Args:
        tache: Instance de Tache
        distribution_supprimee_etait_en_cours: True si la distribution supprimée était EN_COURS

    Returns:
        tuple: (tache_modifiee: bool, nouveau_statut: str|None)
    """
    # Recharger les distributions restantes
    distributions_restantes = tache.distributions_charge.all()

    # Compter par statut
    nb_non_realisee = distributions_restantes.filter(status='NON_REALISEE').count()
    nb_en_cours = distributions_restantes.filter(status='EN_COURS').count()
    nb_realisee = distributions_restantes.filter(status='REALISEE').count()

    tache_modifiee = False
    nouveau_statut = None

    # Si on a supprimé une distribution EN_COURS et qu'il n'y en a plus
    if distribution_supprimee_etait_en_cours and nb_en_cours == 0:
        if nb_non_realisee > 0:
            # Il reste du travail à faire
            if tache.statut == 'EN_COURS':
                tache.statut = 'PLANIFIEE'
                tache.save(update_fields=['statut'])
                tache_modifiee = True
                nouveau_statut = 'PLANIFIEE'
        elif nb_realisee > 0:
            # Tout est terminé
            tache.statut = 'TERMINEE'
            if not tache.date_fin_reelle:
                tache.date_fin_reelle = timezone.now().date()
            tache.save(update_fields=['statut', 'date_fin_reelle'])
            tache_modifiee = True
            nouveau_statut = 'TERMINEE'

    return tache_modifiee, nouveau_statut


# ==============================================================================
# GESTION DES REPORTS CHAÎNÉS
# ==============================================================================

def valider_limite_reports(distribution) -> int:
    """
    Vérifie que la limite de reports n'est pas atteinte.

    Args:
        distribution: Instance de DistributionCharge

    Returns:
        int: Nombre actuel de reports dans la chaîne

    Raises:
        ValidationError: Si la limite est atteinte
    """
    chain_length = compter_reports_chaine(distribution)

    if chain_length >= MAX_REPORTS_CHAIN:
        raise ValidationError(
            ERROR_MESSAGES['max_reports_reached'].format(
                count=chain_length,
                max=MAX_REPORTS_CHAIN
            )
        )

    return chain_length


def compter_reports_chaine(distribution) -> int:
    """
    Compte le nombre de reports dans la chaîne d'une distribution.

    Args:
        distribution: Instance de DistributionCharge

    Returns:
        int: Nombre de reports (0 si pas de report)
    """
    chain_length = 0
    current = distribution
    visited = set()  # Protection contre boucles infinies

    while current.distribution_origine_id and current.id not in visited:
        visited.add(current.id)
        chain_length += 1
        current = current.distribution_origine

        if current is None:
            break

    return chain_length


def get_distribution_finale(distribution):
    """
    Suit la chaîne de reports jusqu'à la distribution finale.

    Args:
        distribution: Instance de DistributionCharge

    Returns:
        DistributionCharge: La dernière distribution de la chaîne
    """
    current = distribution
    visited = set()  # Protection contre boucles infinies

    while current.distribution_remplacement_id and current.id not in visited:
        visited.add(current.id)
        if current.distribution_remplacement:
            current = current.distribution_remplacement
        else:
            break

    return current


def get_distribution_origine(distribution):
    """
    Remonte la chaîne de reports jusqu'à la distribution d'origine.

    Args:
        distribution: Instance de DistributionCharge

    Returns:
        DistributionCharge: La première distribution de la chaîne
    """
    current = distribution
    visited = set()

    while current.distribution_origine_id and current.id not in visited:
        visited.add(current.id)
        if current.distribution_origine:
            current = current.distribution_origine
        else:
            break

    return current


def get_chaine_reports(distribution) -> list:
    """
    Retourne l'historique complet des reports pour une distribution.

    Args:
        distribution: Instance de DistributionCharge

    Returns:
        list: Liste des dictionnaires avec les infos de chaque distribution
    """
    chaine = []

    # Remonter à l'origine
    origine = get_distribution_origine(distribution)

    # Descendre la chaîne
    current = origine
    visited = set()

    while current and current.id not in visited:
        visited.add(current.id)
        chaine.append({
            'id': current.id,
            'date': str(current.date),
            'status': current.status,
            'motif': current.motif_report_annulation or '',
            'commentaire': current.commentaire or '',
            'heures_planifiees': current.heures_planifiees,
            'heures_reelles': current.heures_reelles,
        })

        if current.distribution_remplacement_id:
            current = current.distribution_remplacement
        else:
            break

    return chaine


# ==============================================================================
# SYNCHRONISATION TÂCHE ↔ DISTRIBUTION
# ==============================================================================

def synchroniser_tache_apres_demarrage(tache, est_premiere_distribution: bool, date_debut_reelle=None):
    """
    Met à jour le statut de la tâche après le démarrage d'une distribution.

    Règle: Si c'est la première distribution démarrée et que la tâche
    est en PLANIFIEE, passer la tâche en EN_COURS.

    ✅ SIMPLIFIÉ: Plus de EN_RETARD ni EXPIREE

    Args:
        tache: Instance de Tache
        est_premiere_distribution: True si aucune distribution active avant
        date_debut_reelle: Date réelle de début (optionnel, défaut: aujourd'hui)

    Returns:
        bool: True si la tâche a été modifiée
    """
    if not est_premiere_distribution:
        return False

    if tache.statut == 'PLANIFIEE':
        tache.statut = 'EN_COURS'
        # Utiliser la date fournie ou aujourd'hui par défaut
        tache.date_debut_reelle = date_debut_reelle if date_debut_reelle else timezone.now().date()
        tache.save(update_fields=['statut', 'date_debut_reelle'])
        return True

    return False


def synchroniser_tache_apres_completion(tache, date_fin_reelle=None) -> bool:
    """
    Met à jour le statut de la tâche après la complétion d'une distribution.

    Règle: Si toutes les distributions sont dans un état terminal (REALISEE,
    ANNULEE, ou REPORTEE avec remplacement terminal), la tâche est TERMINEE.

    Args:
        tache: Instance de Tache
        date_fin_reelle: Date réelle de fin (optionnel, défaut: aujourd'hui)

    Returns:
        bool: True si la tâche a été marquée comme terminée
    """
    if tache.statut != 'EN_COURS':
        return False

    if verifier_toutes_distributions_terminees(tache):
        tache.statut = 'TERMINEE'
        # Utiliser la date fournie ou aujourd'hui par défaut
        tache.date_fin_reelle = date_fin_reelle if date_fin_reelle else timezone.now().date()
        tache.save(update_fields=['statut', 'date_fin_reelle'])
        return True

    return False


def synchroniser_tache_apres_annulation(tache) -> tuple:
    """
    Met à jour le statut de la tâche après l'annulation d'une distribution.

    Règles:
    - Si toutes les distributions sont ANNULEE → Tâche ANNULEE
    - Si certaines REALISEE, reste ANNULEE → Tâche TERMINEE
    - Si reste des distributions actives → Pas de changement
    - Si plus de distributions actives et aucune réalisée → PLANIFIEE

    Args:
        tache: Instance de Tache

    Returns:
        tuple: (bool: modifiée, str: nouveau_statut)
    """
    distributions = tache.distributions_charge.all()

    # Compter par statut
    total = distributions.count()
    annulees = distributions.filter(status='ANNULEE').count()
    realisees = distributions.filter(status='REALISEE').count()
    actives = distributions.filter(status__in=STATUTS_ACTIFS).count()

    # Toutes annulées → Tâche annulée
    if annulees == total:
        tache.statut = 'ANNULEE'
        tache.save(update_fields=['statut'])
        return True, 'ANNULEE'

    # Il reste des distributions actives → Pas de changement
    if actives > 0:
        return False, tache.statut

    # Certaines réalisées, reste annulées → Terminée
    if realisees > 0:
        tache.statut = 'TERMINEE'
        tache.date_fin_reelle = timezone.now().date()
        tache.save(update_fields=['statut', 'date_fin_reelle'])
        return True, 'TERMINEE'

    # Aucune réalisée, aucune active → Repasser en PLANIFIEE
    tache.statut = 'PLANIFIEE'
    tache.date_debut_reelle = None
    tache.save(update_fields=['statut', 'date_debut_reelle'])
    return True, 'PLANIFIEE'


def synchroniser_tache_apres_restauration(tache) -> tuple:
    """
    Met à jour le statut de la tâche après la restauration d'une distribution.

    Règle: Si la tâche était ANNULEE, la repasser en PLANIFIEE.

    Args:
        tache: Instance de Tache

    Returns:
        tuple: (bool: modifiée, str: nouveau_statut)
    """
    if tache.statut == 'ANNULEE':
        tache.statut = 'PLANIFIEE'
        tache.save(update_fields=['statut'])
        return True, 'PLANIFIEE'

    return False, tache.statut


def restaurer_distributions_apres_replanification(tache) -> int:
    """
    Restaure les distributions ANNULEE en NON_REALISEE après replanification d'une tâche.

    Appelé quand une tâche ANNULEE est modifiee (replanifiee).
    Les distributions qui etaient annulees doivent etre restaurees
    pour permettre leur execution.

    Args:
        tache: Instance de Tache

    Returns:
        int: Nombre de distributions restaurées
    """
    from .models import DistributionCharge

    # Restaurer toutes les distributions ANNULEE en NON_REALISEE
    distributions_annulees = tache.distributions_charge.filter(status='ANNULEE')
    count = distributions_annulees.count()

    if count > 0:
        distributions_annulees.update(status='NON_REALISEE')
        print(f"[REPLANIFICATION] {count} distribution(s) restaurée(s) pour la tâche #{tache.id}")

    return count


def etendre_tache_si_necessaire(tache, nouvelle_date) -> bool:
    """
    Étend la date de fin de la tâche si la nouvelle date est au-delà.

    Args:
        tache: Instance de Tache
        nouvelle_date: Date de la nouvelle distribution

    Returns:
        bool: True si la tâche a été étendue
    """
    if nouvelle_date > tache.date_fin_planifiee:
        tache.date_fin_planifiee = nouvelle_date
        tache.save(update_fields=['date_fin_planifiee'])
        return True

    return False


# ==============================================================================
# VÉRIFICATIONS
# ==============================================================================

def verifier_toutes_distributions_terminees(tache) -> bool:
    """
    Vérifie si toutes les distributions d'une tâche sont dans un état terminal.

    Une distribution est considérée comme terminée si:
    - Son statut est REALISEE ou ANNULEE
    - Son statut est REPORTEE ET sa distribution de remplacement finale
      est REALISEE ou ANNULEE

    Args:
        tache: Instance de Tache

    Returns:
        bool: True si toutes les distributions sont terminées
    """
    for dist in tache.distributions_charge.all():
        statut_effectif = get_statut_effectif(dist)
        if statut_effectif not in STATUTS_GERES:
            return False

    return True


def get_statut_effectif(distribution) -> str:
    """
    Retourne le statut effectif d'une distribution en tenant compte
    de la chaîne de reports.

    Args:
        distribution: Instance de DistributionCharge

    Returns:
        str: Le statut effectif
    """
    if distribution.status == 'REPORTEE':
        finale = get_distribution_finale(distribution)
        return finale.status

    return distribution.status


def verifier_premiere_distribution_active(tache) -> bool:
    """
    Vérifie si c'est la première distribution à être activée.

    Args:
        tache: Instance de Tache

    Returns:
        bool: True si aucune distribution n'est EN_COURS ou REALISEE
    """
    return not tache.distributions_charge.filter(
        status__in=['EN_COURS', 'REALISEE']
    ).exists()


def verifier_equipe_assignee(tache) -> bool:
    """
    Vérifie qu'au moins une équipe est assignée à la tâche.

    Args:
        tache: Instance de Tache

    Returns:
        bool: True si au moins une équipe est assignée
    """
    # Vérifier le champ ManyToMany (nouveau)
    if tache.equipes.exists():
        return True

    # Vérifier le champ legacy (ancien)
    if tache.id_equipe_id:
        return True

    return False


def verifier_date_disponible(tache, date, exclude_id=None) -> bool:
    """
    Vérifie qu'aucune distribution n'existe déjà à cette date pour la tâche.

    Args:
        tache: Instance de Tache
        date: Date à vérifier
        exclude_id: ID de distribution à exclure (pour les modifications)

    Returns:
        bool: True si la date est disponible
    """
    queryset = tache.distributions_charge.filter(date=date)

    if exclude_id:
        queryset = queryset.exclude(pk=exclude_id)

    return not queryset.exists()


# ==============================================================================
# SYNCHRONISATION TÂCHE → DISTRIBUTIONS
# ==============================================================================

def compter_distributions_actives(tache) -> int:
    """
    Compte le nombre de distributions actives pour une tâche.

    Args:
        tache: Instance de Tache

    Returns:
        int: Nombre de distributions actives (NON_REALISEE, EN_COURS)
    """
    return tache.distributions_charge.filter(status__in=STATUTS_ACTIFS).count()


def valider_terminaison_tache(tache) -> bool:
    """
    Vérifie qu'une tâche peut être terminée (pas de distributions actives).

    Args:
        tache: Instance de Tache

    Returns:
        bool: True si la tâche peut être terminée

    Raises:
        ValidationError: Si des distributions sont encore actives
    """
    count = compter_distributions_actives(tache)

    if count > 0:
        raise ValidationError(
            ERROR_MESSAGES['cannot_complete_with_active_distributions'].format(count=count)
        )

    return True


def synchroniser_distributions_apres_annulation_tache(tache) -> int:
    """
    Annule toutes les distributions actives d'une tâche annulée.

    Cette fonction est appelée quand une tâche passe au statut ANNULEE.
    Toutes les distributions actives (NON_REALISEE, EN_COURS)
    sont automatiquement annulées avec le motif "ANNULATION_TACHE".

    Args:
        tache: Instance de Tache

    Returns:
        int: Nombre de distributions annulées
    """
    distributions_actives = tache.distributions_charge.filter(status__in=STATUTS_ACTIFS)
    count = distributions_actives.count()

    if count > 0:
        distributions_actives.update(
            status='ANNULEE',
            motif_report_annulation='ANNULATION_TACHE',
            updated_at=timezone.now()
        )

    return count


def corriger_distributions_tache_annulee(tache) -> int:
    """
    Corrige les distributions d'une tâche déjà annulée (migration de données).

    Cette fonction est utilisée pour corriger les données existantes où
    une tâche est ANNULEE mais ses distributions sont encore actives.

    Args:
        tache: Instance de Tache (doit être au statut ANNULEE)

    Returns:
        int: Nombre de distributions corrigées
    """
    if tache.statut != 'ANNULEE':
        return 0

    return synchroniser_distributions_apres_annulation_tache(tache)
