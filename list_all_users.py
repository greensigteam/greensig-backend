import os
import django

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')
django.setup()

from api_users.models import Utilisateur


def list_all_users():
    users = Utilisateur.objects.all()
    for user in users:
        print(f"ID: {user.id} | Email: {user.email} | Nom: {user.nom} | Prénom: {user.prenom} | Actif: {user.actif} | Dernière connexion: {user.derniere_connexion}")

if __name__ == "__main__":
    list_all_users()
