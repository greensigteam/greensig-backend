"""
Script pour nettoyer les données de la base de données GreenSIG
Usage: python clear_database.py
"""

import os
import sys
import django
from pathlib import Path

# Configuration Django
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')
django.setup()

from api.models import (
    Site, SousSite, Arbre, Gazon, Palmier, Arbuste, Vivace, Cactus, Graminee,
    Puit, Pompe, Vanne, Clapet, Canalisation, Aspersion, Goutte, Ballon
)


def clear_all_data():
    """Supprime toutes les données des tables"""
    print("\n" + "="*60)
    print("NETTOYAGE DE LA BASE DE DONNÉES - GreenSIG")
    print("="*60 + "\n")

    models_to_clear = [
        # Objets (doivent être supprimés avant les sites à cause des FK)
        ('Arbres', Arbre),
        ('Gazons', Gazon),
        ('Palmiers', Palmier),
        ('Arbustes', Arbuste),
        ('Vivaces', Vivace),
        ('Cactus', Cactus),
        ('Graminées', Graminee),
        ('Puits', Puit),
        ('Pompes', Pompe),
        ('Vannes', Vanne),
        ('Clapets', Clapet),
        ('Canalisations', Canalisation),
        ('Aspersions', Aspersion),
        ('Goutte-à-goutte', Goutte),
        ('Ballons', Ballon),
        # Hiérarchie spatiale
        ('Sous-sites', SousSite),
        ('Sites', Site),
    ]

    total_deleted = 0

    for name, model in models_to_clear:
        count = model.objects.count()
        if count > 0:
            model.objects.all().delete()
            print(f"✓ {name:20} : {count} objets supprimés")
            total_deleted += count
        else:
            print(f"  {name:20} : Aucune donnée")

    print("\n" + "="*60)
    print(f"Total : {total_deleted} objets supprimés")
    print("="*60 + "\n")


def main():
    """Fonction principale"""
    print("\n⚠️  ATTENTION : Ce script va SUPPRIMER TOUTES LES DONNÉES de la base.")
    print("Cette action est IRRÉVERSIBLE !")
    response = input("\nÊtes-vous absolument sûr ? (tapez 'SUPPRIMER' pour confirmer) : ")

    if response == 'SUPPRIMER':
        clear_all_data()
        print("✓ Base de données nettoyée avec succès.\n")
    else:
        print("✗ Opération annulée.\n")


if __name__ == '__main__':
    main()
