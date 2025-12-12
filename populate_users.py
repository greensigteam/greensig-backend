#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script pour alimenter la base de donnees avec les utilisateurs simules.
Conforme aux donnees mockees du frontend (mockUsersData.ts)

Usage:
    python populate_users.py

Mot de passe par defaut pour tous les comptes: greensig2024
"""

import os
import sys
import io
import django

# Force UTF-8 output on Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from datetime import date, datetime
from django.utils import timezone
from api_users.models import (
    Utilisateur, Role, UtilisateurRole, Client, Operateur,
    Competence, CompetenceOperateur, Equipe, Absence,
    HistoriqueEquipeOperateur,
    TypeUtilisateur, StatutOperateur, NiveauCompetence,
    TypeAbsence, StatutAbsence
)

# Mot de passe par defaut pour tous les comptes
DEFAULT_PASSWORD = 'greensig2025'


def clear_existing_data():
    """Supprime les données existantes (sauf compétences et rôles)."""
    print("\n🗑️  Nettoyage des données existantes...")

    # Ordre important pour respecter les contraintes FK
    HistoriqueEquipeOperateur.objects.all().delete()
    Absence.objects.all().delete()
    CompetenceOperateur.objects.all().delete()
    Equipe.objects.all().delete()
    Client.objects.all().delete()
    Operateur.objects.all().delete()
    UtilisateurRole.objects.all().delete()

    # Supprimer les utilisateurs sauf superuser
    Utilisateur.objects.filter(is_superuser=False).delete()

    print("   ✅ Données nettoyées")


def ensure_roles_and_competences():
    """S'assure que les rôles et compétences existent."""
    print("\n📋 Vérification des rôles et compétences...")

    # Les rôles sont normalement créés par init_competences
    roles_count = Role.objects.count()
    competences_count = Competence.objects.count()

    if roles_count == 0 or competences_count == 0:
        print("   ⚠️  Rôles ou compétences manquants!")
        print("   Exécutez d'abord: python manage.py init_competences")
        sys.exit(1)

    print(f"   ✅ {roles_count} rôles, {competences_count} compétences trouvés")


def create_utilisateurs():
    """Crée les utilisateurs de base."""
    print("\n👥 Création des utilisateurs...")

    utilisateurs_data = [
        {
            'email': 'admin@greensig.ma',
            'nom': 'Admin',
            'prenom': 'Super',
            'type_utilisateur': TypeUtilisateur.ADMIN,
            'is_staff': True,
            'roles': ['ADMIN']
        },
        {
            'email': 'hassan.idrissi@greensig.ma',
            'nom': 'Idrissi',
            'prenom': 'Hassan',
            'type_utilisateur': TypeUtilisateur.OPERATEUR,
            'roles': ['OPERATEUR', 'CHEF_EQUIPE']
        },
        {
            'email': 'youssef.amrani@greensig.ma',
            'nom': 'Amrani',
            'prenom': 'Youssef',
            'type_utilisateur': TypeUtilisateur.OPERATEUR,
            'roles': ['OPERATEUR']
        },
        {
            'email': 'karim.benjelloun@greensig.ma',
            'nom': 'Benjelloun',
            'prenom': 'Karim',
            'type_utilisateur': TypeUtilisateur.OPERATEUR,
            'roles': ['OPERATEUR']
        },
        {
            'email': 'omar.tazi@greensig.ma',
            'nom': 'Tazi',
            'prenom': 'Omar',
            'type_utilisateur': TypeUtilisateur.OPERATEUR,
            'roles': ['OPERATEUR', 'CHEF_EQUIPE']
        },
        {
            'email': 'fatima.alaoui@greensig.ma',
            'nom': 'Alaoui',
            'prenom': 'Fatima',
            'type_utilisateur': TypeUtilisateur.OPERATEUR,
            'roles': ['OPERATEUR']
        },
        {
            'email': 'ahmed.benali@client.ma',
            'nom': 'Benali',
            'prenom': 'Ahmed',
            'type_utilisateur': TypeUtilisateur.CLIENT,
            'roles': ['CLIENT']
        },
        {
            'email': 'said.mokhtar@greensig.ma',
            'nom': 'Mokhtar',
            'prenom': 'Said',
            'type_utilisateur': TypeUtilisateur.OPERATEUR,
            'roles': ['OPERATEUR']
        },
    ]

    created_users = {}

    for data in utilisateurs_data:
        roles_names = data.pop('roles')

        # Créer l'utilisateur
        user, created = Utilisateur.objects.get_or_create(
            email=data['email'],
            defaults=data
        )


        # Toujours réinitialiser le mot de passe, même si l'utilisateur existe déjà
        user.set_password(DEFAULT_PASSWORD)
        user.save()
        if created:
            print(f"   ✅ Créé: {user.get_full_name()} ({user.email})")
        else:
            print(f"   🔄 Réinitialisé: {user.get_full_name()} ({user.email})")

        # Assigner les rôles
        for role_name in roles_names:
            try:
                role = Role.objects.get(nom_role=role_name)
                UtilisateurRole.objects.get_or_create(
                    utilisateur=user,
                    role=role
                )
            except Role.DoesNotExist:
                print(f"   ⚠️  Rôle non trouvé: {role_name}")

        created_users[data['email']] = user

    return created_users


