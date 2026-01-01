from django.contrib.gis.db import models
from django.utils import timezone
import uuid


# ==============================================================================
# 2.2 HIÉRARCHIE SPATIALE
# ==============================================================================

class Site(models.Model):
    """ Entité 5 : SITE - Représente un site d'intervention global """
    nom_site = models.CharField(max_length=255, verbose_name="Nom du site")
    adresse = models.TextField(verbose_name="Adresse complète", blank=True, null=True)
    superficie_totale = models.FloatField(verbose_name="Surface totale m²", blank=True, null=True)
    code_site = models.CharField(max_length=50, unique=True, verbose_name="Code unique", blank=True)

    # Structure cliente propriétaire du site
    structure_client = models.ForeignKey(
        'api_users.StructureClient',
        on_delete=models.CASCADE,
        related_name='sites',
        verbose_name="Structure cliente",
        null=True,
        blank=True,
        help_text="Structure/organisation propriétaire du site"
    )

    # LEGACY: Ancien champ client (à supprimer après migration)
    client = models.ForeignKey(
        'api_users.Client',
        on_delete=models.CASCADE,
        related_name='sites_legacy',
        verbose_name="[LEGACY] Client propriétaire",
        null=True,
        blank=True
    )

    # Superviseur affecté au site (gestion opérationnelle)
    superviseur = models.ForeignKey(
        'api_users.Superviseur',
        on_delete=models.SET_NULL,
        related_name='sites_affectes',
        verbose_name="Superviseur affecté",
        null=True,
        blank=True,
        help_text="Superviseur responsable de la gestion de ce site"
    )

    # Dates de contrat
    date_debut_contrat = models.DateField(blank=True, null=True)
    date_fin_contrat = models.DateField(blank=True, null=True)
    actif = models.BooleanField(default=True, verbose_name="Site actif")

    # Géométrie
    geometrie_emprise = models.PolygonField(srid=4326, verbose_name="Délimitation (Polygon)")
    centroid = models.PointField(srid=4326, blank=True, null=True, verbose_name="Point central")

    def save(self, *args, **kwargs):
        # Auto-generate code_site if not provided
        if not self.code_site:
            year = timezone.now().year
            # Generate a unique code: SITE-YYYY-XXXX
            short_uuid = uuid.uuid4().hex[:4].upper()
            self.code_site = f"SITE-{year}-{short_uuid}"
            # Ensure uniqueness
            while Site.objects.filter(code_site=self.code_site).exists():
                short_uuid = uuid.uuid4().hex[:4].upper()
                self.code_site = f"SITE-{year}-{short_uuid}"

        # Auto-calculate centroid from geometrie_emprise if not provided
        if self.geometrie_emprise and not self.centroid:
            self.centroid = self.geometrie_emprise.centroid

        super().save(*args, **kwargs)

    def __str__(self):
        return self.nom_site


class SousSite(models.Model):
    """ Entité 6 : SOUS-SITE - Représente une villa/unité """
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='sous_sites')
    nom = models.CharField(max_length=255, verbose_name="Nom de la villa/unité", default="Unit")
    geometrie = models.PointField(srid=4326, verbose_name="Localisation")

    def __str__(self):
        return f"{self.nom} ({self.site.nom_site})"


# ==============================================================================
# CLASSE MÈRE CONCRÈTE (Polymorphisme)
# ==============================================================================

ETAT_CHOICES = [
    ('bon', 'Bon état'),
    ('moyen', 'État moyen'),
    ('mauvais', 'Mauvais état'),
    ('critique', 'État critique'),
]


