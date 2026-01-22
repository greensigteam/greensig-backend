from django.db import models
from django.core.exceptions import ValidationError
from api_users.models import Client, StructureClient, Equipe, Operateur
from api.models import Objet
from django.utils import timezone

# TODO: La fonctionnalité de création de type de tâche côté frontend a été supprimée (bouton "Créer un nouveau type").
# Elle doit être réactivée uniquement si nécessaire, via le backend ou une interface admin dédiée.
# Voir demande utilisateur du 17/12/2025.
class TypeTache(models.Model):
    UNITE_PRODUCTIVITE_CHOICES = [
        ('m2', 'Mètres carrés (m²)'),
        ('ml', 'Mètres linéaires (ml)'),
        ('unite', 'Unités'),
        ('cuvettes', 'Cuvettes'),
        ('arbres', 'Arbres'),
    ]

    nom_tache = models.CharField(max_length=100, unique=True, verbose_name="Nom de la tâche")
    symbole = models.CharField(max_length=50, blank=True, verbose_name="Symbole")
    description = models.TextField(blank=True, verbose_name="Description")
    productivite_theorique = models.FloatField(null=True, blank=True, verbose_name="Productivité théorique")
    unite_productivite = models.CharField(
        max_length=20,
        choices=UNITE_PRODUCTIVITE_CHOICES,
        default='m2',
        blank=True,
        verbose_name="Unité de productivité"
    )

    class Meta:
        verbose_name = "Type de tâche"
        verbose_name_plural = "Types de tâches"
        ordering = ['nom_tache']

    def __str__(self):
        return self.nom_tache

