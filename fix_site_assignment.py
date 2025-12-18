import os
import sys
import django
from django.db.models import F

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')
django.setup()

from api.models import Objet, Site

def fix_site_assignments():
    print("="*60)
    print("CORRECTION DE L'AFFECTATION DES SITES")
    print("="*60)

    # 1. Charger tous les sites
    sites = list(Site.objects.all())
    print(f"Sites disponibles: {len(sites)}")
    for s in sites:
        print(f" - [{s.id}] {s.nom_site}")

    if not sites:
        print("Aucun site trouvé via l'ORM. Abandon.")
        return

    # 2. Parcourir tous les objets
    # On utilise select_related pour éviter trop de requêtes si on accède au site actuel
    # Mais ici on veut juste l'update.
    # On récupère geometry aussi.
    
    # Note: Objet.objects.all() return instances of Objet.
    # The geometry is NOT on Objet model directly in the python class methods shown previously,
    # BUT looking at `models.py`, `Objet` has `get_geometry()`.
    # However, for spatial queries, we usually need the geometry field.
    # The geometry field is on the CHILD classes (Arbre, Puit, etc.).
    # Base `Objet` does NOT have a geometry field in the provided schema (it only has get_geometry helper).
    
    # PROBLEM: We cannot filter `Objet.objects.filter(geometry__within=site.geom)` if Objet has no geometry field.
    # We must iterate over children OR use the `get_geometry()` and check in python (slower but safer given polymorphism).
    
    # Given database size might be small (<10k), Python-side check is acceptable.
    # Optimization: Iterate over each child model class? No, `Objet.objects.all()` is better to cover everything.
    
    print("\nAnalyse spatiale en cours...")
    
    updated_count = 0
    errors_count = 0
    unchanged_count = 0
    
    # Fetch all objects
    all_objets = Objet.objects.all()
    total = all_objets.count()
    print(f"Total objets à vérifier: {total}")
    
    for i, obj in enumerate(all_objets, 1):
        if i % 100 == 0:
            print(f"Traitement... {i}/{total}")
            
        try:
            geom = obj.get_geometry()
            if not geom:
                # S'il n'a pas de géométrie (ex: objet abstrait ou erreur), on skip
                # print(f"Objet {obj.id} sans géométrie. Skip.")
                continue
                
            current_site_id = obj.site_id
            
            # Trouver le site qui contient ce point
            found_site = None
            
            # Vérification spatiale simple
            for site in sites:
                if site.geometrie_emprise and site.geometrie_emprise.contains(geom):
                    found_site = site
                    break
            
            if found_site:
                if found_site.id != current_site_id:
                    obj.site = found_site
                    obj.save()
                    updated_count += 1
                    # print(f" -> Objet {obj.id} déplacé de Site {current_site_id} vers {found_site.nom_site}")
                else:
                    unchanged_count += 1
            else:
                # L'objet est en dehors de tous les sites
                # Optionnel: On pourrait chercher le plus proche ? Pour l'instant on laisse tel quel.
                # print(f"Objet {obj.id} hors de tous les sites connus.")
                pass
                
        except Exception as e:
            print(f"Erreur sur objet {obj.id}: {e}")
            errors_count += 1

    print("\n" + "="*60)
    print("RÉSULTAT")
    print("="*60)
    print(f"Objets réalignés: {updated_count}")
    print(f"Objets inchangés: {unchanged_count}")
    print(f"Erreurs:          {errors_count}")
    print("="*60)

if __name__ == "__main__":
    fix_site_assignments()
