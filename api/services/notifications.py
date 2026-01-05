"""
Service de notifications pour GreenSIG
Utilise Django Channels pour envoyer des notifications temps reel via WebSocket.

Architecture:
- Django declenche des evenements (signals, views)
- NotificationService cree la notification en base et l'envoie via WebSocket
- Frontend React recoit via WebSocket natif
"""

import logging
from typing import List, Optional, Union
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


class NotificationTypes:
    """Constantes pour les types de notification"""

    # Taches
    TACHE_CREEE = 'tache_creee'
    TACHE_ASSIGNEE = 'tache_assignee'
    TACHE_MODIFIEE = 'tache_modifiee'
    TACHE_TERMINEE = 'tache_terminee'
    TACHE_EN_RETARD = 'tache_en_retard'
    TACHE_ANNULEE = 'tache_annulee'
    TACHE_VALIDEE = 'tache_validee'
    TACHE_REJETEE = 'tache_rejetee'

    # Reclamations
    RECLAMATION_CREEE = 'reclamation_creee'
    RECLAMATION_URGENTE = 'reclamation_urgente'
    RECLAMATION_PRISE_EN_COMPTE = 'reclamation_prise_en_compte'
    RECLAMATION_RESOLUE = 'reclamation_resolue'
    RECLAMATION_CLOTUREE = 'reclamation_cloturee'

    # Absences
    ABSENCE_DEMANDEE = 'absence_demandee'
    ABSENCE_VALIDEE = 'absence_validee'
    ABSENCE_REFUSEE = 'absence_refusee'

    # Equipes
    EQUIPE_MEMBRE_AJOUTE = 'equipe_membre_ajoute'
    EQUIPE_MEMBRE_RETIRE = 'equipe_membre_retire'

    # Sites
    SITE_ASSIGNE = 'site_assigne'
    SITE_RETIRE = 'site_retire'
    SITE_CREE = 'site_cree'
    SITE_MODIFIE = 'site_modifie'


