"""
Celery tasks for api module.

Async tasks for:
- PDF export (map with legend)
- Data export (Excel, GeoJSON, KML, Shapefile)
- Async notifications
- Statistics calculation
"""

import logging
import os
import json
import base64
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)


# ==============================================================================
# EXPORT TASKS
# ==============================================================================

@shared_task(bind=True, name='api.tasks.export_pdf_async')
def export_pdf_async(self, user_id, title, map_image_base64, visible_layers,
                     center, zoom, site_names):
    """
    Async task to generate a PDF export of the map.

    Args:
        user_id: ID of the user requesting the export
        title: Title for the PDF
        map_image_base64: Base64 encoded map image
        visible_layers: Dict of visible layer names
        center: Map center coordinates [lon, lat]
        zoom: Map zoom level
        site_names: List of visible site names

    Returns:
        dict: Result with file path or error message
    """
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import cm
    from reportlab.lib.utils import ImageReader
    from api_users.models import Utilisateur
    from datetime import datetime
    import io

    try:
        # Get user
        user = Utilisateur.objects.get(pk=user_id)
        user_name = user.get_full_name() or f"{user.prenom} {user.nom}".strip()
        user_info = f"Exporté par: {user_name} ({user.email})" if user.email else f"Exporté par: {user_name}"

        # Create PDF in memory
        buffer = io.BytesIO()
        page_width, page_height = landscape(A4)
        pdf = canvas.Canvas(buffer, pagesize=landscape(A4))

        # User info
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(2*cm, page_height - 2*cm, user_info)

        # Sites
        if site_names:
            sites_text = f"Site(s): {', '.join(site_names)}"
            pdf.setFont("Helvetica", 10)
            pdf.drawString(2*cm, page_height - 2.6*cm, sites_text)
            date_y = page_height - 3.2*cm
        else:
            date_y = page_height - 2.6*cm

        # Date
        pdf.setFont("Helvetica", 10)
        date_str = datetime.now().strftime("%d/%m/%Y %H:%M")
        pdf.drawString(2*cm, date_y, f"Date d'export: {date_str}")

        # Map image
        if map_image_base64:
            try:
                image_data = base64.b64decode(
                    map_image_base64.split(',')[1] if ',' in map_image_base64 else map_image_base64
                )
                image = ImageReader(io.BytesIO(image_data))

                img_width = page_width * 0.7
                img_height = (page_height - 6*cm) * 0.7
                img_x = 2*cm
                img_y = page_height - 5*cm - img_height

                pdf.drawImage(image, img_x, img_y, width=img_width,
                             height=img_height, preserveAspectRatio=True)
            except Exception as e:
                logger.error(f"Error loading map image: {e}")

        # Legend
        legend_x = page_width - 6*cm
        legend_y = page_height - 3*cm
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(legend_x, legend_y, "Légende")
        legend_y -= 0.6*cm

        # Draw legend items for visible layers
        pdf.setFont("Helvetica", 9)
        for layer_name, is_visible in visible_layers.items():
            if is_visible:
                pdf.drawString(legend_x + 0.5*cm, legend_y, f"• {layer_name}")
                legend_y -= 0.4*cm

        pdf.save()

        # Save to media folder
        buffer.seek(0)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"export_carte_{timestamp}_{user_id}.pdf"

        export_dir = os.path.join(settings.MEDIA_ROOT, 'exports', 'pdf')
        os.makedirs(export_dir, exist_ok=True)

        filepath = os.path.join(export_dir, filename)
        with open(filepath, 'wb') as f:
            f.write(buffer.getvalue())

        # Return relative URL
        relative_path = f"exports/pdf/{filename}"
        download_url = f"{settings.MEDIA_URL}{relative_path}"

        logger.info(f"PDF export completed: {filepath}")

        return {
            'success': True,
            'file_path': filepath,
            'download_url': download_url,
            'filename': filename,
        }

    except Utilisateur.DoesNotExist:
        logger.error(f"User {user_id} not found for PDF export")
        return {'success': False, 'error': 'User not found'}
    except Exception as e:
        logger.error(f"Error in export_pdf_async: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task(bind=True, name='api.tasks.export_data_async')
def export_data_async(self, user_id, model_name, export_format, filters=None, ids=None):
    """
    Async task to export data in various formats.

    Args:
        user_id: ID of the user requesting the export
        model_name: Name of the model to export (arbres, gazons, etc.)
        export_format: Format to export (xlsx, geojson, kml, shp)
        filters: Optional dict of filters to apply
        ids: Optional list of specific IDs to export

    Returns:
        dict: Result with file path or error message
    """
    from api.models import (
        Site, SousSite, Arbre, Gazon, Palmier, Arbuste, Vivace,
        Cactus, Graminee, Puit, Pompe, Vanne, Clapet,
        Canalisation, Aspersion, Goutte, Ballon
    )
    from datetime import datetime
    import io

    MODEL_MAPPING = {
        'sites': Site,
        'sous-sites': SousSite,
        'arbres': Arbre,
        'gazons': Gazon,
        'palmiers': Palmier,
        'arbustes': Arbuste,
        'vivaces': Vivace,
        'cactus': Cactus,
        'graminees': Graminee,
        'puits': Puit,
        'pompes': Pompe,
        'vannes': Vanne,
        'clapets': Clapet,
        'canalisations': Canalisation,
        'aspersions': Aspersion,
        'gouttes': Goutte,
        'ballons': Ballon,
    }

    try:
        if model_name not in MODEL_MAPPING:
            return {'success': False, 'error': f'Invalid model: {model_name}'}

        model_class = MODEL_MAPPING[model_name]
        queryset = model_class.objects.all()

        # Apply filters
        if ids:
            queryset = queryset.filter(pk__in=ids)

        if filters:
            if 'site' in filters:
                queryset = queryset.filter(site_id=filters['site'])
            # Add more filter handling as needed

        if not queryset.exists():
            return {'success': False, 'error': 'No data to export'}

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        export_dir = os.path.join(settings.MEDIA_ROOT, 'exports', export_format)
        os.makedirs(export_dir, exist_ok=True)

        # Export based on format
        if export_format == 'xlsx':
            from openpyxl import Workbook

            wb = Workbook()
            ws = wb.active
            ws.title = model_name.capitalize()

            # Get model fields
            fields = [f.name for f in model_class._meta.get_fields()
                     if hasattr(f, 'column') and f.name != 'geom']

            # Header
            ws.append(fields)

            # Data
            for obj in queryset:
                row = []
                for field in fields:
                    value = getattr(obj, field, '')
                    if hasattr(value, 'pk'):
                        value = str(value)
                    row.append(value)
                ws.append(row)

            filename = f"{model_name}_{timestamp}.xlsx"
            filepath = os.path.join(export_dir, filename)
            wb.save(filepath)

        elif export_format == 'geojson':
            from api.services.geo_io import export_to_geojson

            geojson_data = export_to_geojson(queryset)
            filename = f"{model_name}_{timestamp}.geojson"
            filepath = os.path.join(export_dir, filename)

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(geojson_data, f, ensure_ascii=False, indent=2)

        elif export_format == 'kml':
            from api.services.geo_io import export_to_kml

            kml_content = export_to_kml(queryset)
            filename = f"{model_name}_{timestamp}.kml"
            filepath = os.path.join(export_dir, filename)

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(kml_content)

        elif export_format == 'shp':
            from api.services.geo_io import export_to_shapefile

            zip_content = export_to_shapefile(queryset, model_name)
            filename = f"{model_name}_{timestamp}.zip"
            filepath = os.path.join(export_dir, filename)

            with open(filepath, 'wb') as f:
                f.write(zip_content)

        else:
            return {'success': False, 'error': f'Unsupported format: {export_format}'}

        relative_path = f"exports/{export_format}/{filename}"
        download_url = f"{settings.MEDIA_URL}{relative_path}"

        logger.info(f"Data export completed: {filepath} ({queryset.count()} records)")

        return {
            'success': True,
            'file_path': filepath,
            'download_url': download_url,
            'filename': filename,
            'record_count': queryset.count(),
        }

    except Exception as e:
        logger.error(f"Error in export_data_async: {str(e)}")
        return {'success': False, 'error': str(e)}


# ==============================================================================
# NOTIFICATION TASKS
# ==============================================================================

@shared_task(bind=True, name='api.tasks.send_notification_async')
def send_notification_async(self, user_ids, message, notification_type='info',
                            title=None, data=None):
    """
    Async task to send notifications to users.

    This task can be used to send notifications without blocking the main request.
    It integrates with Django Channels for real-time WebSocket notifications.

    Args:
        user_ids: List of user IDs to notify (or single ID)
        message: Notification message
        notification_type: Type of notification (info, warning, error, success)
        title: Optional title for the notification
        data: Optional additional data dict

    Returns:
        dict: Result with count of notifications sent
    """
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    if isinstance(user_ids, int):
        user_ids = [user_ids]

    channel_layer = get_channel_layer()
    sent_count = 0
    errors = []

    notification_payload = {
        'type': 'notification',
        'notification_type': notification_type,
        'message': message,
        'title': title,
        'data': data or {},
        'timestamp': timezone.now().isoformat(),
    }

    for user_id in user_ids:
        try:
            # Send to user's WebSocket group
            group_name = f"user_{user_id}"
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    'type': 'send_notification',
                    **notification_payload
                }
            )
            sent_count += 1
            logger.debug(f"Notification sent to user {user_id}")
        except Exception as e:
            errors.append(f"User {user_id}: {str(e)}")
            logger.warning(f"Failed to send notification to user {user_id}: {e}")

    result = {
        'success': True,
        'sent_count': sent_count,
        'total_users': len(user_ids),
        'errors': errors if errors else None,
    }

    if sent_count > 0:
        logger.info(f"Notifications sent: {sent_count}/{len(user_ids)}")

    return result


