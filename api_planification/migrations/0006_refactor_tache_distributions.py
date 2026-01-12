# Generated migration for refactoring Tache and DistributionCharge
# Date: 2026-01-11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api_planification', '0005_distributioncharge'),
    ]

    operations = [
        # 1. Convertir date_debut_planifiee et date_fin_planifiee en DateField
        migrations.AlterField(
            model_name='tache',
            name='date_debut_planifiee',
            field=models.DateField(verbose_name='Date début planifiée'),
        ),
        migrations.AlterField(
            model_name='tache',
            name='date_fin_planifiee',
            field=models.DateField(verbose_name='Date fin planifiée'),
        ),

        # 2. Convertir date_debut_reelle et date_fin_reelle en DateField
        migrations.AlterField(
            model_name='tache',
            name='date_debut_reelle',
            field=models.DateField(blank=True, null=True, verbose_name='Date début réelle'),
        ),
        migrations.AlterField(
            model_name='tache',
            name='date_fin_reelle',
            field=models.DateField(blank=True, null=True, verbose_name='Date fin réelle'),
        ),

        # 2. Ajouter heure_debut et heure_fin à DistributionCharge
        migrations.AddField(
            model_name='distributioncharge',
            name='heure_debut',
            field=models.TimeField(blank=True, help_text='Heure de début de travail prévue (ex: 08:00)', null=True, verbose_name='Heure de début'),
        ),
        migrations.AddField(
            model_name='distributioncharge',
            name='heure_fin',
            field=models.TimeField(blank=True, help_text='Heure de fin de travail prévue (ex: 17:00)', null=True, verbose_name='Heure de fin'),
        ),
    ]
