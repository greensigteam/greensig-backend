"""
Script d'audit pour vérifier la configuration de la planification.
Vérifie toutes les données de base nécessaires pour une planification fonctionnelle.
"""
import os
import sys
import django

# Fix encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')
django.setup()

from api_planification.models import TypeTache, RatioProductivite
from api_users.models import (
    Equipe, HoraireTravail, JourFerie, Competence,
    Operateur, Absence
)
from api.models import Site

def print_section(title):
    """Affiche un titre de section."""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}")

def check_types_taches():
    """Vérifie les types de tâches configurés."""
    print_section("1. TYPES DE TÂCHES")

    count = TypeTache.objects.count()
    print(f"\n✅ {count} type(s) de tâche configuré(s)")

    if count > 0:
        print("\nTypes de tâches existants:")
        for tt in TypeTache.objects.all()[:10]:
            print(f"  • {tt.nom_tache} ({tt.unite_productivite})")
        if count > 10:
            print(f"  ... et {count - 10} autre(s)")
    else:
        print("\n❌ AUCUN type de tâche configuré !")
        print("   → Créez des types de tâches via Django Admin ou API")

    return count > 0

def check_ratios_productivite():
    """Vérifie les ratios de productivité."""
    print_section("2. RATIOS DE PRODUCTIVITÉ")

    count = RatioProductivite.objects.filter(actif=True).count()
    print(f"\n✅ {count} ratio(s) de productivité actif(s)")

    if count > 0:
        print("\nExemples de ratios configurés:")
        for ratio in RatioProductivite.objects.filter(actif=True)[:10]:
            print(f"  • {ratio.id_type_tache.nom_tache} × {ratio.type_objet}: {ratio.ratio} {ratio.unite_mesure}/h")
        if count > 10:
            print(f"  ... et {count - 10} autre(s)")

        # Vérifier couverture
        types_avec_ratios = RatioProductivite.objects.filter(actif=True).values_list('id_type_tache', flat=True).distinct().count()
        types_total = TypeTache.objects.count()
        print(f"\n📊 Couverture: {types_avec_ratios}/{types_total} types de tâches ont des ratios")
    else:
        print("\n❌ AUCUN ratio de productivité configuré !")
        print("   → Créez des ratios via /api/planification/ratios-productivite/")

    return count > 0

def check_equipes():
    """Vérifie les équipes."""
    print_section("3. ÉQUIPES")

    count = Equipe.objects.filter(actif=True).count()
    print(f"\n✅ {count} équipe(s) active(s)")

    if count > 0:
        print("\nÉquipes configurées:")
        for equipe in Equipe.objects.filter(actif=True)[:10]:
            membres = equipe.operateurs.filter(statut='ACTIF').count()
            chef = equipe.chef_equipe
            print(f"  • {equipe.nom_equipe}: {membres} membre(s), Chef: {chef.prenom if chef else 'Aucun'}")

        # Vérifier équipes sans membres
        sans_membres = Equipe.objects.filter(actif=True, operateurs__isnull=True).count()
        if sans_membres > 0:
            print(f"\n⚠️  {sans_membres} équipe(s) sans membres")
    else:
        print("\n❌ AUCUNE équipe configurée !")
        print("   → Créez des équipes via /api/users/equipes/")

    return count > 0