def create_client(users):
    """Crée le profil client."""
    print("\n🏢 Création du client...")

    user = users.get('ahmed.benali@client.ma')
    if not user:
        print("   ⚠️  Utilisateur client non trouvé")
        return None

    client, created = Client.objects.get_or_create(
        utilisateur=user,
        defaults={
            'nom_structure': 'Residence Al Amal',
            'adresse': 'Hay Riad, Rabat',
            'telephone': '+212 6 12 34 56 78',
            'contact_principal': 'Ahmed Benali',
            'email_facturation': 'facturation@residencealamal.ma'
        }
    )

    if created:
        print(f"   ✅ Client créé: {client.nom_structure}")
    else:
        print(f"   ⏭️  Client existe: {client.nom_structure}")

    return client


def create_operateurs(users):
    """Crée les profils opérateurs."""
    print("\n🔧 Création des opérateurs...")

    operateurs_data = [
        {
            'email': 'hassan.idrissi@greensig.ma',
            'numero_immatriculation': 'OP-2024-001',
            'statut': StatutOperateur.ACTIF,
            'date_embauche': date(2024, 2, 1),
            'telephone': '+212 6 11 11 11 11'
        },
        {
            'email': 'youssef.amrani@greensig.ma',
            'numero_immatriculation': 'OP-2024-002',
            'statut': StatutOperateur.ACTIF,
            'date_embauche': date(2024, 3, 15),
            'telephone': '+212 6 22 22 22 22'
        },
        {
            'email': 'karim.benjelloun@greensig.ma',
            'numero_immatriculation': 'OP-2024-003',
            'statut': StatutOperateur.EN_CONGE,
            'date_embauche': date(2024, 4, 1),
            'telephone': '+212 6 33 33 33 33'
        },
        {
            'email': 'omar.tazi@greensig.ma',
            'numero_immatriculation': 'OP-2024-004',
            'statut': StatutOperateur.ACTIF,
            'date_embauche': date(2024, 2, 15),
            'telephone': '+212 6 44 44 44 44'
        },
        {
            'email': 'fatima.alaoui@greensig.ma',
            'numero_immatriculation': 'OP-2024-005',
            'statut': StatutOperateur.ACTIF,
            'date_embauche': date(2024, 5, 1),
            'telephone': '+212 6 55 55 55 55'
        },
        {
            'email': 'said.mokhtar@greensig.ma',
            'numero_immatriculation': 'OP-2024-006',
            'statut': StatutOperateur.ACTIF,
            'date_embauche': date(2024, 6, 1),
            'telephone': '+212 6 66 66 66 66'
        },
    ]

    created_operateurs = {}

    for data in operateurs_data:
        email = data.pop('email')
        user = users.get(email)

        if not user:
            print(f"   ⚠️  Utilisateur non trouvé: {email}")
            continue

        operateur, created = Operateur.objects.get_or_create(
            utilisateur=user,
            defaults=data
        )

        if created:
            print(f"   ✅ Opérateur créé: {operateur}")
        else:
            print(f"   ⏭️  Opérateur existe: {operateur}")

        created_operateurs[email] = operateur

    return created_operateurs


