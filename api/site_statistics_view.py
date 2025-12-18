# api/site_statistics_view.py
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Count
from datetime import datetime, timedelta

from .models import (
    Site, Objet, Arbre, Gazon, Palmier, Arbuste, Vivace, Cactus, Graminee,
    Puit, Pompe, Vanne, Clapet, Canalisation, Aspersion, Goutte, Ballon
)


class SiteStatisticsView(APIView):
    """
    Vue pour retourner les statistiques d'un site spécifique.
    
    GET /api/sites/{site_id}/statistics/
    
    Returns:
        {
            "site_info": {
                "id": 1,
                "nom": "Site A",
                "superficie": 44486.08
            },
            "vegetation": {
                "total": 150,
                "by_type": {
                    "arbres": 50,
                    "gazons": 20,
                    "palmiers": 30,
                    ...
                },
                "by_state": {
                    "bon": 120,
                    "moyen": 20,
                    "mauvais": 8,
                    "critique": 2
                },
                "by_family": [
                    {"famille": "Palmaceae", "count": 25},
                    ...
                ]
            },
            "hydraulique": {
                "total": 80,
                "by_type": {
                    "puits": 5,
                    "pompes": 10,
                    ...
                },
                "by_state": {...}
            },
            "interventions": {
                "never_intervened": 30,
                "urgent_maintenance": 15,
                "last_30_days": 25
            }
        }
    """
    
    def get(self, request, site_id):
        try:
            site = Site.objects.get(pk=site_id)
        except Site.DoesNotExist:
            return Response({'error': 'Site not found'}, status=404)
        
        # Site info
        site_info = {
            'id': site.id,
            'nom': site.nom_site,
            'superficie': site.superficie_totale
        }
        
        # Get all objects for this site
        objets = Objet.objects.filter(site=site).select_related(
            'arbre', 'gazon', 'palmier', 'arbuste', 'vivace', 'cactus', 'graminee',
            'puit', 'pompe', 'vanne', 'clapet', 'canalisation', 'aspersion', 'goutte', 'ballon'
        )
        
        # Count by type
        vegetation_types = {
            'arbres': Arbre.objects.filter(site=site).count(),
            'gazons': Gazon.objects.filter(site=site).count(),
            'palmiers': Palmier.objects.filter(site=site).count(),
            'arbustes': Arbuste.objects.filter(site=site).count(),
            'vivaces': Vivace.objects.filter(site=site).count(),
            'cactus': Cactus.objects.filter(site=site).count(),
            'graminees': Graminee.objects.filter(site=site).count(),
        }
        
        hydraulique_types = {
            'puits': Puit.objects.filter(site=site).count(),
            'pompes': Pompe.objects.filter(site=site).count(),
            'vannes': Vanne.objects.filter(site=site).count(),
            'clapets': Clapet.objects.filter(site=site).count(),
            'canalisations': Canalisation.objects.filter(site=site).count(),
            'aspersions': Aspersion.objects.filter(site=site).count(),
            'gouttes': Goutte.objects.filter(site=site).count(),
            'ballons': Ballon.objects.filter(site=site).count(),
        }
        
        # Count by state - SEPARATELY for vegetation and hydraulic
        vegetation_models = [Arbre, Gazon, Palmier, Arbuste, Vivace, Cactus, Graminee]
        hydraulic_models = [Puit, Pompe, Vanne, Clapet, Canalisation, Aspersion, Goutte, Ballon]

        # Initialize state counts
        vegetation_by_state = {'bon': 0, 'moyen': 0, 'mauvais': 0, 'critique': 0}
        hydraulic_by_state = {'bon': 0, 'moyen': 0, 'mauvais': 0, 'critique': 0}

        # Count vegetation by state
        for Model in vegetation_models:
            state_counts = Model.objects.filter(site=site).values('etat').annotate(count=Count('id'))
            for item in state_counts:
                if item['etat'] in vegetation_by_state:
                    vegetation_by_state[item['etat']] += item['count']

        # Count hydraulic by state
        for Model in hydraulic_models:
            state_counts = Model.objects.filter(site=site).values('etat').annotate(count=Count('id'))
            for item in state_counts:
                if item['etat'] in hydraulic_by_state:
                    hydraulic_by_state[item['etat']] += item['count']
        
        # Vegetation by family
        families = []
        for Model in [Arbre, Gazon, Palmier, Arbuste, Vivace, Cactus, Graminee]:
            family_counts = Model.objects.filter(site=site).exclude(
                famille__isnull=True
            ).exclude(famille='').values('famille').annotate(count=Count('id'))
            families.extend([{'famille': f['famille'], 'count': f['count']} for f in family_counts])
        
        # Sort by count and get top 10
        families.sort(key=lambda x: x['count'], reverse=True)
        top_families = families[:10]
        
        # Intervention statistics
        now = datetime.now().date()
        thirty_days_ago = now - timedelta(days=30)
        six_months_ago = now - timedelta(days=180)
        
        # Count objects with intervention dates
        intervention_stats = {
            'never_intervened': 0,
            'urgent_maintenance': 0,  # > 6 months
            'last_30_days': 0
        }
        
        # Check ALL models (vegetation + hydraulic)
        all_models = vegetation_models + hydraulic_models
        for Model in all_models:
            if hasattr(Model, 'last_intervention_date'):
                intervention_stats['never_intervened'] += Model.objects.filter(
                    site=site,
                    last_intervention_date__isnull=True
                ).count()

                intervention_stats['urgent_maintenance'] += Model.objects.filter(
                    site=site,
                    last_intervention_date__lt=six_months_ago
                ).count()

                intervention_stats['last_30_days'] += Model.objects.filter(
                    site=site,
                    last_intervention_date__gte=thirty_days_ago
                ).count()
        
        return Response({
            'site_info': site_info,
            'vegetation': {
                'total': sum(vegetation_types.values()),
                'by_type': vegetation_types,
                'by_state': vegetation_by_state,
                'by_family': top_families
            },
            'hydraulique': {
                'total': sum(hydraulique_types.values()),
                'by_type': hydraulique_types,
                'by_state': hydraulic_by_state
            },
            'interventions': intervention_stats,
            'total_objects': sum(vegetation_types.values()) + sum(hydraulique_types.values())
        })