@shared_task(bind=True, name='api.tasks.notify_export_complete')
def notify_export_complete(self, user_id, export_type, download_url, filename):
    """
    Notify a user that their export is ready for download.

    Args:
        user_id: ID of the user to notify
        export_type: Type of export (pdf, xlsx, geojson, etc.)
        download_url: URL to download the exported file
        filename: Name of the exported file

    Returns:
        dict: Result of the notification
    """
    return send_notification_async.apply(
        args=[[user_id]],
        kwargs={
            'message': f"Votre export {export_type.upper()} est prêt: {filename}",
            'notification_type': 'success',
            'title': 'Export terminé',
            'data': {
                'export_type': export_type,
                'download_url': download_url,
                'filename': filename,
            }
        }
    )


# ==============================================================================
# STATISTICS TASKS
# ==============================================================================

@shared_task(bind=True, name='api.tasks.calculate_site_statistics')
def calculate_site_statistics(self, site_id=None):
    """
    Calculate and cache statistics for sites.

    Can be run for a specific site or all sites.

    Args:
        site_id: Optional site ID to calculate stats for (None = all sites)

    Returns:
        dict: Calculated statistics
    """
    from api.models import Site, Arbre, Gazon, Palmier
    from django.db.models import Count, Sum, Avg

    try:
        if site_id:
            sites = Site.objects.filter(pk=site_id)
        else:
            sites = Site.objects.filter(actif=True)

        stats = []
        for site in sites:
            site_stats = {
                'site_id': site.id,
                'site_name': site.nom_site,
                'counts': {
                    'arbres': Arbre.objects.filter(site=site).count(),
                    'gazons': Gazon.objects.filter(site=site).count(),
                    'palmiers': Palmier.objects.filter(site=site).count(),
                },
                'total_objects': 0,
                'calculated_at': timezone.now().isoformat(),
            }
            site_stats['total_objects'] = sum(site_stats['counts'].values())
            stats.append(site_stats)

        logger.info(f"Statistics calculated for {len(stats)} site(s)")

        return {
            'success': True,
            'statistics': stats,
            'site_count': len(stats),
        }

    except Exception as e:
        logger.error(f"Error calculating statistics: {str(e)}")
        return {'success': False, 'error': str(e)}