def assign_competences(operateurs):
    """Assigne les compétences aux opérateurs."""
    print("\n🎓 Attribution des compétences...")

    # Récupérer les compétences par nom
    competences = {c.nom_competence: c for c in Competence.objects.all()}

    # Noms exacts des competences dans la base (sans accents)
    competences_data = [
        # Hassan Idrissi (Chef equipe)
        ('hassan.idrissi@greensig.ma', 'Utilisation de tondeuse', NiveauCompetence.EXPERT, date(2024, 2, 15)),
        ('hassan.idrissi@greensig.ma', 'Taille de nettoyage', NiveauCompetence.EXPERT, date(2024, 2, 15)),
        ('hassan.idrissi@greensig.ma', 'Arrosage', NiveauCompetence.INTERMEDIAIRE, date(2024, 3, 1)),
        ('hassan.idrissi@greensig.ma', "Gestion d'equipe", NiveauCompetence.EXPERT, date(2024, 2, 1)),
        ('hassan.idrissi@greensig.ma', 'Organisation des taches', NiveauCompetence.INTERMEDIAIRE, date(2024, 2, 1)),

        # Youssef Amrani
        ('youssef.amrani@greensig.ma', 'Utilisation de tondeuse', NiveauCompetence.INTERMEDIAIRE, date(2024, 4, 1)),
        ('youssef.amrani@greensig.ma', 'Arrosage', NiveauCompetence.EXPERT, date(2024, 3, 20)),
        ('youssef.amrani@greensig.ma', 'Nettoyage general', NiveauCompetence.INTERMEDIAIRE, date(2024, 4, 15)),

        # Karim Benjelloun
        ('karim.benjelloun@greensig.ma', 'Taille de nettoyage', NiveauCompetence.EXPERT, date(2024, 4, 15)),
        ('karim.benjelloun@greensig.ma', 'Taille de decoration', NiveauCompetence.INTERMEDIAIRE, date(2024, 5, 1)),
        ('karim.benjelloun@greensig.ma', 'Confection des cuvettes', NiveauCompetence.EXPERT, date(2024, 4, 15)),

        # Omar Tazi (Chef equipe)
        ('omar.tazi@greensig.ma', 'Utilisation de tondeuse', NiveauCompetence.EXPERT, date(2024, 2, 20)),
        ('omar.tazi@greensig.ma', 'Taille de nettoyage', NiveauCompetence.EXPERT, date(2024, 2, 20)),
        ('omar.tazi@greensig.ma', 'Confection des cuvettes', NiveauCompetence.EXPERT, date(2024, 3, 1)),
        ('omar.tazi@greensig.ma', "Gestion d'equipe", NiveauCompetence.INTERMEDIAIRE, date(2024, 2, 15)),

        # Fatima Alaoui
        ('fatima.alaoui@greensig.ma', 'Arrosage', NiveauCompetence.EXPERT, date(2024, 5, 15)),
        ('fatima.alaoui@greensig.ma', 'Desherbage manuel et mecanique', NiveauCompetence.INTERMEDIAIRE, date(2024, 6, 1)),
        ('fatima.alaoui@greensig.ma', 'Nettoyage general', NiveauCompetence.EXPERT, date(2024, 5, 20)),

        # Said Mokhtar
        ('said.mokhtar@greensig.ma', 'Utilisation de tondeuse', NiveauCompetence.DEBUTANT, date(2024, 6, 15)),
        ('said.mokhtar@greensig.ma', 'Nettoyage general', NiveauCompetence.INTERMEDIAIRE, date(2024, 7, 1)),
    ]

    count = 0
    for email, comp_name, niveau, date_acq in competences_data:
        operateur = operateurs.get(email)
        competence = competences.get(comp_name)

        if not operateur or not competence:
            print(f"   ⚠️  Opérateur ou compétence non trouvé: {email} / {comp_name}")
            continue

        _, created = CompetenceOperateur.objects.get_or_create(
            operateur=operateur,
            competence=competence,
            defaults={
                'niveau': niveau,
                'date_acquisition': date_acq
            }
        )

        if created:
            count += 1

    print(f"   ✅ {count} compétences attribuées")