class NotificationService:
    """
    Service centralise pour l'envoi de notifications via Django Channels.

    Usage:
        from api.services.notifications import NotificationService

        # Notifier la creation d'une tache
        NotificationService.notify_tache_creee(tache)

        # Notification personnalisee
        NotificationService.send(
            type_notification='info',
            titre='Titre',
            message='Message',
            recipients=[user.id],
            data={'key': 'value'}
        )
    """

    @staticmethod
    def _get_channel_layer():
        """Recupere le channel layer pour envoyer des messages WebSocket."""
        return get_channel_layer()

    @staticmethod
    def _get_user_group_name(user_id: int) -> str:
        """Retourne le nom du groupe WebSocket pour un utilisateur."""
        return f"notifications_user_{user_id}"

    @staticmethod
    def send(
        type_notification: str,
        titre: str,
        message: str,
        recipients: List[Union[int, 'Utilisateur']],
        data: dict = None,
        priorite: str = 'normal',
        acteur: Optional[Union[int, 'Utilisateur']] = None
    ) -> bool:
        """
        Envoie une notification a un ou plusieurs utilisateurs.

        Args:
            type_notification: Type de notification (voir NotificationTypes)
            titre: Titre de la notification
            message: Contenu de la notification
            recipients: Liste des IDs utilisateurs ou instances Utilisateur
            data: Donnees supplementaires (IDs, liens, etc.)
            priorite: low, normal, high, urgent
            acteur: Utilisateur qui a declenche la notification

        Returns:
            True si au moins une notification a ete envoyee
        """
        # logger.debug(f"NotificationService.send: type={type_notification} recipients={recipients}")

        from api.models import Notification
        from api_users.models import Utilisateur

        if not recipients:
            logger.warning("Aucun destinataire pour la notification")
            return False

        data = data or {}
        channel_layer = NotificationService._get_channel_layer()
        sent_count = 0

        # Recuperer l'acteur si c'est un ID
        acteur_instance = None
        if acteur:
            if isinstance(acteur, int):
                try:
                    acteur_instance = Utilisateur.objects.get(id=acteur)
                except Utilisateur.DoesNotExist:
                    pass
            else:
                acteur_instance = acteur

        for recipient in recipients:
            try:
                # Recuperer l'ID utilisateur
                if hasattr(recipient, 'id'):
                    user_id = recipient.id
                else:
                    user_id = recipient

                # Recuperer l'utilisateur
                try:
                    user = Utilisateur.objects.get(id=user_id, actif=True)
                except Utilisateur.DoesNotExist:
                    logger.warning(f"Utilisateur {user_id} non trouve ou inactif")
                    continue

                # Creer la notification en base
                notification = Notification.objects.create(
                    destinataire=user,
                    type_notification=type_notification,
                    titre=titre,
                    message=message,
                    priorite=priorite,
                    data=data,
                    acteur=acteur_instance,
                )

                # Envoyer via WebSocket
                group_name = NotificationService._get_user_group_name(user_id)
                try:
                    async_to_sync(channel_layer.group_send)(
                        group_name,
                        {
                            'type': 'notification_message',
                            'notification': notification.to_websocket_payload(),
                        }
                    )
                    logger.info(f"[DEBUG-NOTIF-WS] Notification envoyee via WebSocket a {user.email}: {titre}")
                    sent_count += 1
                except Exception as e:
                    # L'utilisateur n'est peut-etre pas connecte
                    logger.info(f"[DEBUG-NOTIF-WS] WebSocket NON DISPONIBLE pour {user.email} (mais creee en base): {e}")
                    sent_count += 1  # La notification est quand meme creee en base

            except Exception as e:
                logger.error(f"Erreur envoi notification a {recipient}: {e}")

        return sent_count > 0

    # =========================================================================
    # NOTIFICATIONS TACHES
    # =========================================================================

    @classmethod
    def notify_tache_creee(cls, tache: 'Tache', createur: Optional['Utilisateur'] = None):
        """
        Notifier la creation d'une nouvelle tache.
        Destinataires: Superviseur du site, chefs des equipes assignees
        """
        # Eviter les doublons au cas ou le signal m2m_changed serait declenche plusieurs fois
        if tache.notifiee and getattr(tache, '_already_notified_in_request', False):
            return
        
        tache._already_notified_in_request = True
        
        destinataires = cls._get_tache_destinataires(tache, include_admins=True)

        if not destinataires:
            logger.warning(f"[NOTIF] Aucun destinataire pour tache #{tache.id}")
            return

        site_nom = cls._get_tache_site_nom(tache)
        tache_titre = cls._get_tache_titre(tache)
        priorite_label = cls._get_priorite_label(tache.priorite)

        cls.send(
            type_notification=NotificationTypes.TACHE_CREEE,
            titre=f"Nouvelle tache: {tache_titre}",
            message=f"Site: {site_nom} - Priorite: {priorite_label}",
            recipients=destinataires,
            data={
                'tache_id': tache.id,
                'titre': tache_titre,
                'site': site_nom,
                'type_tache': tache.id_type_tache.nom_tache if tache.id_type_tache else '',
                'priorite': tache.priorite,
                'date_debut': str(tache.date_debut_planifiee) if tache.date_debut_planifiee else '',
                'date_fin': str(tache.date_fin_planifiee) if tache.date_fin_planifiee else '',
            },
            priorite='high' if tache.priorite >= 4 else 'normal',
            acteur=createur
        )

    @classmethod
    def notify_tache_assignee(cls, tache: 'Tache', operateurs: List['Operateur']):
        """
        Notifier les operateurs de leur assignation a une tache.
        Note: Les operateurs n'ont pas de compte utilisateur, donc on notifie leurs superviseurs.
        """
        superviseurs_ids = set()
        for op in operateurs:
            if op.superviseur and op.superviseur.utilisateur:
                superviseurs_ids.add(op.superviseur.utilisateur.id)

        if not superviseurs_ids:
            return

        site_nom = cls._get_tache_site_nom(tache)
        tache_titre = cls._get_tache_titre(tache)

        cls.send(
            type_notification=NotificationTypes.TACHE_ASSIGNEE,
            titre=f"Operateurs assignes: {tache_titre}",
            message=f"{len(operateurs)} operateur(s) assigne(s) - {site_nom}",
            recipients=list(superviseurs_ids),
            data={
                'tache_id': tache.id,
                'titre': tache_titre,
                'site': site_nom,
                'operateurs': [f"{op.prenom} {op.nom}" for op in operateurs],
                'date_debut': str(tache.date_debut_planifiee) if tache.date_debut_planifiee else '',
            }
        )

    @classmethod
    def notify_tache_terminee(cls, tache: 'Tache', createur: Optional['Utilisateur'] = None):
        """
        Notifier la fin d'une tache.
        Destinataires: Clients de la structure, superviseur du site
        """
        destinataires = []

        # Clients de la structure
        if tache.id_structure_client:
            clients = tache.id_structure_client.utilisateurs.select_related('utilisateur').all()
            for client in clients:
                if client.utilisateur and client.utilisateur.actif:
                    destinataires.append(client.utilisateur.id)

        # Superviseur du site
        site = cls._get_tache_site(tache)
        if site and site.superviseur and site.superviseur.utilisateur:
            destinataires.append(site.superviseur.utilisateur.id)

        if not destinataires:
            return

        tache_titre = cls._get_tache_titre(tache)

        cls.send(
            type_notification=NotificationTypes.TACHE_TERMINEE,
            titre=f"Tache terminee: {tache_titre}",
            message=f"Site: {site.nom_site if site else 'N/A'}",
            recipients=list(set(destinataires)),
            data={
                'tache_id': tache.id,
                'titre': tache_titre,
                'site': site.nom_site if site else '',
                'date_fin_reelle': str(tache.date_fin_reelle) if tache.date_fin_reelle else '',
            },
            acteur=createur
        )

    @classmethod
    def notify_tache_en_retard(cls, tache: 'Tache'):
        """
        Notifier qu'une tache est en retard.
        Destinataires: Superviseur, admins
        """
        destinataires = cls._get_tache_destinataires(tache, include_admins=True)

        if not destinataires:
            return

        site_nom = cls._get_tache_site_nom(tache)
        tache_titre = cls._get_tache_titre(tache)
        jours_retard = cls._calculer_jours_retard(tache)

        cls.send(
            type_notification=NotificationTypes.TACHE_EN_RETARD,
            titre=f"Tache en retard: {tache_titre}",
            message=f"{jours_retard} jour(s) de retard - {site_nom}",
            recipients=destinataires,
            data={
                'tache_id': tache.id,
                'titre': tache_titre,
                'site': site_nom,
                'date_fin_prevue': str(tache.date_fin_planifiee) if tache.date_fin_planifiee else '',
                'jours_retard': jours_retard,
            },
            priorite='urgent'
        )

    @classmethod
    def notify_tache_validee(cls, tache: 'Tache', etat_validation: str, valideur: Optional['Utilisateur'] = None, commentaire: str = ''):
        """
        Notifier la validation ou le rejet d'une tâche.
        Destinataires: Superviseur du site, clients de la structure

        Args:
            tache: La tâche validée/rejetée
            etat_validation: 'VALIDEE' ou 'REJETEE'
            valideur: L'utilisateur qui a validé
            commentaire: Commentaire de validation
        """
        destinataires = []

        # Superviseur du site
        site = cls._get_tache_site(tache)
        if site and site.superviseur and site.superviseur.utilisateur:
            if site.superviseur.utilisateur.actif:
                destinataires.append(site.superviseur.utilisateur.id)

        # Clients de la structure
        if tache.id_structure_client:
            clients = tache.id_structure_client.utilisateurs.select_related('utilisateur').all()
            for client in clients:
                if client.utilisateur and client.utilisateur.actif:
                    destinataires.append(client.utilisateur.id)

        if not destinataires:
            return

        tache_titre = cls._get_tache_titre(tache)
        site_nom = cls._get_tache_site_nom(tache)

        is_validated = etat_validation == 'VALIDEE'
        notif_type = NotificationTypes.TACHE_VALIDEE if is_validated else NotificationTypes.TACHE_REJETEE

        titre = f"Tâche {'validée' if is_validated else 'rejetée'}: {tache_titre}"
        message = f"Site: {site_nom}"
        if commentaire:
            message += f" - {commentaire[:100]}"

        cls.send(
            type_notification=notif_type,
            titre=titre,
            message=message,
            recipients=list(set(destinataires)),
            data={
                'tache_id': tache.id,
                'titre': tache_titre,
                'site': site_nom,
                'etat_validation': etat_validation,
                'commentaire': commentaire,
                'valideur_nom': f"{valideur.prenom} {valideur.nom}" if valideur else '',
            },
            priorite='high' if not is_validated else 'normal',
            acteur=valideur
        )

    # =========================================================================
    # NOTIFICATIONS RECLAMATIONS
    # =========================================================================

    @classmethod
    def notify_reclamation_creee(cls, reclamation: 'Reclamation', acteur: Optional['Utilisateur'] = None):
        """
        Notifier la creation d'une reclamation.
        Destinataires: Superviseur du site, admins si urgence elevee
        """
        destinataires = []

        # Superviseur du site
        if reclamation.site and reclamation.site.superviseur:
            sup = reclamation.site.superviseur
            if sup.utilisateur and sup.utilisateur.actif:
                destinataires.append(sup.utilisateur.id)
                logger.info(f"[DEBUG-NOTIF] Reclamation #{reclamation.id}: Ajout superviseur site {sup.utilisateur.id}")

        # Toujours ajouter les admins
        admins = cls._get_admin_ids()
        destinataires.extend(admins)
        logger.info(f"[DEBUG-NOTIF] Reclamation #{reclamation.id}: Ajout admins {admins}")

        is_urgent = reclamation.urgence and reclamation.urgence.ordre >= 4
        
        final_recipients = list(set(destinataires))
        logger.info(f"[DEBUG-NOTIF] Reclamation #{reclamation.id}: Destinataires finaux={final_recipients}")

        if not final_recipients:
            logger.info(f"[DEBUG-NOTIF] Reclamation #{reclamation.id}: AUCUN DESTINATAIRE")
            return

        notif_type = NotificationTypes.RECLAMATION_URGENTE if is_urgent else NotificationTypes.RECLAMATION_CREEE

        cls.send(
            type_notification=notif_type,
            titre=f"Reclamation {reclamation.numero_reclamation}",
            message=f"{reclamation.type_reclamation.nom_reclamation if reclamation.type_reclamation else 'N/A'} - {reclamation.site.nom_site if reclamation.site else 'N/A'}",
            recipients=final_recipients,
            data={
                'reclamation_id': reclamation.id,
                'numero': reclamation.numero_reclamation,
                'description': (reclamation.description or '')[:150],
                'type': reclamation.type_reclamation.nom_reclamation if reclamation.type_reclamation else '',
                'urgence': reclamation.urgence.niveau_urgence if reclamation.urgence else '',
                'site': reclamation.site.nom_site if reclamation.site else '',
            },
            priorite='urgent' if is_urgent else 'high',
            acteur=acteur or reclamation.createur
        )

    @classmethod
    def notify_reclamation_statut_change(cls, reclamation: 'Reclamation', ancien_statut: str, acteur: Optional['Utilisateur'] = None):
        """Notifier un changement de statut de reclamation"""
        nouveau_statut = reclamation.statut

        # Determiner le type de notification et les destinataires
        if nouveau_statut == 'PRISE_EN_COMPTE':
            notif_type = NotificationTypes.RECLAMATION_PRISE_EN_COMPTE
            destinataires = [reclamation.createur.id] if reclamation.createur else []
            titre = "Reclamation prise en compte"
        elif nouveau_statut == 'EN_COURS':
            notif_type = NotificationTypes.RECLAMATION_PRISE_EN_COMPTE  # Can use same icon/logic or add new type
            destinataires = [reclamation.createur.id] if reclamation.createur else []
            titre = "Reclamation en cours de traitement"
        elif nouveau_statut == 'RESOLUE':
            notif_type = NotificationTypes.RECLAMATION_RESOLUE
            destinataires = []
            if reclamation.createur:
                destinataires.append(reclamation.createur.id)
            if reclamation.structure_client:
                for client_profile in reclamation.structure_client.utilisateurs.select_related('utilisateur').all():
                    if client_profile.utilisateur and client_profile.utilisateur.actif:
                        destinataires.append(client_profile.utilisateur.id)
            titre = "Reclamation resolue"
        elif nouveau_statut == 'EN_ATTENTE_VALIDATION_CLOTURE':
            notif_type = NotificationTypes.RECLAMATION_RESOLUE
            destinataires = [reclamation.createur.id] if reclamation.createur else []
            titre = "Cloture de reclamation a valider"
        elif nouveau_statut == 'CLOTUREE':
            notif_type = NotificationTypes.RECLAMATION_CLOTUREE
            destinataires = [reclamation.createur.id] if reclamation.createur else []
            titre = "Reclamation cloturee"
        elif nouveau_statut == 'REJETEE':
            notif_type = NotificationTypes.RECLAMATION_CLOTUREE  # Use a neutral/gray icon
            destinataires = [reclamation.createur.id] if reclamation.createur else []
            titre = "Reclamation rejetee"
        else:
            return

        if not destinataires:
            return

        cls.send(
            type_notification=notif_type,
            titre=f"{titre}: {reclamation.numero_reclamation}",
            message=f"Statut: {ancien_statut} -> {nouveau_statut}",
            recipients=list(set(destinataires)),
            data={
                'reclamation_id': reclamation.id,
                'numero': reclamation.numero_reclamation,
                'ancien_statut': ancien_statut,
                'nouveau_statut': nouveau_statut,
                'site': reclamation.site.nom_site if reclamation.site else '',
            },
            acteur=acteur
        )

    # =========================================================================
    # NOTIFICATIONS ABSENCES
    # =========================================================================

    @classmethod
    def notify_absence_demandee(cls, absence: 'Absence', acteur: Optional['Utilisateur'] = None):
        """
        Notifier une nouvelle demande d'absence.
        Destinataires: Admins
        """
        admins = cls._get_admin_ids()
        if not admins:
            return

        cls.send(
            type_notification=NotificationTypes.ABSENCE_DEMANDEE,
            titre=f"Nouvelle demande d'absence",
            message=f"Operateur: {absence.operateur.nom} {absence.operateur.prenom}",
            recipients=admins,
            data={
                'absence_id': absence.id,
                'operateur_nom': f"{absence.operateur.nom} {absence.operateur.prenom}",
                'date_debut': str(absence.date_debut),
                'date_fin': str(absence.date_fin),
            },
            acteur=acteur
        )

    @classmethod
    def notify_absence_validee(cls, absence: 'Absence', acteur: Optional['Utilisateur'] = None):
        """
        Notifier la validation d'une absence.
        Destinataires: Superviseur de l'operateur
        """
        destinataires = []
        if absence.operateur.superviseur and absence.operateur.superviseur.utilisateur:
            destinataires.append(absence.operateur.superviseur.utilisateur.id)

        if not destinataires:
            return

        cls.send(
            type_notification=NotificationTypes.ABSENCE_VALIDEE,
            titre=f"Absence validee",
            message=f"Operateur: {absence.operateur.nom} {absence.operateur.prenom}",
            recipients=destinataires,
            data={
                'absence_id': absence.id,
                'operateur_nom': f"{absence.operateur.nom} {absence.operateur.prenom}",
                'date_debut': str(absence.date_debut),
                'date_fin': str(absence.date_fin),
            },
            acteur=acteur
        )

    @classmethod
    def notify_absence_refusee(cls, absence: 'Absence', motif: str = '', acteur: Optional['Utilisateur'] = None):
        """
        Notifier le refus d'une absence.
        Destinataires: Superviseur de l'operateur
        """
        destinataires = []
        if absence.operateur.superviseur and absence.operateur.superviseur.utilisateur:
            destinataires.append(absence.operateur.superviseur.utilisateur.id)

        if not destinataires:
            return

        cls.send(
            type_notification=NotificationTypes.ABSENCE_REFUSEE,
            titre=f"Absence refusee",
            message=f"Motif: {motif}",
            recipients=destinataires,
            data={
                'absence_id': absence.id,
                'operateur_nom': f"{absence.operateur.nom} {absence.operateur.prenom}",
                'motif': motif,
            },
            acteur=acteur
        )

    # =========================================================================
    # HELPERS
    # =========================================================================

    @classmethod
    def _get_tache_destinataires(cls, tache: 'Tache', include_admins: bool = False) -> List[int]:
        """Recuperer les destinataires pour une notification de tache"""
        destinataires = []

        # Superviseur du site (via les objets lies)
        site = cls._get_tache_site(tache)
        if site and site.superviseur and site.superviseur.utilisateur:
            if site.superviseur.utilisateur.actif:
                destinataires.append(site.superviseur.utilisateur.id)

        # Chefs des equipes assignees (via M2M equipes)
        for equipe in tache.equipes.all():
            if equipe.chef_equipe and equipe.chef_equipe.superviseur:
                sup = equipe.chef_equipe.superviseur
                if sup.utilisateur and sup.utilisateur.actif:
                    destinataires.append(sup.utilisateur.id)

        # Legacy: equipe unique
        if tache.id_equipe and tache.id_equipe.chef_equipe:
            chef = tache.id_equipe.chef_equipe
            if chef.superviseur and chef.superviseur.utilisateur:
                if chef.superviseur.utilisateur.actif:
                    destinataires.append(chef.superviseur.utilisateur.id)

        if include_admins:
            destinataires.extend(cls._get_admin_ids())

        return list(set(destinataires))

    @classmethod
    def _get_tache_site(cls, tache: 'Tache'):
        """Recuperer le site d'une tache via ses objets"""
        objet = tache.objets.select_related('site__superviseur__utilisateur').first()
        if objet and objet.site:
            return objet.site
        return None

    @classmethod
    def _get_tache_site_nom(cls, tache: 'Tache') -> str:
        """Recuperer le nom du site d'une tache"""
        site = cls._get_tache_site(tache)
        return site.nom_site if site else ''

    @classmethod
    def _get_tache_titre(cls, tache: 'Tache') -> str:
        """Recuperer le titre d'une tache (via son type)"""
        return tache.id_type_tache.nom_tache if tache.id_type_tache else 'Tache'

    @classmethod
    def _get_admin_ids(cls) -> List[int]:
        """Recuperer les IDs des utilisateurs admin actifs"""
        from django.apps import apps
        UtilisateurRole = apps.get_model('api_users', 'UtilisateurRole')

        admin_ids = UtilisateurRole.objects.filter(
            role__nom_role='ADMIN',
            utilisateur__actif=True
        ).values_list('utilisateur_id', flat=True)

        return list(admin_ids)

    @classmethod
    def _calculer_jours_retard(cls, tache: 'Tache') -> int:
        """Calculer le nombre de jours de retard d'une tache"""
        from django.utils import timezone

        if not tache.date_fin_planifiee:
            return 0

        today = timezone.now().date()
        if tache.date_fin_planifiee < today:
            return (today - tache.date_fin_planifiee).days
        return 0

    @classmethod
    def _get_priorite_label(cls, priorite: int) -> str:
        """Retourne le label de priorite"""
        labels = {
            1: 'Tres basse',
            2: 'Basse',
            3: 'Normale',
            4: 'Haute',
            5: 'Urgente',
        }
        return labels.get(priorite, 'Normale')

    # =========================================================================
    # NOTIFICATIONS SITES
    # =========================================================================

    @classmethod
    def notify_site_assigne(cls, site: 'Site', superviseur: 'Superviseur', acteur: Optional['Utilisateur'] = None):
        """
        Notifier un superviseur qu'un site lui a ete assigne.
        Destinataires: Le superviseur concerne
        """
        if not superviseur or not superviseur.utilisateur:
            logger.warning(f"[NOTIF] Site #{site.id}: Superviseur sans compte utilisateur")
            return

        if not superviseur.utilisateur.actif:
            logger.warning(f"[NOTIF] Site #{site.id}: Superviseur inactif")
            return

        structure_nom = site.structure_client.nom if site.structure_client else 'N/A'

        cls.send(
            type_notification=NotificationTypes.SITE_ASSIGNE,
            titre=f"Nouveau site assigne: {site.nom_site}",
            message=f"Organisation: {structure_nom} - Superficie: {site.superficie_totale or 'N/A'} m²",
            recipients=[superviseur.utilisateur.id],
            data={
                'site_id': site.id,
                'site_nom': site.nom_site,
                'site_code': site.code_site,
                'structure_client': structure_nom,
                'superficie': site.superficie_totale,
                'adresse': site.adresse or '',
            },
            priorite='high',
            acteur=acteur
        )
        logger.info(f"[NOTIF] Site #{site.id} assigne au superviseur {superviseur.utilisateur.email}")

    @classmethod
    def notify_site_retire(cls, site: 'Site', superviseur: 'Superviseur', acteur: Optional['Utilisateur'] = None):
        """
        Notifier un superviseur qu'un site lui a ete retire.
        Destinataires: Le superviseur concerne
        """
        if not superviseur or not superviseur.utilisateur:
            return

        if not superviseur.utilisateur.actif:
            return

        cls.send(
            type_notification=NotificationTypes.SITE_RETIRE,
            titre=f"Site retire: {site.nom_site}",
            message=f"Vous n'etes plus responsable de ce site",
            recipients=[superviseur.utilisateur.id],
            data={
                'site_id': site.id,
                'site_nom': site.nom_site,
                'site_code': site.code_site,
            },
            priorite='normal',
            acteur=acteur
        )
        logger.info(f"[NOTIF] Site #{site.id} retire du superviseur {superviseur.utilisateur.email}")

    @classmethod
    def notify_sites_assignes_bulk(cls, sites: List['Site'], superviseur: 'Superviseur', acteur: Optional['Utilisateur'] = None):
        """
        Notifier un superviseur que plusieurs sites lui ont ete assignes.
        Destinataires: Le superviseur concerne
        """
        if not superviseur or not superviseur.utilisateur:
            logger.warning(f"[NOTIF] Assignation bulk: Superviseur sans compte utilisateur")
            return

        if not superviseur.utilisateur.actif:
            return

        if not sites:
            return

        sites_noms = [s.nom_site for s in sites]
        sites_ids = [s.id for s in sites]

        cls.send(
            type_notification=NotificationTypes.SITE_ASSIGNE,
            titre=f"{len(sites)} site(s) assigne(s)",
            message=f"Sites: {', '.join(sites_noms[:3])}{'...' if len(sites_noms) > 3 else ''}",
            recipients=[superviseur.utilisateur.id],
            data={
                'sites_ids': sites_ids,
                'sites_noms': sites_noms,
                'count': len(sites),
            },
            priorite='high',
            acteur=acteur
        )
        logger.info(f"[NOTIF] {len(sites)} sites assignes au superviseur {superviseur.utilisateur.email}")
