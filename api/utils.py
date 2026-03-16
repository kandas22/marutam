"""
Utility functions and decorators
"""
import functools
from flask import jsonify, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from database import get_db


def role_required(*allowed_roles):
    """
    Decorator to check if user has required role
    Usage: @role_required('admin', 'mess_user')
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            
            # Get user role from database
            db = get_db()
            result = db.table('users').select('role, is_active').eq('id', user_id).single().execute()
            
            if not result.data:
                return jsonify({'error': 'User not found'}), 404
            
            if not result.data['is_active']:
                return jsonify({'error': 'User account is deactivated'}), 403
            
            user_role = result.data['role']
            
            if user_role not in allowed_roles:
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def admin_required(func):
    """Decorator to check if user is admin"""
    return role_required('admin')(func)


def log_activity(user_id, action, table_name=None, record_id=None, old_data=None, new_data=None):
    """Log user activity to activity_log table"""
    db = get_db()
    
    log_entry = {
        'user_id': user_id,
        'action': action,
        'table_name': table_name,
        'record_id': str(record_id) if record_id else None,
        'old_data': old_data,
        'new_data': new_data,
        'ip_address': request.remote_addr if request else None,
        'user_agent': request.headers.get('User-Agent') if request else None
    }
    
    try:
        db.table('activity_log').insert(log_entry).execute()
    except Exception as e:
        print(f"Failed to log activity: {e}")


def get_current_user():
    """Get current user details from JWT"""
    verify_jwt_in_request()
    user_id = get_jwt_identity()
    db = get_db()
    result = db.table('users').select('*').eq('id', user_id).single().execute()
    return result.data if result.data else None


def paginate_query(query, page=1, per_page=20):
    """Apply pagination to a Supabase query"""
    offset = (page - 1) * per_page
    return query.range(offset, offset + per_page - 1)


def serialize_response(data, message=None, status='success'):
    """Standardize API response format"""
    response = {
        'status': status,
        'data': data
    }
    if message:
        response['message'] = message
    return response
