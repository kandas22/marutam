"""
Authentication Routes
Handles login, logout, and token management
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, 
    jwt_required, 
    get_jwt_identity,
    get_jwt
)
import bcrypt
from database import get_db
from utils import log_activity, serialize_response

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    User login endpoint
    ---
    Request Body:
        - username: Username
        - password: User password
    Returns:
        - access_token: JWT token for authentication
        - user: User details
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400
    
    db = get_db()
    
    # Get user by username
    try:
        result = db.table('users').select('*').eq('username', username).single().execute()
    except Exception as e:
        return jsonify({'error': 'Database connection error: Unable to reach the database. Please check your network connection.'}), 503
    
    if not result.data:
        return jsonify({'error': 'Invalid credentials'}), 401
    
    user = result.data
    
    # Check if user is active
    if not user['is_active']:
        return jsonify({'error': 'Account is deactivated. Contact administrator.'}), 403
    
    # Verify password
    try:
        if not bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            return jsonify({'error': 'Invalid credentials'}), 401
    except Exception:
        return jsonify({'error': 'Invalid credentials'}), 401
    
    # Create access token with user info
    access_token = create_access_token(
        identity=user['id'],
        additional_claims={
            'role': user['role'],
            'email': user['email']
        }
    )
    
    # Log login activity
    log_activity(user['id'], 'LOGIN')
    
    # Remove password hash from response
    user.pop('password_hash', None)
    
    return jsonify(serialize_response({
        'access_token': access_token,
        'user': user
    }, 'Login successful')), 200


@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """
    User logout endpoint
    Logs the logout activity
    """
    user_id = get_jwt_identity()
    log_activity(user_id, 'LOGOUT')
    
    return jsonify(serialize_response(None, 'Logout successful')), 200


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """
    Get current logged-in user details
    """
    user_id = get_jwt_identity()
    db = get_db()
    
    result = db.table('users').select('*').eq('id', user_id).single().execute()
    
    if not result.data:
        return jsonify({'error': 'User not found'}), 404
    
    user = result.data
    user.pop('password_hash', None)
    
    return jsonify(serialize_response(user)), 200


@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """
    Change user password
    ---
    Request Body:
        - current_password: Current password
        - new_password: New password
    """
    user_id = get_jwt_identity()
    data = request.get_json()
    
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    
    if not current_password or not new_password:
        return jsonify({'error': 'Current and new password are required'}), 400
    
    if len(new_password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    
    db = get_db()
    
    # Get current user
    result = db.table('users').select('password_hash').eq('id', user_id).single().execute()
    
    if not result.data:
        return jsonify({'error': 'User not found'}), 404
    
    # Verify current password
    if not bcrypt.checkpw(current_password.encode('utf-8'), result.data['password_hash'].encode('utf-8')):
        return jsonify({'error': 'Current password is incorrect'}), 401
    
    # Hash new password
    new_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    # Update password
    db.table('users').update({'password_hash': new_hash}).eq('id', user_id).execute()
    
    log_activity(user_id, 'PASSWORD_CHANGE')
    
    return jsonify(serialize_response(None, 'Password changed successfully')), 200