def create_equipes(operateurs):
    """Crée les équipes."""
    print("\n👷 Création des équipes...")

    # Hassan est chef de l'équipe A
    hassan = operateurs.get('hassan.idrissi@greensig.ma')
    # Omar est chef de l'équipe B
    omar = operateurs.get('omar.tazi@greensig.ma')

    if not hassan or not omar:
        print("   ⚠️  Chefs d'équipe non trouvés")
        return {}

    equipes_data = [
        {
            'nom_equipe': 'Equipe A - Entretien',
            'chef_equipe': hassan,
            'specialite': 'Entretien général',
            'membres': [
                'hassan.idrissi@greensig.ma',
                'youssef.amrani@greensig.ma',
                'fatima.alaoui@greensig.ma'
            ]
        },
        {
            'nom_equipe': 'Equipe B - Plantation',
            'chef_equipe': omar,
            'specialite': 'Plantation et aménagement',
            'membres': [
                'omar.tazi@greensig.ma',
                'karim.benjelloun@greensig.ma'
            ]
        }
    ]

    created_equipes = {}

    for data in equipes_data:
        membres = data.pop('membres')

        # Créer l'équipe sans validation (skip car chef déjà validé)
        equipe, created = Equipe.objects.get_or_create(
            nom_equipe=data['nom_equipe'],
            defaults={
                'chef_equipe': data['chef_equipe'],
                'specialite': data['specialite']
            }
        )

        if created:
            # Sauvegarder avec skip_validation pour éviter l'erreur de circularité
            equipe.save(skip_validation=True)
            print(f"   ✅ Équipe créée: {equipe.nom_equipe}")
        else:
            print(f"   ⏭️  Équipe existe: {equipe.nom_equipe}")

        # Assigner les membres à l'équipe
        for email in membres:
            op = operateurs.get(email)
            if op:
                op.equipe = equipe
                op.save()

        created_equipes[data['nom_equipe']] = equipe

    return created_equipes


def create_historique_equipes(operateurs, equipes):
    """Crée l'historique des affectations aux équipes."""
    print("\n📜 Création de l'historique des équipes...")

    historique_data = [
        ('hassan.idrissi@greensig.ma', 'Equipe A - Entretien', date(2024, 2, 1), 'CHEF'),
        ('youssef.amrani@greensig.ma', 'Equipe A - Entretien', date(2024, 3, 15), 'MEMBRE'),
        ('karim.benjelloun@greensig.ma', 'Equipe B - Plantation', date(2024, 4, 1), 'MEMBRE'),
        ('omar.tazi@greensig.ma', 'Equipe B - Plantation', date(2024, 2, 15), 'CHEF'),
        ('fatima.alaoui@greensig.ma', 'Equipe A - Entretien', date(2024, 5, 1), 'MEMBRE'),
    ]

    count = 0
    for email, equipe_nom, date_debut, role in historique_data:
        operateur = operateurs.get(email)
        equipe = equipes.get(equipe_nom)

        if not operateur or not equipe:
            continue

        _, created = HistoriqueEquipeOperateur.objects.get_or_create(
            operateur=operateur,
            equipe=equipe,
            date_debut=date_debut,
            defaults={'role_dans_equipe': role}
        )

        if created:
            count += 1

    print(f"   ✅ {count} entrées d'historique créées")


