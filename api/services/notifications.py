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
    TACHE_ANNULEE = 'tache_annulee'
    TACHE_VALIDEE = 'tache_validee'
    TACHE_REJETEE = 'tache_rejetee'

    # Reclamations
    RECLAMATION_CREEE = 'reclamation_creee'
    RECLAMATION_URGENTE = 'reclamation_urgente'
    RECLAMATION_PRISE_EN_COMPTE = 'reclamation_prise_en_compte'
    RECLAMATION_RESOLUE = 'reclamation_resolue'
    RECLAMATION_CLOTUREE = 'reclamation_cloturee'
    RECLAMATION_RAPPEL_CLOTURE = 'reclamation_rappel_cloture'
    RECLAMATION_AUTO_CLOTURE = 'reclamation_auto_cloture'

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

    # Satisfaction
    SATISFACTION_EVALUEE = 'satisfaction_evaluee'


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
        acteur: Optional[Union[int, 'Utilisateur']] = None,
        use_celery: bool = False
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
            use_celery: Si True, envoie en arriere-plan via Celery (recommande pour > 5 destinataires)

        Returns:
            True si au moins une notification a ete envoyee
        """
        if not recipients:
            logger.warning("Aucun destinataire pour la notification")
            return False

        # Normaliser les IDs recipients
        recipient_ids = []
        for r in recipients:
            if hasattr(r, 'id'):
                recipient_ids.append(r.id)
            else:
                recipient_ids.append(r)

        # Si beaucoup de destinataires ou use_celery demande, utiliser Celery
        if use_celery or len(recipient_ids) > 5:
            try:
                from api.tasks import send_notification_async
                acteur_id = acteur.id if hasattr(acteur, 'id') else acteur
                send_notification_async.delay(
                    user_ids=recipient_ids,
                    message=message,
                    notification_type=type_notification,
                    title=titre,
                    data=data
                )
                logger.info(f"[NOTIF] Envoi async via Celery: {len(recipient_ids)} destinataires")
                return True
            except Exception as e:
                logger.warning(f"Celery non disponible, fallback synchrone: {e}")
                # Continuer en mode synchrone si Celery n'est pas disponible

        # Mode synchrone optimise avec bulk_create
        return NotificationService._send_batch_sync(
            type_notification=type_notification,
            titre=titre,
            message=message,
            recipient_ids=recipient_ids,
            data=data,
            priorite=priorite,
            acteur=acteur
        )

    @staticmethod
    def _send_batch_sync(
        type_notification: str,
        titre: str,
        message: str,
        recipient_ids: List[int],
        data: dict = None,
        priorite: str = 'normal',
        acteur: Optional[Union[int, 'Utilisateur']] = None
    ) -> bool:
        """
        Envoi synchrone optimise avec bulk_create pour les notifications en base.
        """
        from api.models import Notification
        from api_users.models import Utilisateur

        data = data or {}
        channel_layer = NotificationService._get_channel_layer()

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

        # Recuperer tous les utilisateurs actifs en une seule requete
        users = Utilisateur.objects.filter(
            id__in=recipient_ids,
            actif=True
        ).only('id', 'email', 'prenom', 'nom')

        if not users.exists():
            logger.warning(f"Aucun utilisateur actif parmi {recipient_ids}")
            return False

        # Creer toutes les notifications en batch
        notifications_to_create = []
        user_map = {}
        for user in users:
            notification = Notification(
                destinataire=user,
                type_notification=type_notification,
                titre=titre,
                message=message,
                priorite=priorite,
                data=data,
                acteur=acteur_instance,
            )
            notifications_to_create.append(notification)
            user_map[user.id] = user

        # Bulk create - beaucoup plus rapide que des creates individuels
        created_notifications = Notification.objects.bulk_create(notifications_to_create)
        logger.info(f"[NOTIF] {len(created_notifications)} notifications creees en batch")

        # Envoyer via WebSocket (toujours individuel car chaque user a son groupe)
        sent_count = 0
        for notification in created_notifications:
            user = notification.destinataire
            group_name = NotificationService._get_user_group_name(user.id)
            try:
                async_to_sync(channel_layer.group_send)(
                    group_name,
                    {
                        'type': 'notification_message',
                        'notification': notification.to_websocket_payload(),
                    }
                )
                sent_count += 1
            except Exception as e:
                # L'utilisateur n'est peut-etre pas connecte - normal
                sent_count += 1  # La notification est quand meme creee en base

        return sent_count > 0

    @staticmethod
    def send_bulk(
        notifications_data: List[dict],
        use_celery: bool = True
    ) -> int:
        """
        Envoie plusieurs notifications differentes en une seule operation.
        Utile pour envoyer des notifications personnalisees a differents utilisateurs.

        Args:
            notifications_data: Liste de dicts avec les cles:
                - type_notification
                - titre
                - message
                - recipient_id (int)
                - data (optionnel)
                - priorite (optionnel, defaut: 'normal')
                - acteur_id (optionnel)
            use_celery: Si True, traite en arriere-plan via Celery

        Returns:
            Nombre de notifications creees
        """
        if not notifications_data:
            return 0

        # Si Celery demande, deleguer a une tache
        if use_celery:
            try:
                from api.tasks import send_bulk_notifications_async
                send_bulk_notifications_async.delay(notifications_data)
                logger.info(f"[NOTIF] Envoi bulk async via Celery: {len(notifications_data)} notifications")
                return len(notifications_data)
            except Exception as e:
                logger.warning(f"Celery non disponible pour bulk, fallback synchrone: {e}")

        # Mode synchrone avec bulk_create
        from api.models import Notification
        from api_users.models import Utilisateur

        # Collecter tous les IDs necessaires
        recipient_ids = [n['recipient_id'] for n in notifications_data if 'recipient_id' in n]
        acteur_ids = [n['acteur_id'] for n in notifications_data if n.get('acteur_id')]

        # Charger tous les utilisateurs en une requete
        all_user_ids = set(recipient_ids + acteur_ids)
        users_map = {u.id: u for u in Utilisateur.objects.filter(id__in=all_user_ids)}

        notifications_to_create = []
        for notif_data in notifications_data:
            recipient_id = notif_data.get('recipient_id')
            recipient = users_map.get(recipient_id)
            if not recipient or not recipient.actif:
                continue

            acteur = users_map.get(notif_data.get('acteur_id')) if notif_data.get('acteur_id') else None

            notification = Notification(
                destinataire=recipient,
                type_notification=notif_data.get('type_notification', 'info'),
                titre=notif_data.get('titre', ''),
                message=notif_data.get('message', ''),
                priorite=notif_data.get('priorite', 'normal'),
                data=notif_data.get('data', {}),
                acteur=acteur,
            )
            notifications_to_create.append(notification)

        if notifications_to_create:
            created = Notification.objects.bulk_create(notifications_to_create)
            logger.info(f"[NOTIF] {len(created)} notifications creees en bulk")

            # Envoyer via WebSocket
            channel_layer = NotificationService._get_channel_layer()
            for notification in created:
                group_name = NotificationService._get_user_group_name(notification.destinataire_id)
                try:
                    async_to_sync(channel_layer.group_send)(
                        group_name,
                        {
                            'type': 'notification_message',
                            'notification': notification.to_websocket_payload(),
                        }
                    )
                except Exception:
                    pass  # WebSocket non disponible, normal

            return len(created)

        return 0

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
        Destinataires: Clients de la structure, superviseur du site, admins
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

        # Admins
        destinataires.extend(cls._get_admin_ids())

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
        if nouveau_statut == 'EN_COURS':
            notif_type = NotificationTypes.RECLAMATION_PRISE_EN_COMPTE
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
    # NOTIFICATIONS SATISFACTION
    # =========================================================================

    @classmethod
    def notify_satisfaction_evaluee(cls, satisfaction: 'SatisfactionClient', acteur: Optional['Utilisateur'] = None):
        """
        Notifier qu'un client a evalué une reclamation.
        Destinataires: Admins, superviseur du site
        """
        destinataires = []
        reclamation = satisfaction.reclamation

        # Admins
        destinataires.extend(cls._get_admin_ids())

        # Superviseur du site
        if reclamation.site and reclamation.site.superviseur:
            sup = reclamation.site.superviseur
            if sup.utilisateur and sup.utilisateur.actif:
                destinataires.append(sup.utilisateur.id)

        if not destinataires:
            return

        # Emoji pour la note
        note_emoji = '⭐' * satisfaction.note
        note_text = f"{satisfaction.note}/5"

        cls.send(
            type_notification=NotificationTypes.SATISFACTION_EVALUEE,
            titre=f"Evaluation client: {reclamation.numero_reclamation}",
            message=f"Note: {note_text} {note_emoji}",
            recipients=list(set(destinataires)),
            data={
                'reclamation_id': reclamation.id,
                'numero': reclamation.numero_reclamation,
                'satisfaction_id': satisfaction.id,
                'note': satisfaction.note,
                'commentaire': (satisfaction.commentaire or '')[:150],
                'site': reclamation.site.nom_site if reclamation.site else '',
                'evaluateur': f"{acteur.prenom} {acteur.nom}" if acteur else '',
            },
            priorite='normal',
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
