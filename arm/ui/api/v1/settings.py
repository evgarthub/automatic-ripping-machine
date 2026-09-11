"""
API v1 Settings routes
arm.yaml is the source of truth for ripper settings
"""
import importlib
import os
from typing import Any, Dict, Tuple, Union

import yaml
from flask import current_app, jsonify, request
from werkzeug.exceptions import HTTPException

import arm.config.config as cfg
import arm.ripper.utils as ripper_utils
from arm.models.ui_settings import UISettings
from arm.ui import db
from arm.ui.utils import build_arm_cfg, generate_comments

from . import api_v1
from .auth import require_token

UI_SETTINGS_FIELDS = {'index_refresh', 'use_icons', 'save_remote_images',
                      'bootstrap_skin', 'language', 'database_limit', 'notify_refresh'}
UI_SETTINGS_BOOL_FIELDS = {'use_icons', 'save_remote_images'}
UI_SETTINGS_INT_FIELDS = {'index_refresh', 'database_limit', 'notify_refresh'}


def is_read_only(path: str) -> bool:
    """Check if a config file is writable, mirroring the legacy settings page.

    Args:
        path: Full path to the config file

    Returns:
        True if the file is not writable
    """
    return not os.access(path, os.W_OK)


def coerce_setting_value(key: str, value: Any, current: Any) -> Any:
    """Coerce a submitted arm.yaml value to the type of the current value.

    Args:
        key: The setting key being coerced
        value: The submitted value
        current: The current value whose type drives coercion

    Returns:
        The coerced value

    Raises:
        ValueError: If the value cannot be coerced to the current type
    """
    if isinstance(current, bool):
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.strip().lower() in ("true", "false"):
            return value.strip().lower() == "true"
        raise ValueError(f"{key} expects a boolean (true/false), got: {value!r}")
    if isinstance(current, int):
        if isinstance(value, bool):
            raise ValueError(f"{key} expects an integer, got a boolean: {value!r}")
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value.strip())
            except ValueError:
                raise ValueError(f"{key} expects an integer, got: {value!r}")
        raise ValueError(f"{key} expects an integer, got: {value!r}")
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    raise ValueError(f"{key} expects a string, got: {value!r}")


