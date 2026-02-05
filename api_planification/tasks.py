"""
Celery tasks for api_planification module.

NOTE: Le systeme de statuts EN_RETARD et EXPIREE a ete supprime.
Les taches restent PLANIFIEE jusqu'a demarrage explicite par l'utilisateur.

Taches restantes:
- invalidate_taches_cache: Invalide le cache des taches (utilitaire)
- export_planning_pdf_async: Export PDF du planning (nouvelle fonctionnalite)
"""

import logging
import os
from datetime import datetime
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)

# Cache key pour la liste des taches
CACHE_KEY_TACHES_LIST = 'taches_list_{user_id}_{params_hash}'
CACHE_TIMEOUT_TACHES = 60  # 1 minute


def invalidate_taches_cache():
    """Invalide le cache de la liste des taches pour tous les utilisateurs."""
    try:
        # Supprimer toutes les cles commencant par 'taches_list_'
        cache.delete_pattern('greensig:taches_list_*')
    except AttributeError:
        # Si delete_pattern n'est pas disponible
        logger.warning("Cache backend doesn't support delete_pattern, skipping cache invalidation")
    except Exception as e:
        logger.warning(f"Failed to invalidate taches cache: {e}")


# ==============================================================================
# TACHES CELERY DESACTIVEES
# ==============================================================================
# Les taches suivantes ont ete supprimees car le systeme de statuts
# EN_RETARD et EXPIREE n'existe plus.
#
# Les taches restent PLANIFIEE jusqu'a ce que l'utilisateur les demarre
# explicitement. Une distribution ne peut pas etre demarree avant sa date
# planifiee.
# ==============================================================================


@shared_task(bind=True, name='api_planification.tasks.refresh_all_task_statuses')
def refresh_all_task_statuses(self):
    """
    DESACTIVEE: Cette tache ne fait plus rien.

    Anciennement: Mettait a jour les statuts EN_RETARD et EXPIREE.
    Maintenant: Le systeme simplifie ne calcule plus automatiquement ces statuts.

    Cette tache est conservee pour eviter les erreurs si elle est encore
    programmee dans Celery Beat, mais elle ne fait rien.
    """
    logger.info("refresh_all_task_statuses: DESACTIVEE (systeme simplifie)")
    return {
        'success': True,
        'message': 'Task disabled - simplified status system',
        'late_distributions': 0,
        'late_tasks': 0,
        'expired_tasks': 0,
        'timestamp': timezone.now().isoformat(),
    }


@shared_task(bind=True, name='api_planification.tasks.update_late_distributions')
def update_late_distributions(self):
    """
    DESACTIVEE: Cette tache ne fait plus rien.

    Anciennement: Marquait les distributions comme EN_RETARD.
    Maintenant: Le statut EN_RETARD n'existe plus.
    """
    logger.info("update_late_distributions: DESACTIVEE (systeme simplifie)")
    return {
        'success': True,
        'message': 'Task disabled - EN_RETARD status removed',
        'updated_distributions': 0,
        'updated_tasks': 0,
    }


@shared_task(bind=True, name='api_planification.tasks.fix_inconsistent_distributions')
def fix_inconsistent_distributions(self):
    """
    DESACTIVEE: Cette tache ne fait plus rien.

    Anciennement: Corrigeait les distributions des taches EXPIREE.
    Maintenant: Le statut EXPIREE n'existe plus.
    """
    logger.info("fix_inconsistent_distributions: DESACTIVEE (systeme simplifie)")
    return {
        'success': True,
        'message': 'Task disabled - EXPIREE status removed',
        'fixed_count': 0,
    }


@shared_task(bind=True, name='api_planification.tasks.mark_expired_tasks')
def mark_expired_tasks(self):
    """
    DESACTIVEE: Cette tache ne fait plus rien.

    Anciennement: Marquait les taches comme EXPIREE.
    Maintenant: Le statut EXPIREE n'existe plus.
    """
    logger.info("mark_expired_tasks: DESACTIVEE (systeme simplifie)")
    return {
        'success': True,
        'message': 'Task disabled - EXPIREE status removed',
        'expired_count': 0,
    }