class Tache(models.Model):
    PRIORITE_CHOICES = [
        (1, 'Priorité 1 (Très basse)'),
        (2, 'Priorité 2 (Basse)'),
        (3, 'Priorité 3 (Moyenne)'),
        (4, 'Priorité 4 (Haute)'),
        (5, 'Priorité 5 (Urgent)'),
    ]
    
    STATUT_CHOICES = [
        ('PLANIFIEE', 'Planifiée'),
        ('EN_RETARD', 'En retard'),  # Heure de début passée sans démarrage
        ('EXPIREE', 'Expirée'),      # Heure de fin passée sans démarrage
        ('EN_COURS', 'En cours'),
        ('TERMINEE', 'Terminée'),
        ('ANNULEE', 'Annulée'),
    ]

    ETAT_VALIDATION_CHOICES = [
        ('EN_ATTENTE', 'En attente de validation'),
        ('VALIDEE', 'Validée'),
        ('REJETEE', 'Rejetée'),
    ]

    # Structure cliente pour la tâche
    id_structure_client = models.ForeignKey(
        StructureClient,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='taches',
        verbose_name="Structure cliente"
    )

    # LEGACY: Ancien champ client (à supprimer après migration)
    id_client = models.ForeignKey(
        Client,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='taches_legacy',
        verbose_name="[LEGACY] Client"
    )

    id_type_tache = models.ForeignKey(TypeTache, on_delete=models.PROTECT, related_name='taches', verbose_name="Type de tâche")

    # Équipe unique (legacy - conservé pour rétrocompatibilité)
    id_equipe = models.ForeignKey(Equipe, on_delete=models.SET_NULL, null=True, blank=True, related_name='taches_legacy', verbose_name="Équipe (legacy)")

    # Multi-équipes (US-PLAN-013)
    equipes = models.ManyToManyField(Equipe, related_name='taches', blank=True, verbose_name="Équipes assignées")

    date_debut_planifiee = models.DateField(verbose_name="Date début planifiée")
    date_fin_planifiee = models.DateField(verbose_name="Date fin planifiée")
    date_echeance = models.DateField(null=True, blank=True, verbose_name="Date d'échéance")
    
    priorite = models.IntegerField(choices=PRIORITE_CHOICES, default=3, verbose_name="Priorité")
    commentaires = models.TextField(blank=True, verbose_name="Commentaires")
    
    date_affectation = models.DateField(null=True, blank=True, verbose_name="Date d'affectation")
    date_debut_reelle = models.DateField(null=True, blank=True, verbose_name="Date début réelle")
    date_fin_reelle = models.DateField(null=True, blank=True, verbose_name="Date fin réelle")
    duree_reelle_minutes = models.IntegerField(null=True, blank=True, verbose_name="Durée réelle (minutes)")
    charge_estimee_heures = models.FloatField(null=True, blank=True, verbose_name="Charge estimée (heures)",
        help_text="Calculée automatiquement ou saisie manuellement")
    charge_manuelle = models.BooleanField(default=False, verbose_name="Charge manuelle",
        help_text="Si True, la charge ne sera pas recalculée automatiquement")

    description_travaux = models.TextField(blank=True, verbose_name="Description des travaux")
    
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='PLANIFIEE', verbose_name="Statut")
    note_qualite = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Note qualité (1-5)")

    # Validation par l'administrateur
    etat_validation = models.CharField(
        max_length=20,
        choices=ETAT_VALIDATION_CHOICES,
        default='EN_ATTENTE',
        verbose_name="État de validation"
    )
    date_validation = models.DateTimeField(null=True, blank=True, verbose_name="Date de validation")
    validee_par = models.ForeignKey(
        'api_users.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='taches_validees',
        verbose_name="Validée par"
    )
    commentaire_validation = models.TextField(blank=True, verbose_name="Commentaire de validation")

    notifiee = models.BooleanField(default=False, verbose_name="Notifiée")
    confirmee = models.BooleanField(default=False, verbose_name="Confirmée")
    
    # Lien avec Réclamation (MCD Entité 19 / Note 54)
    reclamation = models.ForeignKey(
        'api_reclamations.Reclamation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='taches_correctives',
        verbose_name="Réclamation liée"
    )
    
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name="Supprimé le") # Soft delete

    # Date de création automatique
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name="Date de création", null=True, blank=True)

    # Many-to-Many relation with Inventory Objects
    objets = models.ManyToManyField(Objet, related_name='taches', blank=True, verbose_name="Objets inventaire")

    reference = models.CharField(max_length=100, unique=True, blank=True, null=True, db_index=True, verbose_name="Référence technique")

    # Gestion du temps de travail (Option 2: Approche Hybride)
    temps_travail_manuel = models.FloatField(
        null=True,
        blank=True,
        verbose_name="Temps de travail manuel (heures)",
        help_text="Temps de travail saisi manuellement (écrase le calcul automatique)"
    )
    temps_travail_manuel_par = models.ForeignKey(
        'api_users.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='taches_temps_manuel',
        verbose_name="Temps manuel saisi par"
    )
    temps_travail_manuel_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de saisie manuelle"
    )

    class Meta:
        verbose_name = "Tâche"
        verbose_name_plural = "Tâches"
        ordering = ['date_debut_planifiee']

    def __str__(self):
        return f"{self.id_type_tache} - {self.date_debut_planifiee}"

    def clean(self):
        """Validation métier de la tâche"""
        super().clean()

        # ✅ CHANGEMENT: Contrainte "même jour" retirée pour permettre tâches multi-jours
        # Désormais une tâche peut s'étendre sur plusieurs jours avec distribution de charge par jour
        # via le modèle DistributionCharge
        if self.date_debut_planifiee and self.date_fin_planifiee:
            if self.date_fin_planifiee < self.date_debut_planifiee:
                raise ValidationError({
                    'date_fin_planifiee': "La date de fin ne peut pas être antérieure à la date de début."
                })

    @property
    def computed_statut(self):
        """
        ✅ Calcule dynamiquement le statut réel basé sur les dates/heures actuelles.

        Cette propriété ignore le statut stocké et calcule ce que devrait être
        le statut en fonction de l'heure actuelle et des distributions.

        Règles de recalcul (conventions standard de gestion de projet):

        STATUTS FINAUX (protégés - ne jamais recalculer pour l'affichage):
        - TERMINEE: travail effectué, audit trail
        - VALIDEE: validation finale du client/superviseur
        - REJETEE: décision prise, nécessite nouvelle tâche
        - ANNULEE: annulation explicite (réactivation via action utilisateur uniquement)

        STATUTS CONDITIONNELS:
        - EN_COURS:
            * Si distributions REALISEE existent → protégé (travail en cours)
            * Si aucune distribution REALISEE → recalcul autorisé (pas de travail effectif)

        STATUTS RECALCULABLES:
        - PLANIFIEE, EN_RETARD, EXPIREE: toujours recalculés selon les dates

        NOTE: La réactivation d'une tâche ANNULEE se fait via le formulaire de
        replanification qui change explicitement le statut, PAS via computed_statut.

        Returns:
            str: Le statut calculé dynamiquement
        """
        # ══════════════════════════════════════════════════════════════════════
        # STATUTS FINAUX - Ne jamais recalculer (actions explicites requises)
        # ══════════════════════════════════════════════════════════════════════
        if self.statut in ('TERMINEE', 'VALIDEE', 'REJETEE', 'ANNULEE'):
            return self.statut

        # ══════════════════════════════════════════════════════════════════════
        # EN_COURS - Protéger seulement si du travail a été effectivement fait
        # ══════════════════════════════════════════════════════════════════════
        if self.statut == 'EN_COURS':
            # Vérifier si des distributions ont été marquées comme réalisées
            has_realisee = self.distributions_charge.filter(status='REALISEE').exists()
            if has_realisee:
                # Du travail effectif a été fait → garder EN_COURS
                return self.statut
            # Aucun travail effectif → permettre le recalcul (replanification possible)

        # ══════════════════════════════════════════════════════════════════════
        # EN_RETARD, EXPIREE, PLANIFIEE - Recalcul basé sur les dates
        # ══════════════════════════════════════════════════════════════════════

        now = timezone.now()
        today = now.date()
        current_time = now.time()

        # Récupérer les distributions triées
        distributions = list(self.distributions_charge.order_by('date', 'heure_debut'))

        if distributions:
            first_dist = distributions[0]
            last_dist = distributions[-1]

            # Vérifier si EXPIREE (dernière distribution passée)
            if last_dist.date < today:
                return 'EXPIREE'
            if last_dist.date == today and last_dist.heure_fin and current_time > last_dist.heure_fin:
                return 'EXPIREE'

            # Vérifier si EN_RETARD (première distribution passée mais pas expirée)
            if first_dist.date < today:
                return 'EN_RETARD'
            if first_dist.date == today and first_dist.heure_debut and current_time > first_dist.heure_debut:
                return 'EN_RETARD'

            # Sinon PLANIFIEE
            return 'PLANIFIEE'

        # Pas de distributions - utiliser les dates planifiées
        if self.date_fin_planifiee:
            # Convertir en date si c'est un datetime
            fin_date = self.date_fin_planifiee.date() if hasattr(self.date_fin_planifiee, 'date') else self.date_fin_planifiee
            if fin_date < today:
                return 'EXPIREE'

        if self.date_debut_planifiee:
            debut_date = self.date_debut_planifiee.date() if hasattr(self.date_debut_planifiee, 'date') else self.date_debut_planifiee
            if debut_date < today:
                return 'EN_RETARD'

        return 'PLANIFIEE'

    @property
    def charge_totale_distributions(self):
        """
        ✅ Calcule la charge totale depuis les distributions journalières.

        Returns:
            float: Somme des heures planifiées de toutes les distributions
        """
        return self.distributions_charge.aggregate(
            total=models.Sum('heures_planifiees')
        )['total'] or 0.0

    @property
    def nombre_jours_travail(self):
        """
        Calcule le nombre de jours travaillés (avec distribution > 0).

        Returns:
            int: Nombre de jours avec des heures planifiées
        """
        return self.distributions_charge.filter(heures_planifiees__gt=0).count()

    @property
    def temps_travail_total(self):
        """
        ✅ Calcule le temps de travail total pour cette tâche (OPTION 2: Approche Hybride).

        Priorité de calcul:
        1. temps_travail_manuel - Si saisi manuellement par un utilisateur (priorité absolue)
        2. heures_reelles (DistributionCharge) - Heures réellement travaillées (le plus fiable)
        3. heures_travaillees (ParticipationTache) - Somme des heures par opérateur
        4. charge_estimee_heures - Estimation initiale
        5. heures_planifiees (DistributionCharge) - Fallback minimum
        6. 0.0 - Aucune donnée disponible

        Returns:
            dict: {
                'heures': float,           # Nombre d'heures calculées
                'source': str,             # Source des données
                'fiable': bool,            # Indique si la donnée est fiable (réelle vs estimée)
                'manuel': bool,            # True si saisi manuellement
                'manuel_par': str|None,    # Nom de l'utilisateur qui a saisi
                'manuel_date': str|None    # Date de saisie manuelle (ISO format)
            }

        Sources possibles:
        - 'MANUEL': Saisi manuellement par un utilisateur (fiable=True)
        - 'REEL': Heures réelles des distributions (fiable=True)
        - 'PARTICIPATION': Heures déclarées par les opérateurs (fiable=True)
        - 'ESTIME': Charge estimée (fiable=False)
        - 'PLANIFIE': Heures planifiées (fiable=False)
        - 'AUCUNE': Aucune donnée disponible (fiable=False)
        """
        # 1. PRIORITÉ ABSOLUE: Temps manuel saisi par un utilisateur
        if self.temps_travail_manuel is not None and self.temps_travail_manuel >= 0:
            return {
                'heures': float(self.temps_travail_manuel),
                'source': 'MANUEL',
                'fiable': True,
                'manuel': True,
                'manuel_par': self.temps_travail_manuel_par.get_full_name() if self.temps_travail_manuel_par else None,
                'manuel_date': self.temps_travail_manuel_date.isoformat() if self.temps_travail_manuel_date else None
            }

        # 2. Essayer heures_reelles des distributions (données terrain réelles)
        heures_reelles = self.distributions_charge.aggregate(
            total=models.Sum('heures_reelles')
        )['total']

        if heures_reelles and heures_reelles > 0:
            return {
                'heures': float(heures_reelles),
                'source': 'REEL',
                'fiable': True,
                'manuel': False,
                'manuel_par': None,
                'manuel_date': None
            }

        # 3. Essayer heures_travaillees des participations (déclarations opérateurs)
        heures_participation = self.participations.aggregate(
            total=models.Sum('heures_travaillees')
        )['total']

        if heures_participation and heures_participation > 0:
            return {
                'heures': float(heures_participation),
                'source': 'PARTICIPATION',
                'fiable': True,
                'manuel': False,
                'manuel_par': None,
                'manuel_date': None
            }

        # 4. Utiliser charge_estimee_heures (estimation initiale)
        if self.charge_estimee_heures and self.charge_estimee_heures > 0:
            return {
                'heures': float(self.charge_estimee_heures),
                'source': 'ESTIME',
                'fiable': False,
                'manuel': False,
                'manuel_par': None,
                'manuel_date': None
            }

        # 5. Fallback: heures_planifiees (minimum prévu)
        heures_planifiees = self.charge_totale_distributions
        if heures_planifiees > 0:
            return {
                'heures': float(heures_planifiees),
                'source': 'PLANIFIE',
                'fiable': False,
                'manuel': False,
                'manuel_par': None,
                'manuel_date': None
            }

        # 6. Aucune donnée disponible
        return {
            'heures': 0.0,
            'source': 'AUCUNE',
            'fiable': False,
            'manuel': False,
            'manuel_par': None,
            'manuel_date': None
        }

    @property
    def is_late(self):
        """
        Vérifie si la tâche est en retard (la première distribution a commencé sans démarrage).

        Une tâche est en retard si:
        - Son statut est PLANIFIEE
        - La PREMIÈRE distribution (date + heure_debut) est passée
        - OU si pas de distributions, la date de début planifiée est passée

        Returns:
            bool: True si la tâche est en retard
        """
        if self.statut != 'PLANIFIEE':
            return False

        now = timezone.now()
        today = now.date()
        current_time = now.time()

        # Récupérer toutes les distributions triées chronologiquement (date ASC, heure_debut ASC)
        distributions = list(self.distributions_charge.order_by('date', 'heure_debut'))

        if distributions:
            # La première distribution chronologiquement
            first_dist = distributions[0]

            # Si la date de la première distribution est passée (avant aujourd'hui)
            if first_dist.date < today:
                return True

            # Si la première distribution est aujourd'hui, vérifier si son heure de début est passée
            if first_dist.date == today and first_dist.heure_debut is not None:
                if current_time > first_dist.heure_debut:
                    return True

            # La première distribution est dans le futur ou aujourd'hui mais pas encore commencée
            return False

        # Pas de distributions → utiliser date_debut_planifiee
        return self.date_debut_planifiee < today

    def mark_as_late(self):
        """
        Marque la tâche comme en retard.
        Appelé automatiquement quand l'heure de début est dépassée sans démarrage.

        Returns:
            bool: True si le statut a été changé
        """
        if self.is_late and self.statut == 'PLANIFIEE':
            self.statut = 'EN_RETARD'
            self.save(update_fields=['statut'])
            return True
        return False

    @property
    def is_expired(self):
        """
        Vérifie si la tâche est expirée (la dernière distribution est passée).

        Une tâche est expirée si:
        - Son statut est PLANIFIEE ou EN_RETARD
        - La DERNIÈRE distribution (date + heure_fin) est passée
        - OU si pas de distributions, la date de fin planifiée est passée

        Returns:
            bool: True si la tâche est expirée
        """
        if self.statut not in ('PLANIFIEE', 'EN_RETARD'):
            return False

        now = timezone.now()
        today = now.date()
        current_time = now.time()

        # Récupérer toutes les distributions triées chronologiquement (date ASC, heure_fin ASC)
        distributions = list(self.distributions_charge.order_by('date', 'heure_fin'))

        if distributions:
            # La dernière distribution chronologiquement
            last_dist = distributions[-1]

            # Si la date de la dernière distribution est passée (avant aujourd'hui)
            if last_dist.date < today:
                return True

            # Si la dernière distribution est aujourd'hui, vérifier si son heure de fin est passée
            if last_dist.date == today and last_dist.heure_fin is not None:
                if current_time > last_dist.heure_fin:
                    return True

            # La dernière distribution est dans le futur ou aujourd'hui mais pas encore terminée
            return False

        # Pas de distributions → utiliser date_fin_planifiee
        return self.date_fin_planifiee < today

    def mark_as_expired(self):
        """
        Marque la tâche comme expirée.
        Appelé automatiquement quand l'heure de fin est dépassée sans démarrage.

        Returns:
            bool: True si le statut a été changé
        """
        if self.is_expired and self.statut in ('PLANIFIEE', 'EN_RETARD'):
            self.statut = 'EXPIREE'
            self.save(update_fields=['statut'])
            return True
        return False

    def save(self, *args, **kwargs):
        # Save first to get an ID if it's new
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Now generate reference if it's empty
        if not self.reference:
            # Organisation (Client)
            org_code = "UNK"
            if self.id_structure_client:
                org_code = (self.id_structure_client.nom[:3].upper() 
                           if self.id_structure_client.nom else "UNK")
            elif self.id_client and self.id_client.structure:
                org_code = (self.id_client.structure.nom[:3].upper() 
                           if self.id_client.structure.nom else "UNK")
            
            # Site (via premier objet ou vide)
            site_code = "GEN" # GEN = General
            first_obj = self.objets.first()
            if first_obj and first_obj.site:
                site_code = (first_obj.site.nom_site[:3].upper() 
                            if first_obj.site.nom_site else "UNK")
            
            # Type de tâche
            type_code = "UNK"
            if self.id_type_tache:
                type_code = (self.id_type_tache.nom_tache[:3].upper() 
                            if self.id_type_tache.nom_tache else "UNK")
            
            self.reference = f"{org_code}-{site_code}-{type_code}-{self.id}"
            # Save the reference
            super().save(update_fields=['reference'])
            
            # Trigger updates for distributions if we just got a first reference? 
            # (Usually distributions are created after task save)

    def delete(self, using=None, keep_parents=False):
        """Soft delete implementation"""
        self.deleted_at = timezone.now()
        self.save()


