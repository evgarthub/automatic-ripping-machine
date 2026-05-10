"""
API v1 System routes
"""
import psutil
from flask import jsonify, current_app

from . import api_v1
from .auth import require_token
import arm.config.config as cfg
from arm.ui.settings import DriveUtils as drive_utils
from arm.models.system_info import SystemInfo
from arm.ui.settings.ServerUtil import ServerUtil
from arm.ui.settings.settings import check_hw_transcode_support


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


@api_v1.route('/system/drives', methods=['GET'])
@require_token
def get_drives():
    """Get list of drives"""
    try:
        drives = drive_utils.get_drives()
        drive_list = []

        for drive in drives:
            drive_info = {
                'name': drive.name,
                'mount_point': drive.mount_point,
                'device': drive.device,
                'type': drive.type,
                'is_mounted': drive.is_mounted,
                'has_disc': drive.has_disc,
                'disc_type': drive.disc_type,
                'capacity': drive.capacity,
                'used': drive.used,
                'free': drive.free
            }
            drive_list.append(drive_info)

        return jsonify({
            'success': True,
            'data': drive_list
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

        if drive.eject():
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
                    'percent_used': round(float(serverutil.storage_transcode_percent), 1),
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