# ==============================================================================
# CLEANUP TASKS
# ==============================================================================

@shared_task(bind=True, name='api.tasks.cleanup_old_exports')
def cleanup_old_exports(self, days=7):
    """
    Periodic task to clean up old export files.

    Removes export files older than the specified number of days.

    Args:
        days: Number of days after which to delete exports (default: 7)

    Returns:
        dict: Summary of deleted files
    """
    import time
    from pathlib import Path

    export_dir = Path(settings.MEDIA_ROOT) / 'exports'

    if not export_dir.exists():
        return {'success': True, 'deleted_count': 0, 'message': 'Export directory does not exist'}

    cutoff_time = time.time() - (days * 24 * 60 * 60)
    deleted_count = 0
    deleted_size = 0
    errors = []

    for file_path in export_dir.rglob('*'):
        if file_path.is_file():
            try:
                if file_path.stat().st_mtime < cutoff_time:
                    file_size = file_path.stat().st_size
                    file_path.unlink()
                    deleted_count += 1
                    deleted_size += file_size
                    logger.debug(f"Deleted old export: {file_path}")
            except Exception as e:
                errors.append(f"{file_path}: {str(e)}")

    result = {
        'success': True,
        'deleted_count': deleted_count,
        'deleted_size_mb': round(deleted_size / (1024 * 1024), 2),
        'errors': errors if errors else None,
    }

    if deleted_count > 0:
        logger.info(f"Cleanup: deleted {deleted_count} files ({result['deleted_size_mb']} MB)")

    return result


