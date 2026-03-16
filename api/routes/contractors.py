"""
Contractor Management Routes
Admin-only endpoints for managing contractors
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database import get_db
from utils import admin_required, role_required, log_activity, serialize_response, paginate_query

contractors_bp = Blueprint('contractors', __name__)


@contractors_bp.route('', methods=['GET'])
@jwt_required()
@role_required('admin', 'grain_shop_user')
def get_contractors():
    """
    Get all contractors
    Admin and Grain Shop users can view contractors
    """
    db = get_db()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('search')
    active_only = request.args.get('active_only', 'true').lower() == 'true'
    
    query = db.table('contractors').select('*')
    
    if active_only:
        query = query.eq('is_active', True)
    
    if search:
        query = query.or_(f"name.ilike.%{search}%,contact_person.ilike.%{search}%")
    
    query = query.order('name')
    query = paginate_query(query, page, per_page)
    
    result = query.execute()
    
    return jsonify(serialize_response({
        'contractors': result.data,
        'page': page,
        'per_page': per_page
    })), 200


@contractors_bp.route('/<contractor_id>', methods=['GET'])
@jwt_required()
@role_required('admin', 'grain_shop_user')
def get_contractor(contractor_id):
    """Get single contractor details"""
    db = get_db()
    
    result = db.table('contractors').select('*').eq('id', contractor_id).single().execute()
    
    if not result.data:
        return jsonify({'error': 'Contractor not found'}), 404
    
    return jsonify(serialize_response(result.data)), 200


@contractors_bp.route('', methods=['POST'])
@jwt_required()
@admin_required
def create_contractor():
    """
    Create new contractor (Admin only)
    ---
    Request Body:
        - name: Contractor name (required)
        - contact_person: Contact person name (optional)
        - phone: Phone number (optional)
        - email: Email address (optional)
        - address: Address (optional)
        - gst_number: GST number (optional)
    """
    admin_id = get_jwt_identity()
    data = request.get_json()
    
    if not data.get('name'):
        return jsonify({'error': 'Contractor name is required'}), 400
    
    db = get_db()
    
    contractor_data = {
        'name': data['name'],
        'contact_person': data.get('contact_person'),
        'phone': data.get('phone'),
        'email': data.get('email'),
        'address': data.get('address'),
        'gst_number': data.get('gst_number'),
        'tender_year': data.get('tender_year'),
        'tender_start_date': data.get('tender_start_date'),
        'tender_end_date': data.get('tender_end_date'),
        'notes': data.get('notes'),
        'user_id': data.get('user_id'),
        'is_active': True,
        'created_by': admin_id
    }
    
    result = db.table('contractors').insert(contractor_data).execute()
    
    if result.data:
        log_activity(admin_id, 'CREATE', 'contractors', result.data[0]['id'], None, contractor_data)
        return jsonify(serialize_response(result.data[0], 'Contractor created successfully')), 201
    
    return jsonify({'error': 'Failed to create contractor'}), 500


@contractors_bp.route('/<contractor_id>', methods=['PUT'])
@jwt_required()
@admin_required
def update_contractor(contractor_id):
    """
    Update contractor details (Admin only)
    """
    admin_id = get_jwt_identity()
    data = request.get_json()
    
    db = get_db()
    
    # Get existing contractor
    existing = db.table('contractors').select('*').eq('id', contractor_id).single().execute()
    if not existing.data:
        return jsonify({'error': 'Contractor not found'}), 404
    
    # Prepare update data
    update_data = {}
    allowed_fields = [
        'name', 'contact_person', 'phone', 'email', 'address', 'gst_number',
        'is_active', 'tender_year', 'tender_start_date', 'tender_end_date', 'notes', 'user_id'
    ]
    
    for field in allowed_fields:
        if field in data:
            update_data[field] = data[field]
    
    if not update_data:
        return jsonify({'error': 'No valid fields to update'}), 400
    
    result = db.table('contractors').update(update_data).eq('id', contractor_id).execute()
    
    if result.data:
        log_activity(admin_id, 'UPDATE', 'contractors', contractor_id, existing.data, update_data)
        return jsonify(serialize_response(result.data[0], 'Contractor updated successfully')), 200
    
    return jsonify({'error': 'Failed to update contractor'}), 500


@contractors_bp.route('/<contractor_id>', methods=['DELETE'])
@jwt_required()
@admin_required
def delete_contractor(contractor_id):
    """Delete/Deactivate contractor (Admin only)"""
    admin_id = get_jwt_identity()
    
    db = get_db()
    
    existing = db.table('contractors').select('*').eq('id', contractor_id).single().execute()
    if not existing.data:
        return jsonify({'error': 'Contractor not found'}), 404
    
    # Soft delete - deactivate
    db.table('contractors').update({'is_active': False}).eq('id', contractor_id).execute()
    
    log_activity(admin_id, 'DELETE', 'contractors', contractor_id, existing.data, None)
    
    return jsonify(serialize_response(None, 'Contractor deactivated successfully')), 200


@contractors_bp.route('/<contractor_id>/inventory', methods=['GET'])
@jwt_required()
@role_required('admin', 'grain_shop_user')
def get_contractor_inventory(contractor_id):
    """Get inventory items supplied by a specific contractor"""
    db = get_db()
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    
    query = db.table('grain_shop_inventory').select(
        '*, items(name, category, unit), contractors(name)'
    ).eq('contractor_id', contractor_id)
    
    if from_date:
        query = query.gte('received_date', from_date)
    if to_date:
        query = query.lte('received_date', to_date)
    
    query = query.order('received_date', desc=True)
    query = paginate_query(query, page, per_page)
    
    result = query.execute()
    
    return jsonify(serialize_response({
        'inventory': result.data,
        'page': page,
        'per_page': per_page
    })), 200