@api_v1.route('/settings', methods=['GET'])
@require_token
def get_settings() -> Tuple[Any, int]:
    """Get all arm ripper settings with their comments.

    Returns:
        JSON response with values from arm.yaml, the comments map and a
        read_only flag for the config file
    """
    try:
        comments = generate_comments()
        return jsonify({
            'success': True,
            'data': {
                'values': cfg.arm_config,
                'comments': comments,
                'read_only': is_read_only(cfg.arm_config_path)
            }
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error getting settings: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@api_v1.route('/settings', methods=['PUT'])
@require_token
def update_settings() -> Union[Any, Tuple[Any, int]]:
    """Update arm ripper settings and rebuild arm.yaml.

    Request Body:
        Flat dict of ARM_ keys with typed values; every key must already
        exist in arm.yaml and is coerced to the current value's type

    Returns:
        JSON response with the reloaded settings values
    """
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or not data:
            return jsonify({
                'success': False,
                'error': 'JSON body required with at least one setting key'
            }), 400

        unknown = sorted(set(data.keys()) - set(cfg.arm_config.keys()))
        if unknown:
            return jsonify({
                'success': False,
                'error': f'Unknown settings keys: {", ".join(unknown)}'
            }), 400

        if is_read_only(cfg.arm_config_path):
            return jsonify({
                'success': False,
                'error': f'{cfg.arm_config_path} is read-only'
            }), 409

        coerced = {}
        errors = []
        for key, value in data.items():
            try:
                coerced[key] = coerce_setting_value(key, value, cfg.arm_config[key])
            except ValueError as e:
                errors.append(str(e))
        if errors:
            return jsonify({
                'success': False,
                'error': f'Invalid settings values: {"; ".join(errors)}'
            }), 400

        merged = dict(cfg.arm_config)
        merged.update(coerced)
        stringified = {key: str(value) for key, value in merged.items()}
        comments = generate_comments()
        arm_cfg = build_arm_cfg(stringified, comments)

        try:
            with open(cfg.arm_config_path, "w") as settings_file:
                settings_file.write(arm_cfg)
        except OSError as e:
            current_app.logger.error(f"{cfg.arm_config_path} is read-only", exc_info=e)
            return jsonify({
                'success': False,
                'error': f'{cfg.arm_config_path} is read-only'
            }), 409

        importlib.reload(cfg)
        current_app.logger.info(f"Setting log level to: {cfg.arm_config['LOGLEVEL']}")
        current_app.logger.setLevel(cfg.arm_config['LOGLEVEL'])

        return jsonify({
            'success': True,
            'data': {
                'values': cfg.arm_config,
                'comments': comments,
                'read_only': is_read_only(cfg.arm_config_path)
            }
        }), 200
    except HTTPException:
        raise
    except Exception as e:
        current_app.logger.error(f"Error updating settings: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@api_v1.route('/settings/ui', methods=['GET'])
@require_token
def get_ui_settings() -> Union[Any, Tuple[Any, int]]:
    """Get the UI settings row (id=1) from the database.

    Returns:
        JSON response with the UISettings row as a dict
    """
    try:
        arm_ui_cfg = UISettings.query.get(1)
        if arm_ui_cfg is None:
            return jsonify({
                'success': False,
                'error': 'UI settings not found; they are created during ARM setup'
            }), 404
        return jsonify({'success': True, 'data': arm_ui_cfg.get_d()}), 200
    except HTTPException:
        raise
    except Exception as e:
        current_app.logger.error(f"Error getting UI settings: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@api_v1.route('/settings/ui', methods=['PUT'])
@require_token
def update_ui_settings() -> Union[Any, Tuple[Any, int]]:
    """Update the UI settings row (id=1) in the database.

    Request Body:
        Flat dict of editable fields: index_refresh, use_icons,
        save_remote_images, bootstrap_skin, language, database_limit,
        notify_refresh

    Returns:
        JSON response with the updated UISettings row
    """
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or not data:
            return jsonify({
                'success': False,
                'error': f'JSON body required with at least one field: {", ".join(sorted(UI_SETTINGS_FIELDS))}'
            }), 400

        unknown = sorted(set(data.keys()) - UI_SETTINGS_FIELDS)
        if unknown:
            return jsonify({
                'success': False,
                'error': f'Unknown UI settings fields: {", ".join(unknown)}'
            }), 400

        arm_ui_cfg = UISettings.query.get(1)
        if arm_ui_cfg is None:
            return jsonify({
                'success': False,
                'error': 'UI settings not found; they are created during ARM setup'
            }), 404

        validated: Dict[str, Any] = {}
        errors = []
        for field, value in data.items():
            if field in UI_SETTINGS_BOOL_FIELDS:
                validated[field] = str(value).strip().lower() == "true"
            elif field in UI_SETTINGS_INT_FIELDS:
                try:
                    validated[field] = int(value)
                except (TypeError, ValueError):
                    errors.append(f"{field} expects an integer, got: {value!r}")
            elif isinstance(value, str):
                validated[field] = value
            elif isinstance(value, (int, float, bool)):
                validated[field] = format(value)
            else:
                errors.append(f"{field} expects a string, got: {value!r}")
        if errors:
            return jsonify({
                'success': False,
                'error': f'Invalid UI settings values: {"; ".join(errors)}'
            }), 400

        for field, value in validated.items():
            setattr(arm_ui_cfg, field, value)
        db.session.commit()

        return jsonify({'success': True, 'data': arm_ui_cfg.get_d()}), 200
    except HTTPException:
        raise
    except Exception as e:
        current_app.logger.error(f"Error updating UI settings: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@api_v1.route('/settings/abcde', methods=['GET'])
@require_token
def get_abcde_settings() -> Tuple[Any, int]:
    """Get the abcde.conf content.

    Returns:
        JSON response with the config file content and a read_only flag
    """
    try:
        return jsonify({
            'success': True,
            'data': {
                'content': cfg.abcde_config,
                'read_only': is_read_only(cfg.abcde_config_path)
            }
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error getting abcde settings: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@api_v1.route('/settings/abcde', methods=['PUT'])
@require_token
def update_abcde_settings() -> Union[Any, Tuple[Any, int]]:
    """Update the abcde.conf file.

    Request Body:
        content (str): Full new abcde.conf content; Windows line endings
        are cleaned to \\n before writing

    Returns:
        JSON response with the written content
    """
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or not isinstance(data.get('content'), str):
            return jsonify({
                'success': False,
                'error': 'JSON body with a string "content" field required'
            }), 400

        if is_read_only(cfg.abcde_config_path):
            return jsonify({
                'success': False,
                'error': f'{cfg.abcde_config_path} is read-only'
            }), 409

        abcde_cfg_str = str(data['content']).strip()
        clean_abcde_str = '\n'.join(abcde_cfg_str.splitlines())
        try:
            with open(cfg.abcde_config_path, "w") as abcde_file:
                abcde_file.write(clean_abcde_str)
        except OSError as e:
            current_app.logger.error(f"{cfg.abcde_config_path} is read-only", exc_info=e)
            return jsonify({
                'success': False,
                'error': f'{cfg.abcde_config_path} is read-only'
            }), 409
        cfg.abcde_config = clean_abcde_str

        return jsonify({
            'success': True,
            'data': {'content': clean_abcde_str}
        }), 200
    except HTTPException:
        raise
    except Exception as e:
        current_app.logger.error(f"Error updating abcde settings: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@api_v1.route('/settings/apprise', methods=['GET'])
@require_token
def get_apprise_settings() -> Tuple[Any, int]:
    """Get the apprise.yaml content.

    Returns:
        JSON response with the config file content and a read_only flag
    """
    try:
        try:
            with open(cfg.apprise_config_path, "r") as apprise_file:
                content = apprise_file.read()
        except OSError:
            content = ""
        return jsonify({
            'success': True,
            'data': {
                'content': content,
                'read_only': is_read_only(cfg.apprise_config_path)
            }
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error getting apprise settings: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@api_v1.route('/settings/apprise', methods=['PUT'])
@require_token
def update_apprise_settings() -> Union[Any, Tuple[Any, int]]:
    """Update the apprise.yaml file.

    Request Body:
        content (str): Full new apprise.yaml content; must parse as a YAML
        mapping (or be empty) before it is written

    Returns:
        JSON response with the written content
    """
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or not isinstance(data.get('content'), str):
            return jsonify({
                'success': False,
                'error': 'JSON body with a string "content" field required'
            }), 400

        try:
            parsed = yaml.safe_load(data['content'])
        except yaml.YAMLError as e:
            return jsonify({
                'success': False,
                'error': f'Invalid YAML: {e}'
            }), 400
        if parsed is not None and not isinstance(parsed, dict):
            return jsonify({
                'success': False,
                'error': 'Invalid YAML: apprise.yaml must contain a mapping'
            }), 400

        if is_read_only(cfg.apprise_config_path):
            return jsonify({
                'success': False,
                'error': f'{cfg.apprise_config_path} is read-only'
            }), 409

        try:
            with open(cfg.apprise_config_path, "w") as apprise_file:
                apprise_file.write(data['content'])
        except OSError as e:
            current_app.logger.error(f"{cfg.apprise_config_path} is read-only", exc_info=e)
            return jsonify({
                'success': False,
                'error': f'{cfg.apprise_config_path} is read-only'
            }), 409

        importlib.reload(cfg)

        return jsonify({
            'success': True,
            'data': {'content': data['content']}
        }), 200
    except HTTPException:
        raise
    except Exception as e:
        current_app.logger.error(f"Error updating apprise settings: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@api_v1.route('/settings/apprise/test', methods=['POST'])
@require_token
def test_apprise() -> Tuple[Any, int]:
    """Send a test notification through Apprise.

    Returns:
        JSON response with the message that was sent
    """
    try:
        message = "This is a notification by the ARM-Notification Test!"
        if cfg.arm_config["UI_BASE_URL"] and cfg.arm_config["WEBSERVER_PORT"]:
            message = message + f" Server URL: http://{cfg.arm_config['UI_BASE_URL']}:{cfg.arm_config['WEBSERVER_PORT']}"
        ripper_utils.notify(None, "ARM notification", message)
        return jsonify({
            'success': True,
            'data': {'message': message}
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error sending test notification: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500
