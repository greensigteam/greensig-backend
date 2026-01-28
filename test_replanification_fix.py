import os
import django
from datetime import date, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')
django.setup()

from api_planification.models import Tache, DistributionCharge
from api_planification.serializers import TacheCreateUpdateSerializer

def test_replanification_coherence():
    """
    Test que la replanification d'une tâche EXPIREE restaure TOUJOURS les distributions,
    peu importe si les nouvelles dates sont dans le futur ou le passé.
    """
    print("=== Test de cohérence de replanification ===\n")
    
    # 1. Trouver une tâche EXPIREE avec distributions ANNULEE
    tache = Tache.objects.filter(statut='EXPIREE').first()
    
    if not tache:
        print("❌ Aucune tâche EXPIREE trouvée pour le test")
        return
    
    print(f"Tâche trouvée: #{tache.id}")
    print(f"Statut actuel: {tache.statut}")
    print(f"Statut calculé: {tache.computed_statut}")
    
    # Vérifier les distributions
    distributions = tache.distributions_charge.all()
    annulees = distributions.filter(status='ANNULEE').count()
    print(f"Distributions: {distributions.count()} total, {annulees} ANNULEE\n")
    
    if annulees == 0:
        print("⚠️ Aucune distribution ANNULEE à restaurer")
        # Créer une distribution annulée pour le test
        dist = DistributionCharge.objects.create(
            tache=tache,
            date=date.today() - timedelta(days=5),
            heures_planifiees=1.0,
            status='ANNULEE'
        )
        print(f"✅ Distribution ANNULEE créée pour le test: #{dist.id}\n")
        annulees = 1
    
    # 2. TEST 1: Replanifier avec dates DANS LE FUTUR
    print("--- TEST 1: Replanification avec dates futures ---")
    future_start = date.today() + timedelta(days=2)
    future_end = date.today() + timedelta(days=5)
    
    serializer = TacheCreateUpdateSerializer(
        instance=tache,
        data={
            'date_debut_planifiee': future_start.isoformat(),
            'date_fin_planifiee': future_end.isoformat(),
        },
        partial=True
    )
    
    if serializer.is_valid():
        serializer.save()
        tache.refresh_from_db()
        restored_1 = tache.distributions_charge.filter(status='NON_REALISEE').count()
        print(f"✅ Tâche mise à jour avec dates futures")
        print(f"   Nouveau statut calculé: {tache.computed_statut}")
        print(f"   Distributions NON_REALISEE: {restored_1}")
        
        # Remettre les distributions en ANNULEE pour le test 2
        tache.distributions_charge.update(status='ANNULEE')
        tache.refresh_from_db()
    else:
        print(f"❌ Erreur: {serializer.errors}")
        return
    
    print()
    
    # 3. TEST 2: Replanifier avec dates DANS LE PASSÉ
    print("--- TEST 2: Replanification avec dates passées ---")
    past_start = date.today() - timedelta(days=10)
    past_end = date.today() - timedelta(days=7)
    
    serializer = TacheCreateUpdateSerializer(
        instance=tache,
        data={
            'date_debut_planifiee': past_start.isoformat(),
            'date_fin_planifiee': past_end.isoformat(),
        },
        partial=True
    )
    
    if serializer.is_valid():
        serializer.save()
        tache.refresh_from_db()
        restored_2 = tache.distributions_charge.filter(status='NON_REALISEE').count()
        print(f"✅ Tâche mise à jour avec dates passées")
        print(f"   Nouveau statut calculé: {tache.computed_statut}")
        print(f"   Distributions NON_REALISEE: {restored_2}")
    else:
        print(f"❌ Erreur: {serializer.errors}")
        return
    
    print()
    
    # 4. Vérification finale
    print("=== RÉSULTAT ===")
    if restored_1 > 0 and restored_2 > 0:
        print("✅ SUCCESS: Les distributions sont restaurées dans les DEUX cas")
        print("   → Comportement cohérent !")
    elif restored_1 > 0 and restored_2 == 0:
        print("❌ FAIL: Restauration uniquement pour dates futures")
        print("   → Comportement incohérent (bug non corrigé)")
    else:
        print("❌ FAIL: Aucune restauration")

if __name__ == '__main__':
    test_replanification_coherence()