# ==============================================================================
# BULK NOTIFICATIONS TASK
# ==============================================================================

@shared_task(bind=True, name='api.tasks.send_bulk_notifications_async')
def send_bulk_notifications_async(self, notifications_data):
    """
    Async task to send multiple notifications in bulk.

    This is more efficient than sending notifications one by one,
    as it uses bulk_create for database operations.

    Args:
        notifications_data: List of dicts with:
            - type_notification
            - titre
            - message
            - recipient_id (int)
            - data (optional)
            - priorite (optional, default: 'normal')
            - acteur_id (optional)

    Returns:
        dict: Result with count of notifications sent
    """
    from api.models import Notification
    from api_users.models import Utilisateur
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    if not notifications_data:
        return {'success': True, 'created_count': 0}

    try:
        # Collecter tous les IDs necessaires
        recipient_ids = [n['recipient_id'] for n in notifications_data if 'recipient_id' in n]
        acteur_ids = [n['acteur_id'] for n in notifications_data if n.get('acteur_id')]

        # Charger tous les utilisateurs en une seule requete
        all_user_ids = set(recipient_ids + acteur_ids)
        users_map = {u.id: u for u in Utilisateur.objects.filter(id__in=all_user_ids, actif=True)}

        notifications_to_create = []
        for notif_data in notifications_data:
            recipient_id = notif_data.get('recipient_id')
            recipient = users_map.get(recipient_id)
            if not recipient:
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

        if not notifications_to_create:
            return {'success': True, 'created_count': 0, 'message': 'No valid recipients'}

        # Bulk create - much faster than individual creates
        created_notifications = Notification.objects.bulk_create(notifications_to_create)
        logger.info(f"Bulk notifications created: {len(created_notifications)}")

        # Send via WebSocket
        channel_layer = get_channel_layer()
        ws_sent = 0
        for notification in created_notifications:
            group_name = f"notifications_user_{notification.destinataire_id}"
            try:
                async_to_sync(channel_layer.group_send)(
                    group_name,
                    {
                        'type': 'notification_message',
                        'notification': notification.to_websocket_payload(),
                    }
                )
                ws_sent += 1
            except Exception:
                pass  # WebSocket not available for this user

        return {
            'success': True,
            'created_count': len(created_notifications),
            'websocket_sent': ws_sent,
        }

    except Exception as e:
        logger.error(f"Error in send_bulk_notifications_async: {str(e)}")
        return {'success': False, 'error': str(e)}
