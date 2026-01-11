"""
Script pour ajouter les nouveaux types de tâches avec leurs compétences requises.

Usage:
    python add_new_task_types.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')
django.setup()

from api_planification.models import TypeTache
from api_users.models import Competence


def main():
    print("🌱 Ajout des nouveaux types de tâches...")
    print("=" * 60)

    # Format des nouveaux types de tâches
    # Selon le tableau: Nom | Rendement | Compétences (9 colonnes: Arbres, Palmiers, Arbustes, Vivaces, Cactus, Graminées, Arbustes, Gazon, Hydraulique)
    nouveaux_types = [
        {
            'nom_tache': 'Topdressing gazon',
            'symbole': 'TDG',
            'description': 'Application de compost ou sable fin sur le gazon',
            'productivite_theorique': 40,
            'unite_productivite': 'm2',
            'competences': ['Gazon']  # Colonne 8
        },
        {
            'nom_tache': 'Compactage du gazon',
            'symbole': 'CPG',
            'description': 'Compactage et raffermissement de la surface du gazon',
            'productivite_theorique': 500,
            'unite_productivite': 'm2',
            'competences': ['Gazon']  # Colonne 8
        },
        {
            'nom_tache': 'Scarification',
            'symbole': 'SCA',
            'description': 'Élimination du feutre et de la mousse des gazons',
            'productivite_theorique': 75,
            'unite_productivite': 'm2',
            'competences': ['Arbustes', 'Gazon']  # Colonnes 7 et 8
        },
        {
            'nom_tache': 'Tonte',
            'symbole': 'TON',
            'description': 'Coupe régulière du gazon',
            'productivite_theorique': 1000,
            'unite_productivite': 'm2',
            'competences': ['Arbustes', 'Gazon']  # Colonnes 7 et 8
        },
        {
            'nom_tache': 'Ramassage des déchets verts',
            'symbole': 'RAM',
            'description': 'Collecte et évacuation des déchets végétaux',
            'productivite_theorique': 56,
            'unite_productivite': 'm2',
            'competences': ['Arbres', 'Palmiers', 'Arbustes', 'Vivaces', 'Cactus', 'Graminées', 'Gazon']  # Colonnes 1-8
        },
        {
            'nom_tache': 'Sursemis',
            'symbole': 'SUR',
            'description': 'Semis complémentaire pour régénérer le gazon',
            'productivite_theorique': 2100,
            'unite_productivite': 'm2',
            'competences': ['Gazon']  # Colonne 8
        },
        {
            'nom_tache': 'Désherbage',
            'symbole': 'DES',
            'description': 'Élimination des mauvaises herbes',
            'productivite_theorique': 15,
            'unite_productivite': 'm2',
            'competences': ['Arbres', 'Palmiers', 'Arbustes', 'Vivaces', 'Cactus', 'Graminées', 'Gazon']  # Colonnes 1-8
        },
        {
            'nom_tache': 'Nivellement des bordures',
            'symbole': 'NBR',
            'description': 'Ajustement et alignement des bordures',
            'productivite_theorique': 18,
            'unite_productivite': 'ml',
            'competences': ['Arbres', 'Palmiers', 'Arbustes', 'Vivaces', 'Cactus', 'Graminées', 'Gazon']  # Colonnes 1-8
        },
        {
            'nom_tache': 'Arrachage des arbres morts',
            'symbole': 'AAM',
            'description': 'Extraction des arbres morts ou malades',
            'productivite_theorique': 1,
            'unite_productivite': 'arbres',
            'competences': ['Arbres', 'Palmiers', 'Arbustes', 'Vivaces', 'Cactus', 'Graminées', 'Gazon']  # Colonnes 1-8
        },
        {
            'nom_tache': 'Arrachage des palmiers morts',
            'symbole': 'APM',
            'description': 'Extraction des palmiers morts ou malades',
            'productivite_theorique': 0.8,
            'unite_productivite': 'arbres',
            'competences': ['Arbres', 'Palmiers', 'Arbustes', 'Vivaces', 'Cactus', 'Graminées', 'Gazon']  # Colonnes 1-8
        },
        {
            'nom_tache': 'Arrachage des arbustes morts',
            'symbole': 'ABM',
            'description': 'Extraction des arbustes morts ou malades',
            'productivite_theorique': 5,
            'unite_productivite': 'arbres',
            'competences': ['Arbres', 'Palmiers', 'Arbustes', 'Vivaces', 'Cactus', 'Graminées', 'Gazon']  # Colonnes 1-8
        },
        {
            'nom_tache': 'Arrachage des graminées mortes',
            'symbole': 'AGM',
            'description': 'Extraction des graminées mortes',
            'productivite_theorique': 20,
            'unite_productivite': 'm2',
            'competences': ['Arbres', 'Palmiers', 'Arbustes', 'Vivaces', 'Cactus', 'Graminées', 'Gazon']  # Colonnes 1-8
        },
        {
            'nom_tache': 'Arrachage des cactus morts',
            'symbole': 'ACM',
            'description': 'Extraction des cactus morts',
            'productivite_theorique': 2,
            'unite_productivite': 'unite',
            'competences': ['Arbres', 'Palmiers', 'Arbustes', 'Vivaces', 'Cactus', 'Graminées', 'Gazon']  # Colonnes 1-8
        },
        {
            'nom_tache': 'Arrachage des vivaces mortes',
            'symbole': 'AVM',
            'description': 'Extraction des vivaces mortes',
            'productivite_theorique': 8,
            'unite_productivite': 'unite',
            'competences': ['Arbres', 'Palmiers', 'Arbustes', 'Vivaces', 'Cactus', 'Graminées', 'Gazon']  # Colonnes 1-8
        },
        {
            'nom_tache': 'Réparation des fuites',
            'symbole': 'RFU',
            'description': 'Réparation des fuites du système d\'irrigation',
            'productivite_theorique': None,
            'unite_productivite': 'unite',
            'competences': ['Hydraulique']  # Colonne 9
        },
    ]

    created_count = 0
    updated_count = 0
    errors = []

    for data in nouveaux_types:
        try:
            competences_names = data.pop('competences')

            # Créer ou mettre à jour le type de tâche
            type_tache, created = TypeTache.objects.update_or_create(
                nom_tache=data['nom_tache'],
                defaults=data
            )

            if created:
                created_count += 1
                print(f"✅ Type créé: {type_tache.nom_tache}")
            else:
                updated_count += 1
                print(f"♻️  Type mis à jour: {type_tache.nom_tache}")

            # Note: Si TypeTache a un champ ManyToMany pour les compétences,
            # il faudra le décommenter et adapter le code ci-dessous:
            """
            # Ajouter les compétences requises
            competences = []
            for nom_comp in competences_names:
                try:
                    comp = Competence.objects.get(nom_competence__iexact=nom_comp)
                    competences.append(comp)
                except Competence.DoesNotExist:
                    print(f"  ⚠️  Compétence '{nom_comp}' non trouvée")

            if hasattr(type_tache, 'competences_requises'):
                type_tache.competences_requises.set(competences)
                print(f"  🎯 Compétences assignées: {', '.join(competences_names)}")
            """

        except Exception as e:
            errors.append(f"❌ Erreur pour '{data.get('nom_tache', 'UNKNOWN')}': {e}")
            print(errors[-1])

    print()
    print("=" * 60)
    print(f"✨ Peuplement terminé:")
    print(f"   - {created_count} types créés")
    print(f"   - {updated_count} types mis à jour")

    if errors:
        print(f"   - {len(errors)} erreurs")
        for error in errors:
            print(f"     {error}")

    print()
    print("⚠️  IMPORTANT:")
    print("   Le modèle TypeTache n'a pas encore de champ pour les compétences.")
    print("   Les compétences requises sont documentées dans le code mais non assignées.")
    print("   Pour activer cette fonctionnalité, il faut:")
    print("   1. Ajouter un champ ManyToManyField 'competences_requises' au modèle TypeTache")
    print("   2. Exécuter les migrations Django")
    print("   3. Décommenter le code d'assignation des compétences dans ce script")


if __name__ == '__main__':
    main()