# ==============================================================================
# EXPORT PDF DU PLANNING
# ==============================================================================

@shared_task(bind=True, name='api_planification.tasks.export_planning_pdf_async')
def export_planning_pdf_async(self, user_id, start_date, end_date, filters=None):
    """
    Genere un PDF du planning pour la periode donnee.

    Args:
        user_id: ID utilisateur (pour filtrage par role et info export)
        start_date: Date debut (YYYY-MM-DD)
        end_date: Date fin (YYYY-MM-DD)
        filters: Dict optionnel {structure_client_id, equipe_id}

    Returns:
        dict: {success, file_path, download_url, filename} ou {success: False, error}
    """
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from io import BytesIO

    from api_users.models import Utilisateur
    from api_planification.models import DistributionCharge

    filters = filters or {}

    try:
        # Recuperer l'utilisateur
        user = Utilisateur.objects.get(pk=user_id)
        user_name = user.get_full_name() or f"{user.prenom} {user.nom}".strip()

        # Determiner le role pour le filtrage
        roles = list(user.roles_utilisateur.values_list('role__nom_role', flat=True))
        is_admin = 'ADMIN' in roles
        is_superviseur = 'SUPERVISEUR' in roles

        # Construire le queryset des distributions
        queryset = DistributionCharge.objects.filter(
            date__gte=start_date,
            date__lte=end_date
        ).select_related(
            'tache',
            'tache__id_type_tache',
            'tache__id_structure_client'
        ).prefetch_related(
            'tache__equipes'
        ).order_by('date', 'heure_debut')

        # Filtrage par role
        if not is_admin:
            if is_superviseur and hasattr(user, 'superviseur_profile'):
                # SUPERVISEUR: seulement ses equipes
                equipes_ids = user.superviseur_profile.equipes_gerees.values_list('id', flat=True)
                queryset = queryset.filter(tache__equipes__id__in=equipes_ids)

        # Filtres additionnels
        if filters.get('structure_client_id'):
            queryset = queryset.filter(tache__id_structure_client_id=filters['structure_client_id'])

        if filters.get('equipe_id'):
            queryset = queryset.filter(tache__equipes__id=filters['equipe_id'])

        # Distinct pour eviter les doublons (ManyToMany)
        queryset = queryset.distinct()

        # Creer le buffer PDF
        buffer = BytesIO()

        # Document PDF (A4 Paysage, marges 1.5cm)
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=1.5*cm,
            leftMargin=1.5*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )

        # Styles
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#2E7D32'),
            spaceAfter=12,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )

        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.grey,
            spaceAfter=20,
            alignment=TA_CENTER
        )

        cell_style = ParagraphStyle(
            'CellStyle',
            parent=styles['Normal'],
            fontSize=8,
            leading=10,
            wordWrap='CJK',
        )

        header_cell_style = ParagraphStyle(
            'HeaderCellStyle',
            parent=styles['Normal'],
            fontSize=9,
            leading=11,
            textColor=colors.whitesmoke,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
        )

        # Contenu du document
        story = []

        # En-tete avec logo si disponible
        try:
            logo_path = os.path.join(settings.BASE_DIR, 'static', 'logo.png')
            if os.path.exists(logo_path):
                logo = Image(logo_path, width=4*cm, height=2*cm)
                header_data = [
                    [Paragraph("PLANNING - GreenSIG", title_style), logo]
                ]
                header_table = Table(header_data, colWidths=[20*cm, 5*cm])
                header_table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                    ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]))
                story.append(header_table)
            else:
                story.append(Paragraph("PLANNING - GreenSIG", title_style))
        except Exception:
            story.append(Paragraph("PLANNING - GreenSIG", title_style))

        # Informations d'export
        period_str = f"Periode: {start_date} au {end_date}"
        export_info = f"Exporte par: {user_name} le {datetime.now().strftime('%d/%m/%Y a %H:%M')}"
        story.append(Paragraph(period_str, subtitle_style))
        story.append(Paragraph(export_info, subtitle_style))
        story.append(Spacer(1, 0.5*cm))

        # Verifier s'il y a des donnees
        distributions = list(queryset)
        if not distributions:
            story.append(Paragraph("Aucune tache planifiee pour cette periode.", cell_style))
            doc.build(story)
            buffer.seek(0)

            # Sauvegarder le fichier
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"planning_{start_date}_{end_date}_{timestamp}.pdf"
            export_dir = os.path.join(settings.MEDIA_ROOT, 'exports', 'pdf')
            os.makedirs(export_dir, exist_ok=True)
            filepath = os.path.join(export_dir, filename)

            with open(filepath, 'wb') as f:
                f.write(buffer.getvalue())

            relative_path = f"exports/pdf/{filename}"
            download_url = f"{settings.MEDIA_URL}{relative_path}"

            return {
                'success': True,
                'file_path': filepath,
                'download_url': download_url,
                'filename': filename,
                'record_count': 0,
            }

        # En-tetes du tableau
        headers = ['Date', 'Reference', 'Type', 'Equipe(s)', 'Horaires', 'Charge', 'Statut', 'Priorite']
        table_data = [[Paragraph(h, header_cell_style) for h in headers]]

        # Mapping statut vers couleurs et labels
        STATUT_LABELS = {
            'NON_REALISEE': 'A faire',
            'EN_COURS': 'En cours',
            'REALISEE': 'Realisee',
            'REPORTEE': 'Reportee',
            'ANNULEE': 'Annulee',
        }

        STATUT_COLORS = {
            'REALISEE': colors.HexColor('#C8E6C9'),  # Vert clair
            'EN_COURS': colors.HexColor('#BBDEFB'),  # Bleu clair
            'REPORTEE': colors.HexColor('#FFF9C4'),  # Jaune clair
            'ANNULEE': colors.HexColor('#FFCDD2'),   # Rouge clair
            'NON_REALISEE': colors.white,
        }

        PRIORITE_LABELS = {
            1: 'P1 - Tres basse',
            2: 'P2 - Basse',
            3: 'P3 - Moyenne',
            4: 'P4 - Haute',
            5: 'P5 - Urgent',
        }

        # Construire les lignes du tableau
        row_statuts = []  # Pour appliquer les couleurs par statut
        row_priorites = []  # Pour appliquer le style urgent

        for dist in distributions:
            tache = dist.tache

            # Date
            date_str = dist.date.strftime('%d/%m/%Y') if dist.date else '-'

            # Reference
            ref_str = tache.reference or f"T-{tache.id}"

            # Type de tache
            type_str = tache.id_type_tache.nom_tache if tache.id_type_tache else '-'

            # Equipes
            equipes_list = list(tache.equipes.all())
            if equipes_list:
                equipes_str = ', '.join([eq.nom_equipe for eq in equipes_list])
            else:
                equipes_str = '-'

            # Horaires
            if dist.heure_debut and dist.heure_fin:
                horaires_str = f"{dist.heure_debut.strftime('%H:%M')} - {dist.heure_fin.strftime('%H:%M')}"
            else:
                horaires_str = '-'

            # Charge (heures planifiees)
            charge_str = f"{dist.heures_planifiees:.1f}h" if dist.heures_planifiees else '-'

            # Statut
            statut_str = STATUT_LABELS.get(dist.status, dist.status)

            # Priorite
            priorite = tache.priorite or 3
            priorite_str = PRIORITE_LABELS.get(priorite, f"P{priorite}")

            # Ajouter la ligne
            row = [
                Paragraph(date_str, cell_style),
                Paragraph(ref_str, cell_style),
                Paragraph(type_str, cell_style),
                Paragraph(equipes_str, cell_style),
                Paragraph(horaires_str, cell_style),
                Paragraph(charge_str, cell_style),
                Paragraph(statut_str, cell_style),
                Paragraph(priorite_str, cell_style),
            ]
            table_data.append(row)
            row_statuts.append(dist.status)
            row_priorites.append(priorite)

        # Statistiques en bas du tableau
        total_distributions = len(distributions)
        total_heures = sum(d.heures_planifiees or 0 for d in distributions)

        # Compter par statut
        statuts_count = {}
        for s in row_statuts:
            statuts_count[s] = statuts_count.get(s, 0) + 1

        stats_parts = [f"Total: {total_distributions} taches, {total_heures:.1f}h"]
        for statut, label in STATUT_LABELS.items():
            count = statuts_count.get(statut, 0)
            if count > 0:
                stats_parts.append(f"{label}: {count}")

        stats_text = " | ".join(stats_parts)
        table_data.append([Paragraph(stats_text, cell_style)] + [Paragraph('', cell_style) for _ in range(len(headers) - 1)])
        stats_row_index = len(table_data) - 1

        # Creer le tableau avec largeurs de colonnes
        # Date(2.5), Ref(3.5), Type(3), Equipes(3.5), Horaires(2.5), Charge(1.5), Statut(2.5), Priorite(2)
        col_widths = [2.5*cm, 3.5*cm, 3*cm, 3.5*cm, 2.5*cm, 1.5*cm, 2.5*cm, 2.5*cm]

        table = Table(table_data, colWidths=col_widths, repeatRows=1)

        # Style du tableau
        table_style_commands = [
            # En-tete
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E7D32')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),

            # Corps
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

            # Bordures
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#2E7D32')),

            # Alternance de couleurs (exclure derniere ligne stats)
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#F5F5F5')]),

            # Ligne de statistiques (derniere ligne)
            ('SPAN', (0, stats_row_index), (-1, stats_row_index)),
            ('BACKGROUND', (0, stats_row_index), (-1, stats_row_index), colors.HexColor('#E8F5E9')),
            ('ALIGN', (0, stats_row_index), (-1, stats_row_index), 'CENTER'),
            ('FONTNAME', (0, stats_row_index), (-1, stats_row_index), 'Helvetica-Oblique'),
            ('TEXTCOLOR', (0, stats_row_index), (-1, stats_row_index), colors.HexColor('#2E7D32')),
        ]

        # Appliquer les couleurs par statut (colonne 6 = Statut)
        statut_col = 6
        for i, statut in enumerate(row_statuts, start=1):
            if statut in STATUT_COLORS:
                table_style_commands.append(('BACKGROUND', (statut_col, i), (statut_col, i), STATUT_COLORS[statut]))

        # Mettre en rouge les taches urgentes (priorite 5, colonne 7 = Priorite)
        priorite_col = 7
        for i, priorite in enumerate(row_priorites, start=1):
            if priorite == 5:
                table_style_commands.append(('TEXTCOLOR', (priorite_col, i), (priorite_col, i), colors.red))
                table_style_commands.append(('FONTNAME', (priorite_col, i), (priorite_col, i), 'Helvetica-Bold'))

        table.setStyle(TableStyle(table_style_commands))
        story.append(table)

        # Generer le PDF
        doc.build(story)

        # Sauvegarder le fichier
        buffer.seek(0)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"planning_{start_date}_{end_date}_{timestamp}.pdf"

        export_dir = os.path.join(settings.MEDIA_ROOT, 'exports', 'pdf')
        os.makedirs(export_dir, exist_ok=True)

        filepath = os.path.join(export_dir, filename)
        with open(filepath, 'wb') as f:
            f.write(buffer.getvalue())

        relative_path = f"exports/pdf/{filename}"
        download_url = f"{settings.MEDIA_URL}{relative_path}"

        logger.info(f"Planning PDF export completed: {filepath} ({len(distributions)} distributions)")

        return {
            'success': True,
            'file_path': filepath,
            'download_url': download_url,
            'filename': filename,
            'record_count': len(distributions),
        }

    except Utilisateur.DoesNotExist:
        logger.error(f"User {user_id} not found for planning PDF export")
        return {'success': False, 'error': 'Utilisateur non trouve'}
    except Exception as e:
        logger.error(f"Error in export_planning_pdf_async: {str(e)}")
        return {'success': False, 'error': str(e)}