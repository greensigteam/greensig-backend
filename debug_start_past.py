import os
import django
import sys
import json
from datetime import date, datetime, timedelta

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')
django.setup()

from api_planification.models import DistributionCharge, Tache
from api_planification.views import DistributionChargeViewSet
from rest_framework.test import APIRequestFactory, force_authenticate
from api_users.models import Utilisateur

def debug_start_past():
    print("--- Debugging Start in Past ---")
    
    # 1. Find a NON_REALISEE distribution
    dist = DistributionCharge.objects.filter(status='NON_REALISEE').first()
    
    if not dist:
        print("No NON_REALISEE distribution found. Creating one...")
        tache = Tache.objects.first()
        if not tache:
            print("No task found.")
            return

        dist = DistributionCharge.objects.create(
            tache=tache,
            date=date.today(),
            heures_planifiees=1.0,
            status='NON_REALISEE'
        )
    
    print(f"Distribution ID: {dist.id}")
    print(f"Current Status: {dist.status}")

    # 2. Simulate Request with PAST date
    factory = APIRequestFactory()
    
    past_date = (date.today() - timedelta(days=5)).strftime('%Y-%m-%d')
    print(f"Attempting to start with past date: {past_date}")
    
    payload = {
        'heure_debut_reelle': '08:00',
        'date_debut_reelle': past_date
    }
    
    request = factory.post(
        f'/api/planification/distributions/{dist.id}/demarrer/',
        payload,
        format='json'
    )

    # 3. Authenticate
    user = Utilisateur.objects.filter(is_superuser=True).first() or Utilisateur.objects.first()
    force_authenticate(request, user=user)
    
    # 4. Call View
    view = DistributionChargeViewSet.as_view({'post': 'demarrer'})
    
    try:
        response = view(request, pk=dist.id)
        print(f"Response Status: {response.status_code}")
        print(f"Response Data: {response.data}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == '__main__':
    debug_start_past()
