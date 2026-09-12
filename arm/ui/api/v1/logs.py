"""
API v1 Logs routes
Mirrors the legacy log pages: list logfiles in LOGPATH and return their
contents as text/plain (modes: armcat, full) or as a download attachment
"""
import os
from datetime import datetime, timezone
from pathlib import Path

from flask import current_app, jsonify, request, send_file
from werkzeug.routing import ValidationError

import arm.config.config as cfg
import arm.ui.utils as ui_utils

from . import api_v1
from .auth import require_token

LOG_MODES = ('armcat', 'full', 'download')


@api_v1.route('/logs', methods=['GET'])
@require_token
def list_logs():
    """List log files in LOGPATH sorted by modification time (newest first)

    Returns:
        JSON response with a list of {name, size_bytes, modified} entries;
        modified is an ISO 8601 UTC timestamp. Logs live flat in LOGPATH
        (LOGPATH/<logfile>), so only top-level files are returned.
    """
    try:
        log_path = cfg.arm_config['LOGPATH']
        files = []
        if os.path.isdir(log_path):
            for name in os.listdir(log_path):
                full_path = os.path.join(log_path, name)
                if os.path.isfile(full_path):
                    stats = os.stat(full_path)
                    files.append((stats.st_mtime, {
                        'name': name,
                        'size_bytes': stats.st_size,
                        'modified': datetime.fromtimestamp(stats.st_mtime, timezone.utc).isoformat()
                    }))
        files.sort(key=lambda item: item[0], reverse=True)
        return jsonify({
            'success': True,
            'data': [entry for _, entry in files]
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error listing logs: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@api_v1.route('/logs/<name>', methods=['GET'])
@require_token
def read_log(name):
    """Return a logfile from LOGPATH, mirroring the legacy logreader

    Query Parameters:
        mode (str): armcat (only ARM: lines) | full (whole file, default) |
            download (send the file as an attachment)
        lines (int): with armcat/full, return only the last N lines

    Returns:
        text/plain response with the (filtered) log content, or the file
        itself as an attachment for mode=download. The whole file is read
        into memory; this is acceptable for a personal appliance.

    Only flat names are accepted: validate_logfile rejects any '/' or
    '../' and the basename check additionally rejects Windows-style
    '..\\' traversal, so nothing outside LOGPATH can be reached.
    """
    mode = request.args.get('mode', 'full')
    if mode not in LOG_MODES:
        return jsonify({'success': False, 'error': f'Invalid mode, must be one of: {", ".join(LOG_MODES)}'}), 400

    if not name or name in ('.', '..') or os.path.basename(name) != name:
        return jsonify({'success': False, 'error': 'Invalid logfile name'}), 400

    full_path = os.path.join(cfg.arm_config['LOGPATH'], name)
    try:
        ui_utils.validate_logfile(name, mode, Path(full_path))
    except ValidationError:
        return jsonify({'success': False, 'error': 'Invalid logfile name or mode'}), 400
    except FileNotFoundError:
        return jsonify({'success': False, 'error': f'Logfile {name} not found'}), 404

    if mode == 'download':
        return send_file(full_path, as_attachment=True)

    lines_param = request.args.get('lines')
    tail = None
    if lines_param is not None:
        try:
            tail = int(lines_param)
        except (TypeError, ValueError):
            return jsonify({'success': False, 'error': 'lines must be an integer'}), 400
        if tail < 1:
            return jsonify({'success': False, 'error': 'lines must be a positive integer'}), 400

    try:
        with open(full_path, encoding="utf8", errors='ignore') as read_log_file:
            content_lines = read_log_file.readlines()
    except OSError as e:
        current_app.logger.error(f"Error reading logfile {name}: {e}")
        return jsonify({'success': False, 'error': f'Logfile {name} not found'}), 404

    if mode == 'armcat':
        content_lines = [line for line in content_lines if "ARM:" in line]
    if tail is not None:
        content_lines = content_lines[-tail:]

    return current_app.response_class(''.join(content_lines), mimetype='text/plain')
