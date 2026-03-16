"""
User Management Routes
Admin-only endpoints for managing users
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import bcrypt
from database import get_db
from utils import admin_required, log_activity, serialize_response, paginate_query

users_bp = Blueprint('users', __name__)


@users_bp.route('', methods=['GET'])
@jwt_required()
@admin_required
def get_users():
    """
    Get all users (Admin only)
    Query params:
        - page: Page number (default: 1)
        - per_page: Items per page (default: 20)
        - role: Filter by role
        - search: Search by name or email
    """
    db = get_db()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    role = request.args.get('role')
    search = request.args.get('search')
    
    query = db.table('users').select('id, username, email, full_name, role, phone, manager_id, is_active, created_at')
    
    if role:
        query = query.eq('role', role)
    
    if search:
        query = query.or_(f"full_name.ilike.%{search}%,email.ilike.%{search}%,username.ilike.%{search}%")
    
    query = query.order('created_at', desc=True)
    query = paginate_query(query, page, per_page)
    
    result = query.execute()
    
    return jsonify(serialize_response({
        'users': result.data,
        'page': page,
        'per_page': per_page
    })), 200


@users_bp.route('/<user_id>', methods=['GET'])
@jwt_required()
@admin_required
def get_user(user_id):
    """Get single user details (Admin only)"""
    db = get_db()
    
    result = db.table('users').select(
        'id, username, email, full_name, role, phone, manager_id, is_active, created_at, updated_at'
    ).eq('id', user_id).single().execute()
    
    if not result.data:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify(serialize_response(result.data)), 200


@users_bp.route('/managers', methods=['GET'])
@jwt_required()
def get_managers():
    """
    Get list of admin users who can be assigned as managers
    """
    db = get_db()
    result = db.table('users').select('id, full_name, username, role').eq('role', 'admin').eq('is_active', True).execute()
    
    managers = result.data if result.data else []
    return jsonify(serialize_response({'managers': managers})), 200


@users_bp.route('', methods=['POST'])
@jwt_required()
@admin_required
def create_user():
    """
    Create new user (Admin only)
    ---
    Request Body:
        - username: Username for login (required)
        - password: User password (required)
        - full_name: Full name (required)
        - role: User role - mess_user or grain_shop_user (required)
        - phone: Phone number (required)
        - email: User email (optional)
        - manager_id: UUID of the assigned manager (optional)
    """
    admin_id = get_jwt_identity()
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['username', 'password', 'full_name', 'role', 'phone']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400
    
    # Validate role - admin cannot create other admins
    # contractor role is for suppliers selected via yearly tender process
    allowed_roles = ['mess_user', 'grain_shop_user', 'contractor']
    if data['role'] not in allowed_roles:
        return jsonify({'error': f'Role must be one of: {", ".join(allowed_roles)}'}), 400
    
    # Validate password length
    if len(data['password']) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    
    db = get_db()
    
    # Check if email already exists (only if email is provided)
    if data.get('email'):
        existing = db.table('users').select('id').eq('email', data['email']).execute()
        if existing.data:
            return jsonify({'error': 'Email already registered'}), 409
    
    # Check if username already exists
    existing_username = db.table('users').select('id').eq('username', data['username']).execute()
    if existing_username.data:
        return jsonify({'error': 'Username already taken'}), 409
    
    # Validate manager_id if provided
    manager_id = data.get('manager_id')
    if manager_id:
        manager = db.table('users').select('id, role').eq('id', manager_id).eq('is_active', True).single().execute()
        if not manager.data:
            return jsonify({'error': 'Selected manager not found'}), 404
        if manager.data['role'] != 'admin':
            return jsonify({'error': 'Manager must be an admin user'}), 400
    
    # Hash password
    password_hash = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    # Create user
    user_data = {
        'username': data['username'],
        'password_hash': password_hash,
        'full_name': data['full_name'],
        'role': data['role'],
        'phone': data['phone'],
        'is_active': True,
        'created_by': admin_id
    }
    
    # Add optional fields
    if data.get('email'):
        user_data['email'] = data['email']
    if manager_id:
        user_data['manager_id'] = manager_id
    
    result = db.table('users').insert(user_data).execute()
    
    if result.data:
        new_user = result.data[0]
        new_user.pop('password_hash', None)
        
        log_activity(admin_id, 'CREATE', 'users', new_user['id'], None, user_data)
        
        return jsonify(serialize_response(new_user, 'User created successfully')), 201
    
    return jsonify({'error': 'Failed to create user'}), 500


@users_bp.route('/<user_id>', methods=['PUT'])
@jwt_required()
@admin_required
def update_user(user_id):
    """
    Update user details (Admin only)
    ---
    Request Body:
        - full_name: Full name (optional)
        - phone: Phone number (optional)
        - is_active: Active status (optional)
    """
    admin_id = get_jwt_identity()
    data = request.get_json()
    
    db = get_db()
    
    # Get existing user
    existing = db.table('users').select('*').eq('id', user_id).single().execute()
    if not existing.data:
        return jsonify({'error': 'User not found'}), 404
    
    # Prevent modifying admin users
    if existing.data['role'] == 'admin' and user_id != admin_id:
        return jsonify({'error': 'Cannot modify other admin accounts'}), 403
    
    # Prepare update data
    update_data = {}
    allowed_fields = ['full_name', 'phone', 'is_active', 'manager_id']
    
    for field in allowed_fields:
        if field in data:
            update_data[field] = data[field]
    
    if not update_data:
        return jsonify({'error': 'No valid fields to update'}), 400
    
    # Update user
    result = db.table('users').update(update_data).eq('id', user_id).execute()
    
    if result.data:
        updated_user = result.data[0]
        updated_user.pop('password_hash', None)
        
        log_activity(admin_id, 'UPDATE', 'users', user_id, existing.data, update_data)
        
        return jsonify(serialize_response(updated_user, 'User updated successfully')), 200
    
    return jsonify({'error': 'Failed to update user'}), 500


@users_bp.route('/<user_id>', methods=['DELETE'])
@jwt_required()
@admin_required
def delete_user(user_id):
    """
    Delete/Deactivate user (Admin only)
    Actually deactivates the user instead of hard delete
    """
    admin_id = get_jwt_identity()
    
    if user_id == admin_id:
        return jsonify({'error': 'Cannot delete your own account'}), 403
    
    db = get_db()
    
    # Get existing user
    existing = db.table('users').select('*').eq('id', user_id).single().execute()
    if not existing.data:
        return jsonify({'error': 'User not found'}), 404
    
    # Prevent deleting admin users
    if existing.data['role'] == 'admin':
        return jsonify({'error': 'Cannot delete admin accounts'}), 403
    
    # Soft delete - deactivate user
    db.table('users').update({'is_active': False}).eq('id', user_id).execute()
    
    log_activity(admin_id, 'DELETE', 'users', user_id, existing.data, None)
    
    return jsonify(serialize_response(None, 'User deactivated successfully')), 200


@users_bp.route('/<user_id>/reset-password', methods=['POST'])
@jwt_required()
@admin_required
def reset_user_password(user_id):
    """
    Reset user password (Admin only)
    ---
    Request Body:
        - new_password: New password for the user
    """
    admin_id = get_jwt_identity()
    data = request.get_json()
    
    new_password = data.get('new_password')
    if not new_password or len(new_password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    
    db = get_db()
    
    # Check user exists
    existing = db.table('users').select('id, role').eq('id', user_id).single().execute()
    if not existing.data:
        return jsonify({'error': 'User not found'}), 404
    
    # Hash new password
    password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    db.table('users').update({'password_hash': password_hash}).eq('id', user_id).execute()
    
    log_activity(admin_id, 'PASSWORD_RESET', 'users', user_id)
    
    return jsonify(serialize_response(None, 'Password reset successfully')), 200