def check_horaires_travail():
    """Vérifie les horaires de travail."""
    print_section("4. HORAIRES DE TRAVAIL")

    count = HoraireTravail.objects.filter(actif=True).count()
    print(f"\n✅ {count} horaire(s) de travail configuré(s)")

    if count > 0:
        equipes_avec_horaires = HoraireTravail.objects.filter(actif=True).values_list('equipe', flat=True).distinct().count()
        equipes_total = Equipe.objects.filter(actif=True).count()

        print(f"📊 Couverture: {equipes_avec_horaires}/{equipes_total} équipes ont des horaires")

        print("\nExemples d'horaires:")
        for horaire in HoraireTravail.objects.filter(actif=True)[:5]:
            print(f"  • {horaire.equipe.nom_equipe} - {horaire.get_jour_semaine_display()}: "
                  f"{horaire.heure_debut.strftime('%H:%M')}-{horaire.heure_fin.strftime('%H:%M')} "
                  f"({horaire.heures_travaillables}h)")

        # Vérifier équipes sans horaires
        equipes_actives = set(Equipe.objects.filter(actif=True).values_list('id', flat=True))
        equipes_avec_horaires_set = set(HoraireTravail.objects.filter(actif=True).values_list('equipe_id', flat=True))
        equipes_sans_horaires = equipes_actives - equipes_avec_horaires_set

        if equipes_sans_horaires:
            print(f"\n⚠️  {len(equipes_sans_horaires)} équipe(s) sans horaires configurés")
            print("   → Utiliser /api/users/horaires/creer_semaine_complete/")
    else:
        print("\n❌ AUCUN horaire de travail configuré !")
        print("   → Créez des horaires via /api/users/horaires/creer_semaine_complete/")

    return count > 0

def check_jours_feries():
    """Vérifie les jours fériés."""
    print_section("5. JOURS FÉRIÉS")

    count = JourFerie.objects.filter(actif=True).count()
    print(f"\n✅ {count} jour(s) férié(s) configuré(s)")

    if count > 0:
        from django.utils import timezone
        annee_actuelle = timezone.now().year

        count_annee = JourFerie.objects.filter(
            actif=True,
            date__year=annee_actuelle
        ).count()

        print(f"📊 {count_annee} jour(s) férié(s) pour {annee_actuelle}")

        print(f"\nJours fériés {annee_actuelle}:")
        for jf in JourFerie.objects.filter(actif=True, date__year=annee_actuelle).order_by('date')[:10]:
            print(f"  • {jf.date.strftime('%d/%m/%Y')} - {jf.nom} ({jf.get_type_ferie_display()})")
    else:
        print("\n⚠️  Aucun jour férié configuré")
        print("   → Optionnel, mais recommandé pour éviter planification sur jours fériés")
        print("   → Créez via /api/users/jours-feries/")

    return True  # Optionnel

def check_competences():
    """Vérifie les compétences."""
    print_section("6. COMPÉTENCES")

    count = Competence.objects.count()
    print(f"\n✅ {count} compétence(s) configurée(s)")

    if count > 0:
        print("\nCompétences disponibles:")
        for comp in Competence.objects.all()[:10]:
            print(f"  • {comp.nom_competence} ({comp.get_categorie_display()})")
        if count > 10:
            print(f"  ... et {count - 10} autre(s)")
    else:
        print("\n⚠️  Aucune compétence configurée")
        print("   → Optionnel pour planification de base")
        print("   → Créez via /api/users/competences/")

    return True  # Optionnel

def check_operateurs():
    """Vérifie les opérateurs."""
    print_section("7. OPÉRATEURS")

    count = Operateur.objects.filter(statut='ACTIF').count()
    print(f"\n✅ {count} opérateur(s) actif(s)")

    if count > 0:
        print("\nOpérateurs actifs:")
        for op in Operateur.objects.filter(statut='ACTIF')[:10]:
            equipe = op.equipe
            print(f"  • {op.prenom} {op.nom} - Équipe: {equipe.nom_equipe if equipe else 'Aucune'}")

        # Vérifier opérateurs sans équipe
        sans_equipe = Operateur.objects.filter(statut='ACTIF', equipe__isnull=True).count()
        if sans_equipe > 0:
            print(f"\n⚠️  {sans_equipe} opérateur(s) sans équipe")
    else:
        print("\n❌ AUCUN opérateur configuré !")
        print("   → Créez des opérateurs via /api/users/operateurs/")

    return count > 0

