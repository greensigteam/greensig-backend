# ==============================================================================
# CONSTANTES POUR LE MODULE PLANIFICATION
# ==============================================================================

# Limite maximale de reports chaînés pour une distribution
MAX_REPORTS_CHAIN = 5

# ==============================================================================
# STATUTS DES DISTRIBUTIONS
# ==============================================================================

STATUT_DISTRIBUTION_CHOICES = [
    ('NON_REALISEE', 'Non Réalisée'),
    ('EN_COURS', 'En Cours'),
    ('REALISEE', 'Réalisée'),
    ('REPORTEE', 'Reportée'),
    ('ANNULEE', 'Annulée'),
    ('EN_RETARD', 'En Retard'),
]

# Statuts terminaux (pas de transition possible)
STATUTS_TERMINAUX = ['REALISEE', 'REPORTEE']

# Statuts actifs (travail en cours ou à faire)
STATUTS_ACTIFS = ['NON_REALISEE', 'EN_COURS', 'EN_RETARD']

# Statuts considérés comme "gérés" pour le calcul de complétion de tâche
STATUTS_GERES = ['REALISEE', 'ANNULEE']

# ==============================================================================
# MOTIFS DE REPORT/ANNULATION
# ==============================================================================

MOTIF_CHOICES = [
    ('METEO', 'Conditions météorologiques'),
    ('ABSENCE', 'Absence équipe'),
    ('EQUIPEMENT', 'Problème équipement'),
    ('CLIENT', 'Demande client'),
    ('URGENCE', 'Réaffectation urgente'),
    ('AUTRE', 'Autre motif'),
    # Motifs système (utilisés automatiquement par le système)
    ('EXPIRATION', 'Tâche expirée'),
    ('ANNULATION_TACHE', 'Tâche annulée'),
]

# Motifs valides pour les actions manuelles (excluant les motifs système)
MOTIFS_VALIDES = ['METEO', 'ABSENCE', 'EQUIPEMENT', 'CLIENT', 'URGENCE', 'AUTRE']

# Tous les motifs (incluant système) pour validation interne
TOUS_MOTIFS = [code for code, _ in MOTIF_CHOICES]

# ==============================================================================
# TRANSITIONS AUTORISÉES
# ==============================================================================

# Dictionnaire définissant les transitions autorisées pour chaque statut
ALLOWED_TRANSITIONS = {
    'NON_REALISEE': ['EN_COURS', 'REPORTEE', 'ANNULEE'],
    'EN_COURS': ['REALISEE', 'ANNULEE'],
    'REALISEE': [],  # État terminal
    'REPORTEE': [],  # État terminal (nouvelle distribution créée)
    'ANNULEE': ['NON_REALISEE'],  # Restauration possible
    'EN_RETARD': ['EN_COURS', 'REPORTEE', 'ANNULEE'],
}

# ==============================================================================
# MESSAGES D'ERREUR
# ==============================================================================

ERROR_MESSAGES = {
    'invalid_transition': "Transition {from_status} → {to_status} non autorisée.",
    'max_reports_reached': (
        "Cette distribution a déjà été reportée {count} fois. "
        "Maximum autorisé: {max}. "
        "Veuillez terminer ou annuler cette distribution."
    ),
    'motif_required': "Le motif est obligatoire pour cette action.",
    'motif_invalid': "Le motif '{motif}' n'est pas valide.",
    'date_future_required': "La nouvelle date doit être dans le futur.",
    'date_conflict': "Une distribution existe déjà pour le {date}.",
    'no_team_assigned': "Aucune équipe assignée à cette tâche.",
    'invalid_status_for_action': "Impossible d'effectuer cette action sur une distribution au statut {status}.",
    # Erreurs liées à la synchronisation tâche → distributions
    'cannot_complete_with_active_distributions': (
        "Impossible de terminer la tâche : {count} distribution(s) sont encore actives "
        "(non réalisées, en cours ou en retard). Veuillez d'abord terminer ou annuler ces distributions."
    ),
    'task_expired_distributions_cancelled': (
        "{count} distribution(s) ont été automatiquement annulées suite à l'expiration de la tâche."
    ),
    'task_cancelled_distributions_cancelled': (
        "{count} distribution(s) ont été automatiquement annulées suite à l'annulation de la tâche."
    ),
}