def create_absences(operateurs, users):
    """Crée les absences."""
    print("\n🏖️  Création des absences...")

    admin = users.get('admin@greensig.ma')

    absences_data = [
        {
            'email': 'karim.benjelloun@greensig.ma',
            'type_absence': TypeAbsence.CONGE,
            'date_debut': date(2024, 12, 5),
            'date_fin': date(2024, 12, 15),
            'statut': StatutAbsence.VALIDEE,
            'motif': 'Congés annuels',
            'validee_par': admin,
            'commentaire': 'Approuvé'
        },
        {
            'email': 'youssef.amrani@greensig.ma',
            'type_absence': TypeAbsence.FORMATION,
            'date_debut': date(2024, 12, 20),
            'date_fin': date(2024, 12, 22),
            'statut': StatutAbsence.DEMANDEE,
            'motif': 'Formation sécurité',
            'validee_par': None,
            'commentaire': ''
        },
        {
            'email': 'fatima.alaoui@greensig.ma',
            'type_absence': TypeAbsence.MALADIE,
            'date_debut': date(2024, 11, 28),
            'date_fin': date(2024, 11, 30),
            'statut': StatutAbsence.VALIDEE,
            'motif': 'Arrêt maladie',
            'validee_par': admin,
            'commentaire': 'Bon rétablissement'
        }
    ]

    count = 0
    for data in absences_data:
        email = data.pop('email')
        operateur = operateurs.get(email)

        if not operateur:
            print(f"   ⚠️  Opérateur non trouvé: {email}")
            continue

        # Vérifier si absence existe déjà (même période)
        exists = Absence.objects.filter(
            operateur=operateur,
            date_debut=data['date_debut'],
            date_fin=data['date_fin']
        ).exists()

        if not exists:
            absence = Absence(operateur=operateur, **data)
            absence.save()
            count += 1

    print(f"   ✅ {count} absences créées")


def print_summary():
    """Affiche un résumé des données créées."""
    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ DES DONNÉES")
    print("=" * 60)

    print(f"\n👥 Utilisateurs: {Utilisateur.objects.count()}")
    print(f"   - Admins: {Utilisateur.objects.filter(type_utilisateur=TypeUtilisateur.ADMIN).count()}")
    print(f"   - Opérateurs: {Utilisateur.objects.filter(type_utilisateur=TypeUtilisateur.OPERATEUR).count()}")
    print(f"   - Clients: {Utilisateur.objects.filter(type_utilisateur=TypeUtilisateur.CLIENT).count()}")

    print(f"\n🏢 Clients: {Client.objects.count()}")
    print(f"🔧 Opérateurs: {Operateur.objects.count()}")
    print(f"👷 Équipes: {Equipe.objects.count()}")
    print(f"🎓 Compétences attribuées: {CompetenceOperateur.objects.count()}")
    print(f"🏖️  Absences: {Absence.objects.count()}")
    print(f"📜 Historique équipes: {HistoriqueEquipeOperateur.objects.count()}")

    print("\n" + "=" * 60)
    print("🔑 IDENTIFIANTS DE CONNEXION")
    print("=" * 60)
    print(f"\n   Mot de passe par défaut: {DEFAULT_PASSWORD}")
    print("\n   Comptes disponibles:")
    for user in Utilisateur.objects.filter(is_superuser=False).order_by('type_utilisateur', 'email'):
        print(f"   - {user.email} ({user.get_type_utilisateur_display()})")

    print("\n" + "=" * 60)


def main():
    """Fonction principale."""
    print("\n" + "=" * 60)
    print("🌿 GREENSIG - Population de la base de données utilisateurs")
    print("=" * 60)

    # Vérification des prérequis
    ensure_roles_and_competences()

    # Nettoyage optionnel
    response = input("\n⚠️  Voulez-vous nettoyer les données existantes ? (o/N): ")
    if response.lower() == 'o':
        clear_existing_data()

    # Création des données
    users = create_utilisateurs()
    create_client(users)
    operateurs = create_operateurs(users)
    assign_competences(operateurs)
    equipes = create_equipes(operateurs)
    create_historique_equipes(operateurs, equipes)
    create_absences(operateurs, users)

    # Résumé
    print_summary()

    print("\n✅ Population terminée avec succès!")


if __name__ == '__main__':
    main()