class Objet(models.Model):
    """
    Classe Mère CONCRÈTE (crée une table 'api_objet' en base de données).

    Permet le polymorphisme : une Tache peut référencer n'importe quel type
    d'objet (Arbre, Gazon, Puit, etc.) via une seule relation ManyToManyField(Objet).

    Les 15 types enfants (Arbre, Gazon, Palmier, etc.) héritent de cette classe
    et créent leurs propres tables avec un lien vers api_objet.
    """
    site = models.ForeignKey(Site, on_delete=models.CASCADE)
    sous_site = models.ForeignKey(SousSite, on_delete=models.SET_NULL, null=True, blank=True)
    etat = models.CharField(
        max_length=20,
        choices=ETAT_CHOICES,
        default='bon',
        verbose_name="État de l'objet",
        db_index=True
    )

    ETAT_CHOICES = [
        ('bon', 'Bon'),
        ('moyen', 'Moyen'),
        ('mauvais', 'Mauvais'),
        ('critique', 'Critique'),
    ]
    etat = models.CharField(max_length=50, choices=ETAT_CHOICES, default='bon', verbose_name="État")

    def get_type_reel(self):
        """
        Retourne l'instance enfant réelle (Arbre, Gazon, Puit, etc.).

        Returns:
            Instance du type enfant ou None si pas trouvé

        Example:
            >>> objet = Objet.objects.get(id=1)
            >>> arbre = objet.get_type_reel()
            >>> print(arbre.nom)  # "Palmier Phoenix"
        """
        types = [
            'arbre', 'gazon', 'palmier', 'arbuste', 'vivace', 'cactus', 'graminee',
            'puit', 'pompe', 'vanne', 'clapet', 'canalisation', 'aspersion', 'goutte', 'ballon'
        ]
        for type_name in types:
            if hasattr(self, type_name):
                return getattr(self, type_name)
        return None

    def get_nom_type(self):
        """
        Retourne le nom de la classe enfant ('Arbre', 'Gazon', 'Puit', etc.).

        Returns:
            str: Nom de la classe ou 'Objet' si pas de type enfant
        """
        objet_reel = self.get_type_reel()
        if objet_reel:
            return objet_reel.__class__.__name__
        return 'Objet'

    def get_geometry(self):
        """
        Retourne la géométrie de l'objet enfant.

        Returns:
            GEOSGeometry: Point, Polygon ou LineString selon le type
        """
        objet_reel = self.get_type_reel()
        if objet_reel and hasattr(objet_reel, 'geometry'):
            return objet_reel.geometry
        return None

    def __str__(self):
        """Représentation textuelle de l'objet."""
        objet_reel = self.get_type_reel()
        if objet_reel and hasattr(objet_reel, 'nom'):
            return f"{self.get_nom_type()} - {objet_reel.nom}"
        elif objet_reel and hasattr(objet_reel, 'marque'):
            return f"{self.get_nom_type()} - {objet_reel.marque}"
        return f"Objet #{self.pk}"


# ==============================================================================
# LES 15 TABLES PHYSIQUES (Avec géométrie stricte pour QGIS)
# ==============================================================================

TAILLE_CHOICES = [
    ('Petit', 'Petit'),
    ('Moyen', 'Moyen'),
    ('Grand', 'Grand')
]

# --- Végétaux ---

class Arbre(Objet):
    """ Table physique : api_tree """
    nom = models.CharField(max_length=255, verbose_name="Nom")
    famille = models.CharField(max_length=255, blank=True, null=True, verbose_name="Famille", db_index=True)
    observation = models.TextField(blank=True, null=True)
    last_intervention_date = models.DateField(blank=True, null=True, db_index=True)
    taille = models.CharField(max_length=50, choices=TAILLE_CHOICES, blank=True, null=True, db_index=True)
    symbole = models.CharField(max_length=255, blank=True, null=True)

    # Géométrie STRICTE : Point
    geometry = models.PointField(srid=4326)


class Gazon(Objet):
    """ Table physique : api_lawnarea """
    nom = models.CharField(max_length=255, verbose_name="Nom")
    famille = models.CharField(max_length=255, blank=True, null=True, verbose_name="Famille", db_index=True)
    observation = models.TextField(blank=True, null=True)
    last_intervention_date = models.DateField(blank=True, null=True, db_index=True)
    area_sqm = models.FloatField(blank=True, null=True, verbose_name="Surface m²", db_index=True)

    # Géométrie STRICTE : Polygone
    geometry = models.PolygonField(srid=4326)


class Palmier(Objet):
    nom = models.CharField(max_length=255, verbose_name="Nom")
    famille = models.CharField(max_length=255, blank=True, null=True, verbose_name="Famille", db_index=True)
    observation = models.TextField(blank=True, null=True)
    last_intervention_date = models.DateField(blank=True, null=True, db_index=True)
    taille = models.CharField(max_length=50, choices=TAILLE_CHOICES, blank=True, null=True, db_index=True)
    symbole = models.CharField(max_length=255, blank=True, null=True)
    geometry = models.PointField(srid=4326)


class Arbuste(Objet):
    nom = models.CharField(max_length=255, verbose_name="Nom")
    famille = models.CharField(max_length=255, blank=True, null=True, verbose_name="Famille")
    observation = models.TextField(blank=True, null=True)
    last_intervention_date = models.DateField(blank=True, null=True)
    densite = models.FloatField(blank=True, null=True)
    symbole = models.CharField(max_length=255, blank=True, null=True)
    geometry = models.PolygonField(srid=4326)


class Vivace(Objet):
    nom = models.CharField(max_length=255, verbose_name="Nom")
    famille = models.CharField(max_length=255, blank=True, null=True, verbose_name="Famille")
    observation = models.TextField(blank=True, null=True)
    last_intervention_date = models.DateField(blank=True, null=True)
    densite = models.FloatField(blank=True, null=True)
    geometry = models.PolygonField(srid=4326)


