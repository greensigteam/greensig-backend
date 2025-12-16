"""
Modèles pour le module Suivi des Tâches
Gère les produits, consommations et photos liées aux interventions
"""
from django.db import models
from django.core.exceptions import ValidationError
from api_planification.models import Tache
from api.models import Objet


# ==============================================================================
# MODELE PRODUIT
# ==============================================================================

class Produit(models.Model):
    """
    Représente un produit phytosanitaire ou engrais utilisé.
    
    Conforme aux exigences réglementaires (homologation, traçabilité).
    """
    nom_produit = models.CharField(
        max_length=255,
        verbose_name="Nom commercial",
        help_text="Nom commercial du produit"
    )
    numero_homologation = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Numéro d'homologation",
        help_text="Numéro d'homologation officiel"
    )
    date_validite = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date de validité",
        help_text="Date limite de validité/homologation"
    )
    cible = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Cible",
        help_text="Exemple: Ver du gazon, mauvaises herbes"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Description"
    )
    actif = models.BooleanField(
        default=True,
        verbose_name="Produit actif",
        help_text="Désactiver si produit retiré du marché"
    )
    date_creation = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création"
    )

    class Meta:
        verbose_name = "Produit"
        verbose_name_plural = "Produits"
        ordering = ['nom_produit']

    def __str__(self):
        return self.nom_produit

    @property
    def est_valide(self):
        """Vérifie si le produit est encore valide."""
        if not self.date_validite:
            return True
        from django.utils import timezone
        return self.date_validite >= timezone.now().date()

    def clean(self):
        """Validation du modèle."""
        if self.date_validite:
            from django.utils import timezone
            if self.date_validite < timezone.now().date():
                raise ValidationError({
                    'date_validite': 'La date de validité ne peut pas être dans le passé.'
                })


# ==============================================================================
# MODELE PRODUIT_MATIERE_ACTIVE
# ==============================================================================

class ProduitMatiereActive(models.Model):
    """
    Matières actives contenues dans un produit.
    
    Un produit peut contenir plusieurs matières actives.
    """
    produit = models.ForeignKey(
        Produit,
        on_delete=models.CASCADE,
        related_name='matieres_actives',
        verbose_name="Produit"
    )
    matiere_active = models.CharField(
        max_length=255,
        verbose_name="Matière active",
        help_text="Nom de la matière active"
    )
    teneur_valeur = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Teneur (valeur)",
        help_text="Valeur numérique de la teneur"
    )
    teneur_unite = models.CharField(
        max_length=20,
        default='%',
        verbose_name="Teneur (unité)",
        help_text="%, g/l, fraction..."
    )
    ordre = models.PositiveIntegerField(
        default=0,
        verbose_name="Ordre d'affichage",
        help_text="Ordre d'affichage si plusieurs matières actives"
    )

    class Meta:
        verbose_name = "Matière active"
        verbose_name_plural = "Matières actives"
        ordering = ['produit', 'ordre', 'matiere_active']
        unique_together = ['produit', 'matiere_active']

    def __str__(self):
        return f"{self.produit.nom_produit} - {self.matiere_active} ({self.teneur_valeur}{self.teneur_unite})"


# ==============================================================================
# MODELE DOSE_PRODUIT
# ==============================================================================

class DoseProduit(models.Model):
    """
    Doses recommandées pour un produit.
    
    Un produit peut avoir plusieurs doses selon le contexte d'utilisation.
    """
    produit = models.ForeignKey(
        Produit,
        on_delete=models.CASCADE,
        related_name='doses',
        verbose_name="Produit"
    )
    dose_valeur = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Dose (valeur)",
        help_text="Valeur numérique de la dose"
    )
    dose_unite_produit = models.CharField(
        max_length=20,
        verbose_name="Unité produit",
        help_text="cc, g, kg, ml, l..."
    )
    dose_unite_support = models.CharField(
        max_length=20,
        verbose_name="Unité support",
        help_text="hl, ha, m²..."
    )
    contexte = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Contexte d'utilisation",
        help_text="Précision sur le contexte (ex: gazon, arbustes)"
    )

    class Meta:
        verbose_name = "Dose produit"
        verbose_name_plural = "Doses produits"
        ordering = ['produit']

    def __str__(self):
        return f"{self.produit.nom_produit} - {self.dose_valeur} {self.dose_unite_produit}/{self.dose_unite_support}"


