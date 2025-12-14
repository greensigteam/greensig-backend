# Script Django pour supprimer tous les utilisateurs n'ayant que le rôle OPERATEUR

from django.core.management.base import BaseCommand
from api_users.models import Utilisateur

class Command(BaseCommand):
    help = "Supprime tous les utilisateurs n'ayant que le rôle OPERATEUR."

    def handle(self, *args, **options):
        count = 0
        for user in Utilisateur.objects.all():
            roles = list(user.roles_utilisateur.values_list('role__nom_role', flat=True))
            if len(roles) == 1 and roles[0] == 'OPERATEUR':
                email = user.email
                user.delete()
                count += 1
                self.stdout.write(self.style.WARNING(f"Utilisateur supprimé: {email}"))
        self.stdout.write(self.style.SUCCESS(f"{count} utilisateur(s) supprimé(s) (seulement OPERATEUR)."))
