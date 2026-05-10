"""
API v1 Notifications routes
"""

import datetime

from flask import current_app, jsonify, request

from arm.models.notifications import Notifications
from arm.ui import db

from . import api_v1
from .auth import require_token


@api_v1.route("/notifications", methods=["GET"])
@require_token
def get_notifications():
    """Get notifications"""
    try:
        unread_only = request.args.get("unread_only", "false").lower() == "true"
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 50))

        query = Notifications.query
        if unread_only:
            query = query.filter_by(seen=False)

        query = query.order_by(Notifications.trigger_time.desc())

        total = query.count()
        notifications = query.offset((page - 1) * per_page).limit(per_page).all()

        result = []
        for notification in notifications:
            result.append(notification.get_d())

        return jsonify(
            {
                "success": True,
                "data": result,
                "meta": {
                    "total": total,
                    "page": page,
                    "per_page": per_page,
                    "pages": (total + per_page - 1) // per_page,
                    "unread_only": unread_only,
                },
            }
        ), 200

    except Exception as e:
        current_app.logger.error(f"Error getting notifications: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@api_v1.route("/notifications/<int:notification_id>/read", methods=["PUT"])
@require_token
def mark_notification_read(notification_id):
    """Mark notification as read"""
    try:
        notification = Notifications.query.get_or_404(notification_id)

        notification.seen = True
        notification.dismiss_time = datetime.datetime.now()
        db.session.commit()

        return jsonify({"success": True, "message": "Notification marked as read"}), 200

    except Exception as e:
        current_app.logger.error(
            f"Error marking notification {notification_id} as read: {e}"
        )
        return jsonify({"success": False, "error": "Internal server error"}), 500


@api_v1.route("/notifications/settings/timeout", methods=["GET"])
@require_token
def get_notification_timeout():
    """Get notification timeout setting"""
    try:
        # This would need to be implemented based on existing settings
        # For now, return a default
        timeout = 30  # days

        return jsonify({"success": True, "data": {"timeout_days": timeout}}), 200

    except Exception as e:
        current_app.logger.error(f"Error getting notification timeout: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500
