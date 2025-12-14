import os
import django
import sys

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')
django.setup()

from api.models import Objet, Site, Arbre

def check_site_data(site_id):
    try:
        site = Site.objects.get(id=site_id)
        print(f"Site found: {site.nom_site} (ID: {site.id})")
    except Site.DoesNotExist:
        print(f"Site with ID {site_id} does not exist!")
        return

    # Check Objets linked to this site
    objets_count = Objet.objects.filter(site_id=site_id).count()
    print(f"Total Objets linked to Site {site_id}: {objets_count}")

    if objets_count == 0:
        print("WARNING: No objects found for this site in the generic 'Objet' table.")
        
        # Check if there are Arbres linked? (should have been inherited)
        # But wait, if Arbre inherits Objet, querying Arbre IS querying Objet.
        # Unless there are Arbres created without Objet parent? (Impossible with MTI)
        
        # Check generic query
        all_sites_with_objects = Objet.objects.values_list('site_id', flat=True).distinct()
        print(f"Sites IDs having objects: {list(all_sites_with_objects)}")
    else:
        # Limit to 5 for preview
        objs = Objet.objects.filter(site_id=site_id)[:5]
        for o in objs:
            print(f" - Object {o.id}: Type={o.get_nom_type()}")

if __name__ == "__main__":
    print("--- Checking Site 1 ---")
    check_site_data(1)
    print("\n--- Checking Site 2 ---")
    check_site_data(2)