def check_sites():
    """Vérifie les sites."""
    print_section("8. SITES")

    count = Site.objects.filter(actif=True).count()
    print(f"\n✅ {count} site(s) actif(s)")

    if count > 0:
        print("\nSites configurés:")
        for site in Site.objects.filter(actif=True)[:10]:
            print(f"  • {site.nom_site} ({site.code_site})")
    else:
        print("\n⚠️  Aucun site configuré")
        print("   → Pas obligatoire pour planification, mais recommandé")

    return True  # Optionnel

def generate_recommendations():
    """Génère des recommandations."""
    print_section("RECOMMANDATIONS")

    recommendations = []

    # Vérifier données critiques
    if TypeTache.objects.count() == 0:
        recommendations.append({
            'priority': '[CRITIQUE]',
            'item': 'Types de taches',
            'action': 'Creer au moins 5-10 types de taches de base (Tonte, Elagage, Arrosage, etc.)',
            'endpoint': 'POST /api/planification/types-taches/'
        })

    if RatioProductivite.objects.filter(actif=True).count() == 0:
        recommendations.append({
            'priority': '[CRITIQUE]',
            'item': 'Ratios de productivite',
            'action': 'Configurer les ratios pour chaque type de tache x type d\'objet',
            'endpoint': 'POST /api/planification/ratios-productivite/'
        })

    if Equipe.objects.filter(actif=True).count() == 0:
        recommendations.append({
            'priority': '[CRITIQUE]',
            'item': 'Equipes',
            'action': 'Creer au moins 1 equipe',
            'endpoint': 'POST /api/users/equipes/'
        })

    if HoraireTravail.objects.filter(actif=True).count() == 0:
        recommendations.append({
            'priority': '[IMPORTANT]',
            'item': 'Horaires de travail',
            'action': 'Configurer les horaires pour chaque equipe (Lun-Dim)',
            'endpoint': 'POST /api/users/horaires/creer_semaine_complete/'
        })

    if Operateur.objects.filter(statut='ACTIF').count() == 0:
        recommendations.append({
            'priority': '[IMPORTANT]',
            'item': 'Operateurs',
            'action': 'Creer des operateurs et les affecter aux equipes',
            'endpoint': 'POST /api/users/operateurs/'
        })

    if JourFerie.objects.filter(actif=True).count() == 0:
        recommendations.append({
            'priority': '[RECOMMANDE]',
            'item': 'Jours feries',
            'action': 'Configurer les jours feries nationaux pour l\'annee en cours',
            'endpoint': 'POST /api/users/jours-feries/'
        })

    if recommendations:
        print("\n📋 Actions à réaliser:\n")
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. {rec['priority']} - {rec['item']}")
            print(f"   Action: {rec['action']}")
            print(f"   Endpoint: {rec['endpoint']}\n")
    else:
        print("\n✅ Toutes les données de base sont configurées !")
        print("   Le système de planification est prêt à être utilisé.")

def main():
    """Point d'entrée principal."""
    print("\n" + "="*80)
    print("  AUDIT COMPLET - SYSTÈME DE PLANIFICATION")
    print("="*80)

    # Exécuter tous les checks
    checks = [
        ('Types de tâches', check_types_taches),
        ('Ratios de productivité', check_ratios_productivite),
        ('Équipes', check_equipes),
        ('Horaires de travail', check_horaires_travail),
        ('Jours fériés', check_jours_feries),
        ('Compétences', check_competences),
        ('Opérateurs', check_operateurs),
        ('Sites', check_sites),
    ]

    results = {}
    for name, check_func in checks:
        results[name] = check_func()

    # Résumé
    print_section("RÉSUMÉ")
    print()
    for name, result in results.items():
        status = "✅ OK" if result else "❌ MANQUANT"
        print(f"  {status:12} - {name}")

    # Recommandations
    generate_recommendations()

    print("\n" + "="*80)
    print("  FIN DE L'AUDIT")
    print("="*80 + "\n")

if __name__ == '__main__':
    main()
