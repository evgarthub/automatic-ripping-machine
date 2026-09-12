"""
API v1 System routes
"""
import os
import subprocess

import psutil
from flask import jsonify, current_app, request

from . import api_v1
from .auth import require_token
import arm.config.config as cfg
from arm.models.system_drives import SystemDrives
from arm.models.system_info import SystemInfo
from arm.ui import db
from arm.ui.settings import DriveUtils as drive_utils
from arm.ui.settings.ServerUtil import ServerUtil
from arm.ui.settings.settings import check_hw_transcode_support

DRIVE_MODES = ('auto', 'manual')


@api_v1.route('/system/info', methods=['GET'])
@require_token
def get_system_info():
    """Get system information"""
    try:
        import arm
        info = {
            'version': arm.__version__ if hasattr(arm, '__version__') else 'unknown',
            'arm_name': cfg.arm_config.get('ARM_NAME', 'ARM'),
            'web_server_ip': cfg.arm_config.get('WEBSERVER_IP', '0.0.0.0'),
            'web_server_port': cfg.arm_config.get('WEBSERVER_PORT', 8080),
            'database_file': cfg.arm_config.get('DBFILE', ''),
            'log_path': cfg.arm_config.get('LOGPATH', ''),
            'install_path': cfg.arm_config.get('INSTALLPATH', '')
        }

        return jsonify({
            'success': True,
            'data': info
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting system info: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


def get_drive_job_info(job):
    """Get basic job info for a drive as used by SystemDrives.debug"""
    if job is None:
        return None
    return {
        'job_id': job.job_id,
        'status': job.status,
        'video_type': job.video_type,
        'title': job.title,
        'year': job.year
    }


def serialize_drive(drive):
    """Serialize a SystemDrives row with the real model fields"""
    return {
        'drive_id': drive.drive_id,
        'name': drive.name,
        'description': drive.description,
        'type': drive.type,
        'mount': drive.mount,
        'maker': drive.maker,
        'model': drive.model,
        'serial': drive.serial,
        'connection': drive.connection,
        'firmware': drive.firmware,
        'location': drive.location,
        'stale': drive.stale,
        'mdisc': drive.mdisc,
        'drive_mode': drive.drive_mode,
        'read_cd': drive.read_cd,
        'read_dvd': drive.read_dvd,
        'read_bd': drive.read_bd,
        'processing': drive.processing,
        'job_current': get_drive_job_info(drive.job_current),
        'job_previous': get_drive_job_info(drive.job_previous)
    }


@api_v1.route('/system/drives', methods=['GET'])
@require_token
def get_drives():
    """Get list of drives"""
    try:
        drives = drive_utils.get_drives()

        return jsonify({
            'success': True,
            'data': [serialize_drive(drive) for drive in drives]
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting drives: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_v1.route('/system/drives/<drive_name>/eject', methods=['POST'])
@require_token
def eject_drive(drive_name):
    """Eject a drive"""
    try:
        drives = drive_utils.get_drives()
        drive = next((d for d in drives if d.name == drive_name), None)

        if not drive:
            return jsonify({
                'success': False,
                'error': f'Drive {drive_name} not found'
            }), 404

        error = drive.eject()
        if error is None:
            return jsonify({
                'success': True,
                'message': f'Drive {drive_name} ejected successfully'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': f'Failed to eject drive {drive_name}'
            }), 500

    except Exception as e:
        current_app.logger.error(f"Error ejecting drive {drive_name}: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_v1.route('/system/drives/scan', methods=['POST'])
@require_token
def scan_drives():
    """Scan the system for new drives and update the database"""
    try:
        new_drives = drive_utils.drives_update()
        return jsonify({
            'success': True,
            'data': {'new_drives': new_drives}
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error scanning drives: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_v1.route('/system/drives/<int:drive_id>', methods=['PUT'])
@require_token
def update_drive(drive_id):
    """Update editable drive fields, mirroring the legacy systeminfo form

    Request Body:
        name (str): new drive nickname
        description (str): new drive description
        drive_mode (str): 'auto' or 'manual'

    Returns:
        JSON response with the updated drive serialization
    """
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or not data:
            return jsonify({
                'success': False,
                'error': 'JSON body required with at least one of: name, description, drive_mode'
            }), 400

        unknown = set(data.keys()) - {'name', 'description', 'drive_mode'}
        if unknown:
            return jsonify({
                'success': False,
                'error': f'Unknown drive fields: {", ".join(sorted(unknown))}'
            }), 400

        if 'drive_mode' in data and str(data['drive_mode']).strip() not in DRIVE_MODES:
            return jsonify({
                'success': False,
                'error': f'Invalid drive_mode, must be one of: {", ".join(DRIVE_MODES)}'
            }), 400

        drive = SystemDrives.query.filter_by(drive_id=drive_id).first()
        if drive is None:
            return jsonify({
                'success': False,
                'error': f'Drive {drive_id} not found'
            }), 404

        if 'name' in data:
            drive.name = str(data['name']).strip()
        if 'description' in data:
            drive.description = str(data['description']).strip()
        if 'drive_mode' in data:
            drive.drive_mode = str(data['drive_mode']).strip()
        db.session.commit()

        return jsonify({
            'success': True,
            'data': serialize_drive(drive)
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error updating drive {drive_id}: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_v1.route('/system/drives/<int:drive_id>', methods=['DELETE'])
@require_token
def remove_drive(drive_id):
    """Remove a drive from the ARM database, mirroring the legacy drive_remove"""
    try:
        drive = SystemDrives.query.filter_by(drive_id=drive_id).first()
        if drive is None:
            return jsonify({
                'success': False,
                'error': f'Drive {drive_id} not found'
            }), 404

        dev_path = drive.mount
        SystemDrives.query.filter_by(drive_id=drive_id).delete()
        db.session.commit()
        return jsonify({
            'success': True,
            'message': f'Removed drive [{dev_path}] from ARM'
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error removing drive {drive_id}: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_v1.route('/system/drives/<int:drive_id>/manual', methods=['POST'])
@require_token
def manual_start_drive(drive_id):
    """Manually start a rip job on a drive, mirroring the legacy drive_manual

    Runs {INSTALLPATH}/scripts/docker/docker_arm_wrapper.sh <dev_path> and
    waits for it to finish like the legacy route does.
    """
    try:
        drive = SystemDrives.query.filter_by(drive_id=drive_id).first()
        if drive is None:
            return jsonify({
                'success': False,
                'error': f'Drive {drive_id} not found'
            }), 404

        dev_path = drive.mount.lstrip('/dev/')
        cmd = os.path.join(
            cfg.arm_config["INSTALLPATH"],
            f"scripts/docker/docker_arm_wrapper.sh {dev_path}",
        )
        current_app.logger.debug(f"Running command[{cmd}]")

        try:
            manual_process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                              stderr=subprocess.PIPE, text=True)
            stdout, stderr = manual_process.communicate()

            if manual_process.returncode != 0:
                raise subprocess.CalledProcessError(manual_process.returncode, cmd,
                                                    output=stdout, stderr=stderr)

            message = f"Manually starting a job on Drive: '{drive.name}'"
            current_app.logger.debug(stdout)
            return jsonify({
                'success': True,
                'message': message
            }), 200
        except subprocess.CalledProcessError as e:
            message = f"Failed to start a job on Drive: '{drive.name}' See logs for info"
            current_app.logger.error(message)
            current_app.logger.error(f"error: {e}")
            current_app.logger.error(f"stdout: {e.output}")
            current_app.logger.error(f"stderr: {e.stderr}")
            return jsonify({
                'success': False,
                'error': message
            }), 500
    except Exception as e:
        current_app.logger.error(f"Error manually starting drive {drive_id}: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_v1.route('/system/dashboard', methods=['GET'])
@require_token
def get_system_dashboard():
    """Homepage-style system overview (CPU, memory, ARM paths, HW transcode)."""
    try:
        server_row = SystemInfo.query.filter_by(id=1).first()
        if server_row is None:
            server_row = SystemInfo.query.first()

        serverutil = ServerUtil()
        hw_support = check_hw_transcode_support()

        if server_row is not None:
            server_data = {
                'name': server_row.name,
                'description': server_row.description,
                'cpu': server_row.cpu,
                'mem_total_gb': server_row.mem_total,
            }
        else:
            memory = psutil.virtual_memory()
            server_data = {
                'name': 'ARM Server',
                'description': 'Automatic Ripping Machine main server',
                'cpu': 'Unable to Identify',
                'mem_total_gb': round(memory.total / (1024 ** 3), 1),
            }

        transcode_path = cfg.arm_config.get('TRANSCODE_PATH', '')
        completed_path = cfg.arm_config.get('COMPLETED_PATH', '')
        vm = psutil.virtual_memory()

        payload = {
            'arm_name': cfg.arm_config.get('ARM_NAME', 'ARM'),
            'server': server_data,
            'cpu_percent': round(float(serverutil.cpu_util), 1),
            'cpu_temp_c': round(float(serverutil.cpu_temp), 1),
            'memory': {
                'total_gb': round(vm.total / (1024 ** 3), 1),
                'free_gb': float(serverutil.memory_free),
                'used_gb': float(serverutil.memory_used),
                'percent': round(float(serverutil.memory_percent), 1),
            },
            'storage': {
                'transcode': {
                    'path': transcode_path,
                    'free_gb': float(serverutil.storage_transcode_free),
                    'percent_used': round(float(serverutil.storage_transcode_percent), 1),
                },
                'completed': {
                    'path': completed_path,
                    'free_gb': float(serverutil.storage_completed_free),
                    'percent_used': round(float(serverutil.storage_completed_percent), 1),
                },
            },
            'hw_support': hw_support,
        }

        return jsonify({
            'success': True,
            'data': payload
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting system dashboard: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_v1.route('/system/stats', methods=['GET'])
@require_token
def get_system_stats():
    """Get system statistics"""
    try:
        from arm.models.job import Job

        # Job statistics
        total_jobs = Job.query.count()
        successful_jobs = Job.query.filter_by(status='success').count()
        failed_jobs = Job.query.filter_by(status='fail').count()
        active_jobs = Job.query.filter(~Job.finished).count()

        # System stats
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        stats = {
            'jobs': {
                'total': total_jobs,
                'successful': successful_jobs,
                'failed': failed_jobs,
                'active': active_jobs
            },
            'system': {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_used_gb': round(memory.used / (1024**3), 2),
                'memory_total_gb': round(memory.total / (1024**3), 2),
                'disk_percent': disk.percent,
                'disk_used_gb': round(disk.used / (1024**3), 2),
                'disk_total_gb': round(disk.total / (1024**3), 2)
            }
        }

        return jsonify({
            'success': True,
            'data': stats
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting system stats: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500