class Cactus(Objet):
    nom = models.CharField(max_length=255, verbose_name="Nom")
    famille = models.CharField(max_length=255, blank=True, null=True, verbose_name="Famille")
    observation = models.TextField(blank=True, null=True)
    last_intervention_date = models.DateField(blank=True, null=True)
    densite = models.FloatField(blank=True, null=True)
    geometry = models.PolygonField(srid=4326)


class Graminee(Objet):
    nom = models.CharField(max_length=255, verbose_name="Nom")
    famille = models.CharField(max_length=255, blank=True, null=True, verbose_name="Famille")
    observation = models.TextField(blank=True, null=True)
    last_intervention_date = models.DateField(blank=True, null=True)
    densite = models.FloatField(blank=True, null=True)
    symbole = models.CharField(max_length=255, blank=True, null=True)
    geometry = models.PolygonField(srid=4326)


# --- Hydraulique ---

class Puit(Objet):
    nom = models.CharField(max_length=255, verbose_name="Nom")
    observation = models.TextField(blank=True, null=True)
    last_intervention_date = models.DateField(blank=True, null=True, db_index=True)
    profondeur = models.FloatField(blank=True, null=True, db_index=True)
    diametre = models.FloatField(blank=True, null=True, db_index=True)
    niveau_statique = models.FloatField(blank=True, null=True)
    niveau_dynamique = models.FloatField(blank=True, null=True)
    symbole = models.CharField(max_length=255, blank=True, null=True)
    geometry = models.PointField(srid=4326)


class Pompe(Objet):
    nom = models.CharField(max_length=255, verbose_name="Nom")
    observation = models.TextField(blank=True, null=True)
    last_intervention_date = models.DateField(blank=True, null=True)
    type = models.CharField(max_length=100, blank=True, null=True)
    diametre = models.FloatField(blank=True, null=True)
    puissance = models.FloatField(blank=True, null=True)
    debit = models.FloatField(blank=True, null=True)
    symbole = models.CharField(max_length=255, blank=True, null=True)
    geometry = models.PointField(srid=4326)


class Vanne(Objet):
    marque = models.CharField(max_length=100, blank=True, null=True)
    type = models.CharField(max_length=100, blank=True, null=True)
    diametre = models.FloatField(blank=True, null=True)
    materiau = models.CharField(max_length=100, blank=True, null=True)
    pression = models.FloatField(blank=True, null=True)
    symbole = models.CharField(max_length=255, blank=True, null=True)
    observation = models.TextField(blank=True, null=True)
    geometry = models.PointField(srid=4326)


class Clapet(Objet):
    marque = models.CharField(max_length=100, blank=True, null=True)
    type = models.CharField(max_length=100, blank=True, null=True)
    diametre = models.FloatField(blank=True, null=True)
    materiau = models.CharField(max_length=100, blank=True, null=True)
    pression = models.FloatField(blank=True, null=True)
    symbole = models.CharField(max_length=255, blank=True, null=True)
    observation = models.TextField(blank=True, null=True)
    geometry = models.PointField(srid=4326)


class Canalisation(Objet):
    marque = models.CharField(max_length=100, blank=True, null=True)
    type = models.CharField(max_length=100, blank=True, null=True)
    diametre = models.FloatField(blank=True, null=True)
    materiau = models.CharField(max_length=100, blank=True, null=True)
    pression = models.FloatField(blank=True, null=True)
    symbole = models.CharField(max_length=255, blank=True, null=True)
    observation = models.TextField(blank=True, null=True)
    # Ligne pour les canalisations
    geometry = models.LineStringField(srid=4326)


class Aspersion(Objet):
    marque = models.CharField(max_length=100, blank=True, null=True)
    type = models.CharField(max_length=100, blank=True, null=True)
    diametre = models.FloatField(blank=True, null=True)
    materiau = models.CharField(max_length=100, blank=True, null=True)
    pression = models.FloatField(blank=True, null=True)
    symbole = models.CharField(max_length=255, blank=True, null=True)
    observation = models.TextField(blank=True, null=True)
    geometry = models.LineStringField(srid=4326)


class Goutte(Objet):
    type = models.CharField(max_length=100, blank=True, null=True)
    diametre = models.FloatField(blank=True, null=True)
    materiau = models.CharField(max_length=100, blank=True, null=True)
    pression = models.FloatField(blank=True, null=True)
    symbole = models.CharField(max_length=255, blank=True, null=True)
    observation = models.TextField(blank=True, null=True)
    # Goutte à goutte est souvent une ligne
    geometry = models.LineStringField(srid=4326)


class Ballon(Objet):
    marque = models.CharField(max_length=100, blank=True, null=True)
    pression = models.FloatField(blank=True, null=True)
    volume = models.FloatField(blank=True, null=True)
    materiau = models.CharField(max_length=100, blank=True, null=True)
    observation = models.TextField(blank=True, null=True)
    geometry = models.PointField(srid=4326)