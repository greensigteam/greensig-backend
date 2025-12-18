# Generated manually for data migration

from django.db import migrations


def migrate_equipe_to_equipes(apps, schema_editor):
    """
    Migre les données de id_equipe (FK) vers equipes (M2M)
    pour les tâches existantes.
    """
    Tache = apps.get_model('api_planification', 'Tache')
    for tache in Tache.objects.filter(id_equipe__isnull=False):
        tache.equipes.add(tache.id_equipe)


def reverse_migrate(apps, schema_editor):
    """
    Reverse: copie la première équipe de equipes vers id_equipe
    """
    Tache = apps.get_model('api_planification', 'Tache')
    for tache in Tache.objects.all():
        first_equipe = tache.equipes.first()
        if first_equipe:
            tache.id_equipe = first_equipe
            tache.save()


class Migration(migrations.Migration):

    dependencies = [
        ('api_planification', '0006_add_equipes_m2m'),
    ]

    operations = [
        migrations.RunPython(migrate_equipe_to_equipes, reverse_migrate),
    ]