class DistributionCharge(models.Model):
    """
    ✅ Distribution journalière de la charge pour tâches multi-jours.

    Permet de planifier précisément combien d'heures sont allouées chaque jour
    pour une tâche qui s'étend sur plusieurs jours.

    Exemple:
        Tâche "Élagage Parc" du 15/01 au 17/01, charge totale 6h:
        - 15/01 (Lun): 2.0h planifiées
        - 16/01 (Mar): 3.0h planifiées
        - 17/01 (Mer): 1.0h planifiées

    Avantages:
    - Planification précise par jour
    - Calcul correct de la disponibilité des équipes
    - Analyses statistiques justes (1 tâche = 1 entrée, pas N occurrences)
    - Suivi de l'avancement jour par jour
    """

    tache = models.ForeignKey(
        Tache,
        on_delete=models.CASCADE,
        related_name='distributions_charge',
        verbose_name="Tâche"
    )

    date = models.DateField(
        verbose_name="Date",
        help_text="Jour de travail"
    )

    heures_planifiees = models.FloatField(
        verbose_name="Heures planifiées",
        help_text="Nombre d'heures prévues ce jour"
    )

    heures_reelles = models.FloatField(
        null=True,
        blank=True,
        verbose_name="Heures réelles",
        help_text="Heures réellement travaillées (rempli après exécution)"
    )

    commentaire = models.TextField(
        blank=True,
        verbose_name="Commentaire",
        help_text="Notes pour ce jour (équipe réduite, météo, etc.)"
    )

    heure_debut = models.TimeField(
        null=True,
        blank=True,
        verbose_name="Heure de début",
        help_text="Heure de début de travail prévue (ex: 08:00)"
    )

    heure_fin = models.TimeField(
        null=True,
        blank=True,
        verbose_name="Heure de fin",
        help_text="Heure de fin de travail prévue (ex: 17:00)"
    )

    # ✅ NOUVEAU: Statut de la distribution
    STATUT_CHOICES = [
        ('NON_REALISEE', 'Non Réalisée'),
        ('REALISEE', 'Réalisée'),
    ]

    status = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default='NON_REALISEE',
        verbose_name="Statut",
        help_text="État de la distribution de charge"
    )

    reference = models.CharField(max_length=120, unique=True, blank=True, null=True, db_index=True, verbose_name="Référence")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Distribution de charge"
        verbose_name_plural = "Distributions de charge"
        unique_together = ['tache', 'date']
        ordering = ['date']
        indexes = [
            models.Index(fields=['tache', 'date']),
        ]

    def __str__(self):
        return f"{self.reference or self.id}"

    def save(self, *args, **kwargs):
        # 1. Si nouvel objet (pas d'ID), on sauvegarde d'abord pour obtenir un ID
        is_new = self._state.adding or not self.id
        if is_new:
            super().save(*args, **kwargs)
            # On passe en mode update
            kwargs['force_insert'] = False

        # 2. Générer la référence si elle manque (maintenant on a un ID)
        if not self.reference:
            # Format: {TACHE_REF}-D{ID}
            # S'assurer que la tâche a une référence
            if not self.tache.reference:
                self.tache.save() 
            
            # Utiliser l'ID unique pour la référence
            self.reference = f"{self.tache.reference}-D{self.id}"
            
            # Sauvegarder la nouvelle référence
            # Si c'était un nouvel objet, on a déjà tout sauvegardé, on update juste la ref
            if is_new:
                super().save(update_fields=['reference'])
                return

        # 3. Si ce n'était pas un nouvel objet, on sauvegarde normalement
        # (Si c'était nouveau, on a déjà return plus haut)
        if not is_new:
            super().save(*args, **kwargs)

    def calculer_heures_depuis_horaires(self):
        """
        Calcule les heures planifiées à partir de heure_debut et heure_fin.
        Retourne le nombre d'heures (float) ou None si les heures ne sont pas définies.
        
        """
        if self.heure_debut and self.heure_fin:
            # Convertir time en datetime pour calculer la différence
            from datetime import datetime, timedelta
            debut = datetime.combine(datetime.today(), self.heure_debut)
            fin = datetime.combine(datetime.today(), self.heure_fin)

            # Calculer la différence en heures
            diff = fin - debut
            heures = diff.total_seconds() / 3600

            return round(heures, 2) if heures > 0 else 0
        return None

    def clean(self):
        """Validation métier"""
        super().clean()

        # Vérifier que la date est dans la période de la tâche
        if self.tache_id and self.date:
            tache = self.tache
            if tache.date_debut_planifiee and tache.date_fin_planifiee:
                # Les dates sont déjà des DateField (datetime.date)
                date_debut = tache.date_debut_planifiee
                date_fin = tache.date_fin_planifiee

                if self.date < date_debut or self.date > date_fin:
                    raise ValidationError({
                        'date': f"Date {self.date.strftime('%d/%m/%Y')} hors période "
                                f"({date_debut.strftime('%d/%m/%Y')} - {date_fin.strftime('%d/%m/%Y')})"
                    })

        # Calcul automatique des heures_planifiees si heure_debut et heure_fin sont définies
        if self.heure_debut and self.heure_fin:
            heures_calculees = self.calculer_heures_depuis_horaires()
            if heures_calculees is not None:
                self.heures_planifiees = heures_calculees

        # Vérifier que les heures sont positives
        if self.heures_planifiees is not None and self.heures_planifiees < 0:
            raise ValidationError({
                'heures_planifiees': "Les heures planifiées doivent être positives"
            })

        if self.heures_reelles is not None and self.heures_reelles < 0:
            raise ValidationError({
                'heures_reelles': "Les heures réelles doivent être positives"
            })

        # Vérifier que heure_fin > heure_debut
        if self.heure_debut and self.heure_fin :
            if self.heure_fin <= self.heure_debut:
                raise ValidationError({
                    'heure_fin': "L'heure de fin doit être postérieure à l'heure de début"
                })