# ==============================================================================
# MODELE CONSOMMATION_PRODUIT
# ==============================================================================

class ConsommationProduit(models.Model):
    """
    Association entre une tâche et les produits consommés.
    
    Permet de tracer la consommation réelle de produits par intervention.
    """
    tache = models.ForeignKey(
        Tache,
        on_delete=models.CASCADE,
        related_name='consommations_produits',
        verbose_name="Tâche"
    )
    produit = models.ForeignKey(
        Produit,
        on_delete=models.PROTECT,
        related_name='consommations',
        verbose_name="Produit"
    )
    quantite_utilisee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Quantité utilisée",
        help_text="Quantité réellement consommée"
    )
    unite = models.CharField(
        max_length=20,
        verbose_name="Unité de mesure",
        help_text="cc, g, kg, ml, l..."
    )
    date_utilisation = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date d'utilisation"
    )
    commentaire = models.TextField(
        blank=True,
        verbose_name="Commentaire",
        help_text="Observations sur l'utilisation"
    )

    class Meta:
        verbose_name = "Consommation produit"
        verbose_name_plural = "Consommations produits"
        unique_together = ['tache', 'produit']
        ordering = ['tache', 'date_utilisation']

    def __str__(self):
        return f"{self.tache} - {self.produit.nom_produit} ({self.quantite_utilisee} {self.unite})"

    def clean(self):
        """Validation de la consommation."""
        if self.quantite_utilisee <= 0:
            raise ValidationError({
                'quantite_utilisee': 'La quantité doit être supérieure à 0.'
            })


# ==============================================================================
# MODELE PHOTO
# ==============================================================================

class Photo(models.Model):
    """
    Photos liées aux interventions, réclamations ou inventaire.
    
    Permet la traçabilité visuelle des travaux.
    """
    TYPE_PHOTO_CHOICES = [
        ('AVANT', 'Avant intervention'),
        ('APRES', 'Après intervention'),
        ('RECLAMATION', 'Réclamation'),
        ('INVENTAIRE', 'Inventaire'),
    ]

    fichier = models.ImageField(
        upload_to='photos/%Y/%m/%d/',
        verbose_name="Fichier Photo",
        help_text="Fichier image uploadé",
        max_length=500,
        null=True, 
        blank=True
    )
    type_photo = models.CharField(
        max_length=20,
        choices=TYPE_PHOTO_CHOICES,
        verbose_name="Type de photo"
    )
    date_prise = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de prise",
        help_text="Date et heure de la prise de photo"
    )
    
    # Relations optionnelles (une photo peut être liée à une seule entité)
    tache = models.ForeignKey(
        Tache,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='photos',
        verbose_name="Tâche"
    )
    reclamation = models.ForeignKey(
        'api_reclamations.Reclamation',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='photos',
        verbose_name="Réclamation"
    )
    objet = models.ForeignKey(
        Objet,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='photos',
        verbose_name="Objet inventaire"
    )
    
    legende = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Légende",
        help_text="Description de la photo"
    )
    
    # Géolocalisation optionnelle
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name="Latitude"
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name="Longitude"
    )

    class Meta:
        verbose_name = "Photo"
        verbose_name_plural = "Photos"
        ordering = ['-date_prise']

    def __str__(self):
        entity = self.tache or self.objet or "Sans lien"
        return f"Photo {self.get_type_photo_display()} - {entity}"

    def clean(self):
        """Validation: une photo doit être liée à au moins une entité."""
        if not any([self.tache, self.objet]):
            raise ValidationError(
                "Une photo doit être liée à au moins une entité (tâche, réclamation ou objet)."
            )
