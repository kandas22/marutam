"""
Price & Unit Change Management Routes
Endpoints for the price/unit change approval workflow:
  Controller proposes → Admin approves/rejects
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database import get_db
from utils import (
    admin_required, role_required, log_activity,
    serialize_response, paginate_query, get_current_user
)

price_changes_bp = Blueprint('price_changes', __name__)


@price_changes_bp.route('/propose', methods=['POST'])
@jwt_required()
@role_required('grain_shop_user')
def propose_change():
    """
    Controller proposes a price or unit change for an item
    ---
    Request Body:
        - item_id: UUID of the item (required)
        - change_type: 'price' or 'unit' (required)
        - new_value: New price or unit value (required)
    """
    user = get_current_user()
    data = request.get_json()

    if not data.get('item_id') or not data.get('change_type') or 'new_value' not in data:
        return jsonify({'error': 'item_id, change_type, and new_value are required'}), 400

    if data['change_type'] not in ('price', 'unit'):
        return jsonify({'error': 'change_type must be "price" or "unit"'}), 400

    db = get_db()

    # Get current item details
    item = db.table('items').select('*').eq('id', data['item_id']).single().execute()
    if not item.data:
        return jsonify({'error': 'Item not found'}), 404

    old_value = str(item.data.get(data['change_type'], ''))
    new_value = str(data['new_value'])

    # Check if there's already a pending change for this item and type
    existing = db.table('price_change_history').select('id').eq(
        'item_id', data['item_id']
    ).eq('change_type', data['change_type']).eq('approval_status', 'pending').execute()

    if existing.data:
        return jsonify({'error': 'There is already a pending change for this item'}), 400

    change_data = {
        'item_id': data['item_id'],
        'change_type': data['change_type'],
        'old_value': old_value,
        'new_value': new_value,
        'proposed_by': user['id'],
        'approval_status': 'pending'
    }

    result = db.table('price_change_history').insert(change_data).execute()

    if result.data:
        log_activity(user['id'], 'PROPOSE_CHANGE', 'price_change_history', result.data[0]['id'], None, change_data)
        return jsonify(serialize_response(result.data[0], f'{data["change_type"].title()} change proposed for approval')), 201

    return jsonify({'error': 'Failed to propose change'}), 500


@price_changes_bp.route('/pending', methods=['GET'])
@jwt_required()
@role_required('admin', 'grain_shop_user')
def get_pending_changes():
    """Get all pending price/unit change proposals"""
    db = get_db()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    change_type = request.args.get('change_type')

    query = db.table('price_change_history').select(
        '*, items(name, category, unit, price), users!proposed_by(full_name)'
    ).eq('approval_status', 'pending')

    if change_type:
        query = query.eq('change_type', change_type)

    query = query.order('proposed_at', desc=True)
    query = paginate_query(query, page, per_page)
    result = query.execute()

    return jsonify(serialize_response({
        'pending_changes': result.data or [],
        'page': page,
        'per_page': per_page
    })), 200


@price_changes_bp.route('/<change_id>/approve', methods=['POST'])
@jwt_required()
@admin_required
def approve_change(change_id):
    """Admin approves a price/unit change"""
    admin_id = get_jwt_identity()
    db = get_db()

    change = db.table('price_change_history').select('*').eq('id', change_id).single().execute()
    if not change.data:
        return jsonify({'error': 'Change request not found'}), 404
    if change.data['approval_status'] != 'pending':
        return jsonify({'error': 'This change has already been processed'}), 400

    change_data = change.data
    item_id = change_data['item_id']
    change_type = change_data['change_type']
    new_value = change_data['new_value']

    # Apply the change to the item
    update_data = {}
    if change_type == 'price':
        update_data['price'] = float(new_value)
    elif change_type == 'unit':
        update_data['unit'] = new_value

    db.table('items').update(update_data).eq('id', item_id).execute()

    # Update the change record
    db.table('price_change_history').update({
        'approval_status': 'approved',
        'approved_by': admin_id,
        'approved_at': 'now()'
    }).eq('id', change_id).execute()

    log_activity(admin_id, 'APPROVE', 'price_change_history', change_id)
    return jsonify(serialize_response(None, f'{change_type.title()} change approved and applied')), 200


@price_changes_bp.route('/<change_id>/reject', methods=['POST'])
@jwt_required()
@admin_required
def reject_change(change_id):
    """Admin rejects a price/unit change"""
    admin_id = get_jwt_identity()
    data = request.get_json() or {}
    db = get_db()

    change = db.table('price_change_history').select('*').eq('id', change_id).single().execute()
    if not change.data:
        return jsonify({'error': 'Change request not found'}), 404
    if change.data['approval_status'] != 'pending':
        return jsonify({'error': 'This change has already been processed'}), 400

    db.table('price_change_history').update({
        'approval_status': 'rejected',
        'approved_by': admin_id,
        'approved_at': 'now()',
        'rejection_reason': data.get('reason')
    }).eq('id', change_id).execute()

    log_activity(admin_id, 'REJECT', 'price_change_history', change_id)
    return jsonify(serialize_response(None, 'Change request rejected')), 200


@price_changes_bp.route('/history', methods=['GET'])
@jwt_required()
@role_required('admin', 'grain_shop_user')
def get_change_history():
    """Get full history of price/unit changes"""
    db = get_db()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    item_id = request.args.get('item_id')
    status = request.args.get('status')

    query = db.table('price_change_history').select(
        '*, items(name, category, unit, price), users!proposed_by(full_name)'
    )

    if item_id:
        query = query.eq('item_id', item_id)
    if status:
        query = query.eq('approval_status', status)

    query = query.order('proposed_at', desc=True)
    query = paginate_query(query, page, per_page)
    result = query.execute()

    return jsonify(serialize_response({
        'history': result.data or [],
        'page': page,
        'per_page': per_page
    })), 200