class RatioProductivite(models.Model):
    """    
    Matrice de productivité: ratio par combinaison (TypeTache, type_objet).
    Le ratio représente le nombre d'unités traitables par heure.
    """
    UNITE_CHOICES = [
        ('m2', 'Mètres carrés'),
        ('ml', 'Mètres linéaires'),
        ('unite', 'Unité'),
    ]

    id_type_tache = models.ForeignKey(
        TypeTache,
        on_delete=models.CASCADE,
        related_name='ratios_productivite',
        verbose_name="Type de tâche"
    )
    type_objet = models.CharField(
        max_length=50,
        verbose_name="Type d'objet",
        help_text="Nom de la classe (Arbre, Gazon, Palmier, etc.)"
    )
    unite_mesure = models.CharField(
        max_length=10,
        choices=UNITE_CHOICES,
        default='unite',
        verbose_name="Unité de mesure"
    )
    ratio = models.FloatField(
        verbose_name="Ratio (unités/heure)",
        help_text="Nombre d'unités traitables par heure"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Description/Notes"
    )
    actif = models.BooleanField(
        default=True,
        verbose_name="Actif"
    )

    class Meta:
        verbose_name = "Ratio de productivité"
        verbose_name_plural = "Ratios de productivité"
        unique_together = ['id_type_tache', 'type_objet']
        ordering = ['id_type_tache', 'type_objet']

    def __str__(self):
        return f"{self.id_type_tache.nom_tache} - {self.type_objet}: {self.ratio} {self.unite_mesure}/h"


class ParticipationTache(models.Model):
    ROLE_CHOICES = [
        ('CHEF', 'Chef d\'équipe'),
        ('MEMBRE', 'Membre'),
    ]

    id_tache = models.ForeignKey(Tache, on_delete=models.CASCADE, related_name='participations')
    id_operateur = models.ForeignKey(Operateur, on_delete=models.CASCADE, related_name='participations_tache')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='MEMBRE', verbose_name="Rôle")
    heures_travaillees = models.FloatField(default=0.0, verbose_name="Heures travaillées")
    realisation = models.TextField(blank=True, verbose_name="Réalisation")
    
    class Meta:
        verbose_name = "Participation tâche"
        verbose_name_plural = "Participations tâches"
        unique_together = ['id_tache', 'id_operateur']
        
    def __str__(self):
        return f"{self.id_operateur} - {self.id_tache} ({self.get_role_display()})"
