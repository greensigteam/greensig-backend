import os
import sys
import django
import random
from datetime import date

# Configuration de l'environnement Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')
django.setup()

from api_users.models import (
    Operateur, Competence, CompetenceOperateur, NiveauCompetence, CategorieCompetence
)

def seed_competences_and_mastery():
    print("\n🎓 Debut du peuplement des competences et maitrises...")

    # 1. Creer les competences de base si elles n'existent pas
    comps_data = [
        ('TECHNIQUE', [
            'Utilisation de tondeuse',
            'Utilisation de debroussailleuse',
            'Utilisation de tronconneuse',
            'Desherbage manuel et mecanique',
            'Binage des sols',
            'Confection des cuvettes',
            'Taille de nettoyage',
            'Taille de decoration',
            'Arrosage',
            'Elagage de palmiers',
            'Nettoyage general',
        ]),
        ('ORGANISATIONNELLE', [
            'Gestion d\'equipe',
            'Organisation des taches',
            'Supervision et coordination',
            'Respect des procedures',
        ])
    ]
    
    all_comps = []
    for cat, names in comps_data:
        for name in names:
            comp, created = Competence.objects.get_or_create(
                nom_competence=name,
                defaults={'categorie': cat}
            )
            all_comps.append(comp)
            if created:
                print(f"   ✅ Competence creee: {name} ({cat})")

    # 2. Assigner les competences aux operateurs
    niveaux = [NiveauCompetence.DEBUTANT, NiveauCompetence.INTERMEDIAIRE, NiveauCompetence.EXPERT]
    
    operateurs = Operateur.objects.all()
    print(f"\n🔧 Attribution des competences a {operateurs.count()} operateurs...")
    
    count = 0
    for op in operateurs:
        # Chaque operateur recoit 3 a 6 competences techniques aleatoires
        tech_comps = [c for c in all_comps if c.categorie == 'TECHNIQUE']
        assigned = random.sample(tech_comps, random.randint(3, 6))
        
        for comp in assigned:
            _, created = CompetenceOperateur.objects.get_or_create(
                operateur=op,
                competence=comp,
                defaults={
                    'niveau': random.choice(niveaux),
                    'date_acquisition': date(2024, 1, 1)
                }
            )
            if created:
                count += 1
        
        # Si l'operateur a le role de chef d'equipe, on s'assure qu'il a des competences d'organisation
        is_chef = op.utilisateur.roles_utilisateur.filter(role__nom_role='CHEF_EQUIPE').exists()
        if is_chef:
            org_comps = [c for c in all_comps if c.categorie == 'ORGANISATIONNELLE']
            for comp in org_comps:
                _, created = CompetenceOperateur.objects.get_or_create(
                    operateur=op,
                    competence=comp,
                    defaults={
                        'niveau': NiveauCompetence.EXPERT if comp.nom_competence == "Gestion d'equipe" else random.choice(niveaux),
                        'date_acquisition': date(2023, 1, 1)
                    }
                )
                if created:
                    count += 1

    print(f"   ✅ {count} relations de maitrise creees.")

if __name__ == "__main__":
    seed_competences_and_mastery()
    print("\n✨ Peuplement des competences termine!")
