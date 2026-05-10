from flask import request, jsonify, current_app

from . import api_v1
from .auth import require_token
from arm.models.config import Config
from arm.ui import db
import arm.config.config as cfg


@api_v1.route('/config', methods=['GET'])
@require_token
def get_config():
    try:
        # Get the latest config (assuming job_id is None for global config)
        config = Config.query.filter_by(job_id=None).first()
        if not config:
            return jsonify({
                'success': False,
                'error': 'Configuration not found'
            }), 404

        return jsonify({
            'success': True,
            'data': config.get_d()
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting config: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_v1.route('/config', methods=['PUT'])
@require_token
def update_config():
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400

        # Get current config
        config = Config.query.filter_by(job_id=None).first()
        if not config:
            return jsonify({
                'success': False,
                'error': 'Configuration not found'
            }), 404

        allowed_fields = [
            'ARM_CHECK_UDF', 'GET_VIDEO_TITLE', 'SKIP_TRANSCODE', 'VIDEOTYPE',
            'MINLENGTH', 'MAXLENGTH', 'MANUAL_WAIT', 'MANUAL_WAIT_TIME',
            'RAW_PATH', 'TRANSCODE_PATH', 'COMPLETED_PATH', 'EXTRAS_SUB',
            'INSTALLPATH', 'LOGPATH', 'LOGLIFE', 'DBFILE', 'WEBSERVER_IP',
            'WEBSERVER_PORT', 'UI_BASE_URL', 'SET_MEDIA_PERMISSIONS',
            'CHMOD_VALUE', 'SET_MEDIA_OWNER', 'CHOWN_USER', 'CHOWN_GROUP',
            'RIPMETHOD', 'MKV_ARGS', 'DELRAWFILES', 'HASHEDKEYS',
            'HB_PRESET_DVD', 'HB_PRESET_BD', 'DEST_EXT', 'HANDBRAKE_CLI'
        ]

        updated = False
        for field in allowed_fields:
            if field in data:
                setattr(config, field, data[field])
                updated = True

        if updated:
            db.session.commit()
            return jsonify({
                'success': True,
                'message': 'Configuration updated'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No valid fields to update'
            }), 400

    except Exception as e:
        current_app.logger.error(f"Error updating config: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500