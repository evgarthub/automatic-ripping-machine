"""
API v1 Notifications routes
"""

import datetime

from flask import current_app, jsonify, request

from arm.models.notifications import Notifications
from arm.models.ui_settings import UISettings
from arm.ui import db

from . import api_v1
from .auth import require_token

DEFAULT_NOTIFY_TIMEOUT = 6500


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


@api_v1.route("/notifications", methods=["DELETE"])
@require_token
def clear_notifications():
    """Clear notifications"""
    try:
        raw_id = request.args.get("id")
        notification_id = None
        if raw_id is not None:
            try:
                notification_id = int(raw_id)
            except (TypeError, ValueError):
                return jsonify({"success": False, "error": "Invalid notification id"}), 400

        query = Notifications.query.filter_by(cleared=False)
        if notification_id is not None:
            query = query.filter_by(id=notification_id)

        notifications = query.all()

        if notification_id is not None and not notifications:
            return jsonify({"success": False, "error": "Notification not found"}), 404

        if not notifications:
            return jsonify(
                {
                    "success": True,
                    "data": {"cleared": 0},
                    "message": "No notifications to clear",
                }
            ), 200

        cleared_time = datetime.datetime.now()
        for notification in notifications:
            notification.cleared = True
            notification.cleared_time = cleared_time
        db.session.commit()

        return jsonify(
            {
                "success": True,
                "data": {"cleared": len(notifications)},
                "message": f"Cleared {len(notifications)} notifications",
            }
        ), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error clearing notifications: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@api_v1.route("/notifications/settings/timeout", methods=["GET"])
@require_token
def get_notification_timeout():
    """Get the notification popup timeout

    The stored value is UISettings.notify_refresh (milliseconds), matching
    the legacy json_api notify_timeout mode; 6500 is the legacy default.
    """
    try:
        armui_cfg = UISettings.query.first()
        timeout = armui_cfg.notify_refresh if armui_cfg else None
        if timeout is None:
            timeout = DEFAULT_NOTIFY_TIMEOUT

        return jsonify({"success": True, "data": {"timeout": int(timeout)}}), 200

    except Exception as e:
        current_app.logger.error(f"Error getting notification timeout: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@api_v1.route("/notifications/settings/timeout", methods=["PUT"])
@require_token
def update_notification_timeout():
    """Update the notification popup timeout (UISettings.notify_refresh)

    Request Body:
        timeout (int): new timeout in milliseconds, must be a positive integer
    """
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or "timeout" not in data:
            return jsonify(
                {"success": False, "error": 'JSON body with an integer "timeout" field required'}
            ), 400

        try:
            timeout = int(data["timeout"])
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "timeout must be an integer"}), 400

        if timeout < 1:
            return jsonify({"success": False, "error": "timeout must be a positive integer"}), 400

        armui_cfg = UISettings.query.first()
        if armui_cfg is None:
            return jsonify(
                {"success": False, "error": "UI settings not found; they are created during ARM setup"}
            ), 404

        armui_cfg.notify_refresh = timeout
        db.session.commit()

        return jsonify({"success": True, "data": {"timeout": timeout}}), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating notification timeout: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500
