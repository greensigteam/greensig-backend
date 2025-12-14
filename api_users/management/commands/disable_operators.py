# Script Django pour désactiver tous les utilisateurs n'ayant que le rôle OPERATEUR

from django.core.management.base import BaseCommand
from api_users.models import Utilisateur, UtilisateurRole

class Command(BaseCommand):
    help = "Désactive tous les utilisateurs n'ayant que le rôle OPERATEUR."

    def handle(self, *args, **options):
        count = 0
        for user in Utilisateur.objects.filter(actif=True):
            roles = list(user.roles_utilisateur.values_list('role__nom_role', flat=True))
            if len(roles) == 1 and roles[0] == 'OPERATEUR':
                user.actif = False
                user.save()
                count += 1
                self.stdout.write(self.style.WARNING(f"Utilisateur désactivé: {user.email}"))
        self.stdout.write(self.style.SUCCESS(f"{count} utilisateur(s) désactivé(s) (seulement OPERATEUR)."))
