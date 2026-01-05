# Generated data migration to populate id_structure_client on existing tasks

from django.db import migrations


def populate_structure_client(apps, schema_editor):
    """
    Populate id_structure_client on existing tasks based on their linked objects' sites.

    For each task that has objets linked but no id_structure_client:
    1. Get the first object's site
    2. Get the site's structure_client
    3. Assign it to the task
    """
    Tache = apps.get_model('api_planification', 'Tache')

    # Get all tasks that don't have id_structure_client set
    tasks_without_structure = Tache.objects.filter(
        id_structure_client__isnull=True
    ).prefetch_related('objets__site')

    updated_count = 0

    for tache in tasks_without_structure:
        # Find the first object with a site that has structure_client
        for obj in tache.objets.all():
            if obj.site_id:
                # Get the site to check for structure_client
                from api.models import Site
                try:
                    site = Site.objects.get(pk=obj.site_id)
                    if site.structure_client_id:
                        tache.id_structure_client_id = site.structure_client_id
                        tache.save(update_fields=['id_structure_client'])
                        updated_count += 1
                        break
                except Site.DoesNotExist:
                    pass

    if updated_count:
        print(f"[DATA MIGRATION] Updated {updated_count} tasks with structure_client")


def reverse_populate(apps, schema_editor):
    """Reverse migration - set id_structure_client to NULL."""
    Tache = apps.get_model('api_planification', 'Tache')
    Tache.objects.filter(id_structure_client__isnull=False).update(id_structure_client=None)


class Migration(migrations.Migration):

    dependencies = [
        ('api_planification', '0003_add_structure_client'),
        ('api', '0005_notification_model'),  # Ensure api is ready
    ]

    operations = [
        migrations.RunPython(populate_structure_client, reverse_populate),
    ]
