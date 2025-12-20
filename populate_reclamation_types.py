import os
import django

# Configuration de l'environnement Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')
django.setup()

from api_reclamations.models import TypeReclamation

def populate_types():
    data = [
        # (Nom, Code, Catégorie)
        ("Fuite d'eau", "FUITE_EAU", "URGENCE"),
        ("Equipement en panne", "EQUIPEMENT_PANNE", "URGENCE"),
        ("Végétation arrachée", "VEGETATION_ARRACHEE", "QUALITE"),
        ("Zone dégradée", "ZONE_DEGRADEE", "QUALITE"),
        ("Manque entretien", "MANQUE_ENTRETIEN", "QUALITE"),
        ("Zone à prioriser", "ZONE_PRIORITE", "AUTRE"),
        ("Evènement planifié", "EVENEMENT_PLANIFIE", "PLANNING"),
        ("Manque matériel", "MANQUE_MATERIEL", "RESSOURCES"),
        ("Manque effectif", "MANQUE_EFFECTIF", "RESSOURCES"),
        ("Maladie", "MALADIE", "QUALITE"),
        ("Ravageur", "RAVAGEUR", "QUALITE"),
        ("Plantes mortes", "PLANTES_MORTES", "QUALITE"),
        ("Sol compacté", "SOL_COMPACTE", "QUALITE"),
        ("Accumulation de déchets verts", "DECHETS_VERTS", "QUALITE"),
        ("Retard des équipes", "RETARD_EQUIPES", "PLANNING"),
        ("Planning non respecté", "PLANNING_NON_RESPECTE", "PLANNING"),
    ]

    print(f"Début du remplissage de TypeReclamation...")
    count = 0
    
    for nom, code, cat in data:
        obj, created = TypeReclamation.objects.get_or_create(
            code_reclamation=code,
            defaults={
                'nom_reclamation': nom,
                'categorie': cat,
                'actif': True
            }
        )
        if created:
            print(f" [OK] Créé : {nom}")
            count += 1
        else:
            print(f" [PASS] Existe déjà : {nom}")

    print(f"Terminé. {count} nouveaux types ajoutés.")

if __name__ == "__main__":
    populate_types()
