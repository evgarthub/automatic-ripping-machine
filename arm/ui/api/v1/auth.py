"""
API v1 Authentication routes
"""
import bcrypt
from flask import request, jsonify, current_app

from . import api_v1
from arm.models.user import User
from arm.models.token import Token
from arm.ui import db

MIN_PASSWORD_LENGTH = 6


def require_token(f):
    """Decorator to require valid API token"""
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({
                'success': False,
                'error': 'Missing or invalid authorization header'
            }), 401

        token_hash = auth_header.split(' ')[1]
        user = Token.validate_token(token_hash)
        if not user:
            return jsonify({
                'success': False,
                'error': 'Invalid or expired token'
            }), 401

        # Store user in request context for use in routes
        setattr(request, 'api_user', user)
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function


@api_v1.route('/auth/token', methods=['POST'])
def generate_token():
    """Generate a new API token"""
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({
            'success': False,
            'error': 'Username and password required'
        }), 400

    username = data['username']
    password = data['password']

    # Find user
    user = User.query.filter_by(email=username).first()
    if not user:
        return jsonify({
            'success': False,
            'error': 'Invalid credentials'
        }), 401

    # Check password
    login_password_hashed = bcrypt.hashpw(password.encode('utf-8'), user.hash)
    if login_password_hashed != user.password:
        return jsonify({
            'success': False,
            'error': 'Invalid credentials'
        }), 401

    # Generate token
    expiry_hours = data.get('expiry_hours', 24)
    token = Token.generate_token(user.user_id, expiry_hours)

    return jsonify({
        'success': True,
        'data': {
            'token': token.token_hash,
            'expiry': token.expiry.isoformat(),
            'user_id': user.user_id
        }
    }), 201


@api_v1.route('/auth/refresh', methods=['POST'])
@require_token
def refresh_token():
    """Refresh an existing token"""
    auth_header = request.headers.get('Authorization')

    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify('Invalid authorization header'), 401

    token_hash = auth_header.split(' ')[1]

    # Get current token
    current_token = Token.query.filter_by(token_hash=token_hash).first()
    if not current_token:
        return jsonify({
            'success': False,
            'error': 'Token not found'
        }), 404

    # Revoke current token
    Token.revoke_token(token_hash)

    # Generate new token
    expiry_hours = request.get_json().get('expiry_hours', 24)
    new_token = Token.generate_token(current_token.user_id, expiry_hours)

    return jsonify({
        'success': True,
        'data': {
            'token': new_token.token_hash,
            'expiry': new_token.expiry.isoformat(),
            'user_id': current_token.user_id
        }
    }), 200


@api_v1.route('/auth/password', methods=['PUT'])
@require_token
def update_password():
    """Change the password of the token's user, mirroring the legacy bcrypt scheme

    Request Body:
        current_password (str): the user's current password
        new_password (str): the new password (min 6 characters)

    The existing hash is reused as the salt so passwords stay compatible
    with the legacy UI. On success every API token of the user is revoked,
    mirroring the legacy redirect to logout after a password change.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or 'current_password' not in data or 'new_password' not in data:
        return jsonify({
            'success': False,
            'error': 'JSON body with current_password and new_password required'
        }), 400

    user = getattr(request, 'api_user', None) or User.query.first()
    if user is None:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    new_password = str(data['new_password']).strip()
    if len(new_password) < MIN_PASSWORD_LENGTH:
        return jsonify({
            'success': False,
            'error': f'New password must be at least {MIN_PASSWORD_LENGTH} characters'
        }), 400

    login_hashed = bcrypt.hashpw(str(data['current_password']).encode('utf-8'), user.hash)
    if login_hashed != user.password:
        return jsonify({'success': False, 'error': 'Current password does not match'}), 400

    user.password = bcrypt.hashpw(new_password.encode('utf-8'), user.hash)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating password: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

    Token.query.filter_by(user_id=user.user_id).delete()
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Password successfully updated, all API tokens revoked'
    }), 200


@api_v1.route('/auth/revoke', methods=['POST'])
@require_token
def revoke_token():
    """Revoke a token"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify('Invalid authorization header'), 401
    
    token_hash = auth_header.split(' ')[1]

    if Token.revoke_token(token_hash):
        return jsonify({
            'success': True,
            'message': 'Token revoked successfully'
        }), 200
    else:
        return jsonify({
            'success': False,
            'error': 'Token not found'
        }), 404