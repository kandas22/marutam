"""
Mess Management Routes
Endpoints for managing mess units and their rations
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database import get_db
from utils import admin_required, role_required, log_activity, serialize_response, paginate_query, get_current_user

mess_bp = Blueprint('mess', __name__)


@mess_bp.route('', methods=['GET'])
@jwt_required()
def get_mess_units():
    """
    Get all mess units
    Admin sees all, mess users see only their assigned mess
    """
    user = get_current_user()
    db = get_db()
    
    query = db.table('mess').select('*, users!manager_id(full_name, email)')
    
    # Non-admin users can only see mess they manage
    if user['role'] == 'mess_user':
        query = query.eq('manager_id', user['id'])
    
    query = query.eq('is_active', True).order('name')
    result = query.execute()
    
    return jsonify(serialize_response(result.data)), 200


@mess_bp.route('/<mess_id>', methods=['GET'])
@jwt_required()
@role_required('admin', 'mess_user')
def get_mess(mess_id):
    """Get single mess details"""
    user = get_current_user()
    db = get_db()
    
    result = db.table('mess').select('*, users!manager_id(full_name, email)').eq('id', mess_id).single().execute()
    
    if not result.data:
        return jsonify({'error': 'Mess not found'}), 404
    
    # Non-admin can only view their own mess
    if user['role'] == 'mess_user' and result.data.get('manager_id') != user['id']:
        return jsonify({'error': 'Access denied'}), 403
    
    return jsonify(serialize_response(result.data)), 200


@mess_bp.route('', methods=['POST'])
@jwt_required()
@admin_required
def create_mess():
    """
    Create new mess unit (Admin only)
    ---
    Request Body:
        - name: Mess name (required)
        - location: Location (optional)
        - capacity: Capacity (optional)
        - manager_id: User ID of mess manager (optional)
    """
    admin_id = get_jwt_identity()
    data = request.get_json()
    
    if not data.get('name'):
        return jsonify({'error': 'Mess name is required'}), 400
    
    db = get_db()
    
    # Validate manager if provided (any non-admin user can be a manager)
    if data.get('manager_id'):
        manager = db.table('users').select('id, role').eq('id', data['manager_id']).single().execute()
        if not manager.data:
            return jsonify({'error': 'Selected manager user not found.'}), 400
        if manager.data['role'] == 'admin':
            return jsonify({'error': 'Admin users cannot be assigned as mess managers.'}), 400
    
    mess_data = {
        'name': data['name'],
        'location': data.get('location'),
        'capacity': data.get('capacity'),
        'manager_id': data.get('manager_id'),
        'is_active': True
    }
    
    result = db.table('mess').insert(mess_data).execute()
    
    if result.data:
        log_activity(admin_id, 'CREATE', 'mess', result.data[0]['id'], None, mess_data)
        return jsonify(serialize_response(result.data[0], 'Mess created successfully')), 201
    
    return jsonify({'error': 'Failed to create mess'}), 500


@mess_bp.route('/<mess_id>', methods=['PUT'])
@jwt_required()
@admin_required
def update_mess(mess_id):
    """Update mess details (Admin only)"""
    admin_id = get_jwt_identity()
    data = request.get_json()
    
    db = get_db()
    
    existing = db.table('mess').select('*').eq('id', mess_id).single().execute()
    if not existing.data:
        return jsonify({'error': 'Mess not found'}), 404
    
    update_data = {}
    allowed_fields = ['name', 'location', 'capacity', 'manager_id', 'is_active']
    
    for field in allowed_fields:
        if field in data:
            update_data[field] = data[field]
    
    # Validate manager if provided (any non-admin user can be a manager)
    if 'manager_id' in update_data and update_data['manager_id']:
        manager = db.table('users').select('id, role').eq('id', update_data['manager_id']).single().execute()
        if not manager.data:
            return jsonify({'error': 'Selected manager user not found.'}), 400
        if manager.data['role'] == 'admin':
            return jsonify({'error': 'Admin users cannot be assigned as mess managers.'}), 400
    
    if not update_data:
        return jsonify({'error': 'No valid fields to update'}), 400
    
    result = db.table('mess').update(update_data).eq('id', mess_id).execute()
    
    if result.data:
        log_activity(admin_id, 'UPDATE', 'mess', mess_id, existing.data, update_data)
        return jsonify(serialize_response(result.data[0], 'Mess updated successfully')), 200
    
    return jsonify({'error': 'Failed to update mess'}), 500


@mess_bp.route('/<mess_id>', methods=['DELETE'])
@jwt_required()
@admin_required
def delete_mess(mess_id):
    """Delete/Deactivate mess (Admin only)"""
    admin_id = get_jwt_identity()
    
    db = get_db()
    
    existing = db.table('mess').select('*').eq('id', mess_id).single().execute()
    if not existing.data:
        return jsonify({'error': 'Mess not found'}), 404
    
    db.table('mess').update({'is_active': False}).eq('id', mess_id).execute()
    
    log_activity(admin_id, 'DELETE', 'mess', mess_id, existing.data, None)
    
    return jsonify(serialize_response(None, 'Mess deactivated successfully')), 200


# =====================================================
# MESS INVENTORY ROUTES
# =====================================================

@mess_bp.route('/<mess_id>/inventory', methods=['GET'])
@jwt_required()
@role_required('admin', 'mess_user')
def get_mess_inventory(mess_id):
    """Get current inventory for a mess"""
    user = get_current_user()
    db = get_db()
    
    # Verify access
    if user['role'] == 'mess_user':
        mess = db.table('mess').select('manager_id').eq('id', mess_id).single().execute()
        if not mess.data or mess.data['manager_id'] != user['id']:
            return jsonify({'error': 'Access denied'}), 403
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    category = request.args.get('category')
    
    query = db.table('mess_inventory').select(
        '*, items(name, category, unit)'
    ).eq('mess_id', mess_id)
    
    if category:
        query = query.eq('items.category', category)
    
    query = query.order('date', desc=True)
    query = paginate_query(query, page, per_page)
    
    result = query.execute()
    
    return jsonify(serialize_response({
        'inventory': result.data,
        'page': page,
        'per_page': per_page
    })), 200


@mess_bp.route('/<mess_id>/inventory', methods=['POST'])
@jwt_required()
@role_required('admin', 'mess_user')
def add_mess_inventory(mess_id):
    """
    Add inventory item to mess
    ---
    Request Body:
        - item_id: Item ID (required)
        - quantity: Quantity (required)
        - date: Date (optional, defaults to today)
    """
    user = get_current_user()
    db = get_db()
    
    # Verify access for mess users
    if user['role'] == 'mess_user':
        mess = db.table('mess').select('manager_id').eq('id', mess_id).single().execute()
        if not mess.data or mess.data['manager_id'] != user['id']:
            return jsonify({'error': 'Access denied'}), 403
    
    data = request.get_json()
    
    if not data.get('item_id') or not data.get('quantity'):
        return jsonify({'error': 'item_id and quantity are required'}), 400
    
    inventory_data = {
        'mess_id': mess_id,
        'item_id': data['item_id'],
        'quantity': float(data['quantity']),
        'date': data.get('date'),
        'recorded_by': user['id']
    }
    
    result = db.table('mess_inventory').insert(inventory_data).execute()
    
    if result.data:
        log_activity(user['id'], 'CREATE', 'mess_inventory', result.data[0]['id'], None, inventory_data)
        return jsonify(serialize_response(result.data[0], 'Inventory added successfully')), 201
    
    return jsonify({'error': 'Failed to add inventory'}), 500


# =====================================================
# DAILY RATION USAGE
# =====================================================

@mess_bp.route('/<mess_id>/daily-usage', methods=['GET'])
@jwt_required()
@role_required('admin', 'mess_user')
def get_daily_usage(mess_id):
    """Get daily ration usage for a mess"""
    user = get_current_user()
    db = get_db()
    
    # Verify access for mess users
    if user['role'] == 'mess_user':
        mess = db.table('mess').select('manager_id').eq('id', mess_id).single().execute()
        if not mess.data or mess.data['manager_id'] != user['id']:
            return jsonify({'error': 'Access denied'}), 403
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    status = request.args.get('status')
    
    query = db.table('daily_ration_usage').select(
        '*, items(name, category, unit), users!recorded_by(full_name)'
    ).eq('mess_id', mess_id)
    
    if from_date:
        query = query.gte('usage_date', from_date)
    if to_date:
        query = query.lte('usage_date', to_date)
    if status:
        query = query.eq('approval_status', status)
    
    query = query.order('usage_date', desc=True).order('meal_type')
    query = paginate_query(query, page, per_page)
    
    result = query.execute()
    
    return jsonify(serialize_response({
        'usage': result.data,
        'page': page,
        'per_page': per_page
    })), 200


@mess_bp.route('/<mess_id>/daily-usage', methods=['POST'])
@jwt_required()
@role_required('admin', 'mess_user')
def add_daily_usage(mess_id):
    """
    Record daily ration usage (requires approval)
    ---
    Request Body:
        - item_id: Item ID (required)
        - quantity_used: Quantity used (required)
        - usage_date: Date of usage (optional, defaults to today)
        - meal_type: Meal type - breakfast, lunch, dinner (optional)
        - personnel_count: Number of personnel served (optional)
        - notes: Additional notes (optional)
    """
    user = get_current_user()
    db = get_db()
    
    # Verify access for mess users
    if user['role'] == 'mess_user':
        mess = db.table('mess').select('manager_id').eq('id', mess_id).single().execute()
        if not mess.data or mess.data['manager_id'] != user['id']:
            return jsonify({'error': 'Access denied'}), 403
    
    data = request.get_json()
    
    if not data.get('item_id') or not data.get('quantity_used'):
        return jsonify({'error': 'item_id and quantity_used are required'}), 400
    
    # Admin entries are auto-approved, mess user entries require approval
    approval_status = 'approved' if user['role'] == 'admin' else 'pending'
    
    usage_data = {
        'mess_id': mess_id,
        'item_id': data['item_id'],
        'quantity_used': float(data['quantity_used']),
        'usage_date': data.get('usage_date'),
        'meal_type': data.get('meal_type'),
        'personnel_count': data.get('personnel_count'),
        'notes': data.get('notes'),
        'recorded_by': user['id'],
        'approval_status': approval_status
    }
    
    # If admin-created, set approval fields
    if user['role'] == 'admin':
        usage_data['approved_by'] = user['id']
    
    result = db.table('daily_ration_usage').insert(usage_data).execute()
    
    if result.data:
        log_activity(user['id'], 'CREATE', 'daily_ration_usage', result.data[0]['id'], None, usage_data)
        
        message = 'Daily usage recorded successfully'
        if approval_status == 'pending':
            message += ' (pending approval)'
        
        return jsonify(serialize_response(result.data[0], message)), 201
    
    return jsonify({'error': 'Failed to record daily usage'}), 500


@mess_bp.route('/<mess_id>/daily-usage/<usage_id>', methods=['PUT'])
@jwt_required()
@role_required('admin', 'mess_user')
def update_daily_usage(mess_id, usage_id):
    """
    Update daily usage record
    For mess users, creates a pending update request
    For admin, updates directly
    """
    user = get_current_user()
    db = get_db()
    
    # Get existing record
    existing = db.table('daily_ration_usage').select('*').eq('id', usage_id).eq('mess_id', mess_id).single().execute()
    
    if not existing.data:
        return jsonify({'error': 'Usage record not found'}), 404
    
    # Verify access for mess users
    if user['role'] == 'mess_user':
        mess = db.table('mess').select('manager_id').eq('id', mess_id).single().execute()
        if not mess.data or mess.data['manager_id'] != user['id']:
            return jsonify({'error': 'Access denied'}), 403
    
    data = request.get_json()
    
    update_data = {}
    allowed_fields = ['quantity_used', 'usage_date', 'meal_type', 'personnel_count', 'notes']
    
    for field in allowed_fields:
        if field in data:
            update_data[field] = data[field]
    
    if not update_data:
        return jsonify({'error': 'No valid fields to update'}), 400
    
    # Admin can update directly
    if user['role'] == 'admin':
        result = db.table('daily_ration_usage').update(update_data).eq('id', usage_id).execute()
        
        if result.data:
            log_activity(user['id'], 'UPDATE', 'daily_ration_usage', usage_id, existing.data, update_data)
            return jsonify(serialize_response(result.data[0], 'Usage record updated successfully')), 200
    else:
        # Mess user - create pending update request
        for field, new_value in update_data.items():
            pending_data = {
                'table_name': 'daily_ration_usage',
                'record_id': usage_id,
                'field_name': field,
                'old_value': str(existing.data.get(field)),
                'new_value': str(new_value),
                'requested_by': user['id'],
                'approval_status': 'pending'
            }
            db.table('pending_updates').insert(pending_data).execute()
        
        log_activity(user['id'], 'UPDATE_REQUEST', 'daily_ration_usage', usage_id, existing.data, update_data)
        return jsonify(serialize_response(None, 'Update request submitted for approval')), 200
    
    return jsonify({'error': 'Failed to update usage record'}), 500
