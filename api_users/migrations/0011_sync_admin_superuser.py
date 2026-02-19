from django.db import migrations


def sync_admin_superuser(apps, schema_editor):
    """Synchronise is_superuser=True pour tous les utilisateurs ayant le rôle ADMIN."""
    Utilisateur = apps.get_model('api_users', 'Utilisateur')
    UtilisateurRole = apps.get_model('api_users', 'UtilisateurRole')
    Role = apps.get_model('api_users', 'Role')

    try:
        admin_role = Role.objects.get(nom_role='ADMIN')
    except Role.DoesNotExist:
        return

    admin_user_ids = UtilisateurRole.objects.filter(
        role=admin_role
    ).values_list('utilisateur_id', flat=True)

    Utilisateur.objects.filter(
        id__in=admin_user_ids,
        is_superuser=False
    ).update(is_superuser=True, is_staff=True)


def reverse_sync(apps, schema_editor):
    """Reverse: ne rien faire (on ne veut pas retirer is_superuser)."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('api_users', '0010_alter_horairetravail_unique_together_and_more'),
    ]

    operations = [
        migrations.RunPython(sync_admin_superuser, reverse_sync),
    ]
