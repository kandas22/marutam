"""
Demand Management Routes
Endpoints for the complete demand workflow:
  Step 1: Mess submits demand
  Step 2: Controller consolidates
  Step 3: Admin approves/rejects
  Step 4: Controller forwards to contractor
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database import get_db
from utils import (
    admin_required, role_required, log_activity,
    serialize_response, paginate_query, get_current_user
)

demands_bp = Blueprint('demands', __name__)


# =====================================================
# STEP 1: MESS SUBMITS DEMAND
# =====================================================

@demands_bp.route('', methods=['POST'])
@jwt_required()
@role_required('mess_user')
def create_demand():
    """
    Create a new demand (Mess In-Charge only)
    ---
    Request Body:
        - mess_id: UUID of the mess submitting demand (required)
        - demand_date: Date for the demand (optional, defaults to today)
        - notes: Additional notes (optional)
        - items: List of items with quantities (required)
            - item_id: UUID of the item
            - requested_quantity: Quantity needed
            - notes: Item-level notes (optional)
    """
    user = get_current_user()
    data = request.get_json()

    if not data.get('mess_id'):
        return jsonify({'error': 'mess_id is required'}), 400
    if not data.get('items') or not isinstance(data['items'], list) or len(data['items']) == 0:
        return jsonify({'error': 'At least one item is required'}), 400

    db = get_db()

    # Verify the mess belongs to this user
    mess = db.table('mess').select('id, manager_id').eq('id', data['mess_id']).single().execute()
    if not mess.data:
        return jsonify({'error': 'Mess not found'}), 404
    if mess.data.get('manager_id') != user['id']:
        return jsonify({'error': 'You can only submit demands for your assigned mess'}), 403

    # Create the demand
    demand_data = {
        'mess_id': data['mess_id'],
        'demand_date': data.get('demand_date'),
        'status': 'draft',
        'notes': data.get('notes'),
        'submitted_by': user['id']
    }

    result = db.table('demands').insert(demand_data).execute()
    if not result.data:
        return jsonify({'error': 'Failed to create demand'}), 500

    demand = result.data[0]
    demand_id = demand['id']

    # Insert demand items
    items_to_insert = []
    for item in data['items']:
        if not item.get('item_id') or not item.get('requested_quantity'):
            continue
        items_to_insert.append({
            'demand_id': demand_id,
            'item_id': item['item_id'],
            'requested_quantity': float(item['requested_quantity']),
            'notes': item.get('notes')
        })

    if items_to_insert:
        db.table('demand_items').insert(items_to_insert).execute()

    log_activity(user['id'], 'CREATE', 'demands', demand_id, None, demand_data)

    return jsonify(serialize_response(demand, 'Demand created as draft')), 201


@demands_bp.route('/<demand_id>/submit', methods=['POST'])
@jwt_required()
@role_required('mess_user')
def submit_demand(demand_id):
    """Submit a draft demand for controller review (Step 1 → Step 2)"""
    user = get_current_user()
    db = get_db()

    demand = db.table('demands').select('*, mess(manager_id)').eq('id', demand_id).single().execute()
    if not demand.data:
        return jsonify({'error': 'Demand not found'}), 404
    if demand.data['status'] != 'draft':
        return jsonify({'error': 'Only draft demands can be submitted'}), 400
    if demand.data.get('mess', {}).get('manager_id') != user['id']:
        return jsonify({'error': 'Access denied'}), 403

    result = db.table('demands').update({
        'status': 'submitted',
        'submitted_by': user['id'],
        'submitted_at': 'now()'
    }).eq('id', demand_id).execute()

    log_activity(user['id'], 'SUBMIT', 'demands', demand_id)
    return jsonify(serialize_response(result.data[0] if result.data else None, 'Demand submitted for review')), 200


# =====================================================
# STEP 2: CONTROLLER VIEWS / CONSOLIDATES DEMANDS
# =====================================================

@demands_bp.route('', methods=['GET'])
@jwt_required()
def get_demands():
    """
    Get demands based on role:
    - Admin: All demands
    - Controller (grain_shop_user): All demands
    - Contractor: Only approved/forwarded demands
    - Mess user: Only their own mess demands
    """
    user = get_current_user()
    db = get_db()
    role = user.get('role', '')

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status_filter = request.args.get('status')
    mess_filter = request.args.get('mess_id')
    category_filter = request.args.get('category')
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')

    query = db.table('demands').select(
        '*, mess(name), users!submitted_by(full_name), contractors(name)'
    )

    # Role-based filtering
    if role == 'mess_user':
        # Get messes managed by this user
        messes = db.table('mess').select('id').eq('manager_id', user['id']).execute()
        mess_ids = [m['id'] for m in messes.data] if messes.data else []
        if mess_ids:
            query = query.in_('mess_id', mess_ids)
        else:
            return jsonify(serialize_response({'demands': [], 'page': page, 'per_page': per_page})), 200
    elif role == 'contractor':
        # Contractors can only see approved/forwarded demands
        query = query.in_('status', ['approved', 'forwarded_to_contractor', 'supplied_to_controller', 'distributed_to_messes'])

    if status_filter:
        query = query.eq('status', status_filter)
    if mess_filter:
        query = query.eq('mess_id', mess_filter)
    if from_date:
        query = query.gte('demand_date', from_date)
    if to_date:
        query = query.lte('demand_date', to_date)

    query = query.order('demand_date', desc=True)
    query = paginate_query(query, page, per_page)
    result = query.execute()

    return jsonify(serialize_response({
        'demands': result.data or [],
        'page': page,
        'per_page': per_page
    })), 200


@demands_bp.route('/<demand_id>', methods=['GET'])
@jwt_required()
def get_demand(demand_id):
    """Get single demand with its items"""
    user = get_current_user()
    db = get_db()

    demand = db.table('demands').select(
        '*, mess(name), users!submitted_by(full_name), contractors(name)'
    ).eq('id', demand_id).single().execute()

    if not demand.data:
        return jsonify({'error': 'Demand not found'}), 404

    # Get demand items
    items = db.table('demand_items').select(
        '*, items(name, category, unit, price)'
    ).eq('demand_id', demand_id).execute()

    response_data = demand.data
    response_data['demand_items'] = items.data or []

    return jsonify(serialize_response(response_data)), 200


@demands_bp.route('/<demand_id>', methods=['PUT'])
@jwt_required()
@role_required('mess_user', 'grain_shop_user')
def update_demand(demand_id):
    """Update a draft demand (items, notes, etc.)"""
    user = get_current_user()
    data = request.get_json()
    db = get_db()

    demand = db.table('demands').select('*').eq('id', demand_id).single().execute()
    if not demand.data:
        return jsonify({'error': 'Demand not found'}), 404
    if demand.data['status'] != 'draft':
        return jsonify({'error': 'Only draft demands can be edited'}), 400

    # Update demand notes
    update_data = {}
    if 'notes' in data:
        update_data['notes'] = data['notes']
    if 'demand_date' in data:
        update_data['demand_date'] = data['demand_date']

    if update_data:
        db.table('demands').update(update_data).eq('id', demand_id).execute()

    # Update items if provided
    if 'items' in data and isinstance(data['items'], list):
        # Remove existing items and re-insert
        db.table('demand_items').delete().eq('demand_id', demand_id).execute()
        items_to_insert = []
        for item in data['items']:
            if item.get('item_id') and item.get('requested_quantity'):
                items_to_insert.append({
                    'demand_id': demand_id,
                    'item_id': item['item_id'],
                    'requested_quantity': float(item['requested_quantity']),
                    'notes': item.get('notes')
                })
        if items_to_insert:
            db.table('demand_items').insert(items_to_insert).execute()

    log_activity(user['id'], 'UPDATE', 'demands', demand_id)
    return jsonify(serialize_response(None, 'Demand updated successfully')), 200


@demands_bp.route('/<demand_id>', methods=['DELETE'])
@jwt_required()
@role_required('mess_user', 'admin')
def delete_demand(demand_id):
    """Delete a draft demand"""
    user = get_current_user()
    db = get_db()

    demand = db.table('demands').select('*').eq('id', demand_id).single().execute()
    if not demand.data:
        return jsonify({'error': 'Demand not found'}), 404
    if demand.data['status'] != 'draft':
        return jsonify({'error': 'Only draft demands can be deleted'}), 400

    # Delete items first (cascade)
    db.table('demand_items').delete().eq('demand_id', demand_id).execute()
    db.table('demands').delete().eq('id', demand_id).execute()

    log_activity(user['id'], 'DELETE', 'demands', demand_id)
    return jsonify(serialize_response(None, 'Demand deleted')), 200


# =====================================================
# STEP 3: ADMIN APPROVES / REJECTS DEMAND
# =====================================================

@demands_bp.route('/<demand_id>/approve', methods=['POST'])
@jwt_required()
@admin_required
def approve_demand(demand_id):
    """
    Admin approves a submitted demand
    Optionally adjust approved quantities
    ---
    Request Body (optional):
        - items: List of { demand_item_id, approved_quantity }
    """
    admin_id = get_jwt_identity()
    data = request.get_json() or {}
    db = get_db()

    demand = db.table('demands').select('*').eq('id', demand_id).single().execute()
    if not demand.data:
        return jsonify({'error': 'Demand not found'}), 404
    if demand.data['status'] != 'submitted':
        return jsonify({'error': 'Only submitted demands can be approved'}), 400

    # Update approved quantities if provided
    if 'items' in data and isinstance(data['items'], list):
        for item_update in data['items']:
            if item_update.get('demand_item_id') and 'approved_quantity' in item_update:
                db.table('demand_items').update({
                    'approved_quantity': float(item_update['approved_quantity'])
                }).eq('id', item_update['demand_item_id']).execute()
    else:
        # Auto-approve all with requested quantities
        demand_items = db.table('demand_items').select('id, requested_quantity').eq('demand_id', demand_id).execute()
        for di in (demand_items.data or []):
            db.table('demand_items').update({
                'approved_quantity': di['requested_quantity']
            }).eq('id', di['id']).execute()

    result = db.table('demands').update({
        'status': 'approved',
        'reviewed_by': admin_id,
        'reviewed_at': 'now()'
    }).eq('id', demand_id).execute()

    log_activity(admin_id, 'APPROVE', 'demands', demand_id)
    return jsonify(serialize_response(result.data[0] if result.data else None, 'Demand approved')), 200


@demands_bp.route('/<demand_id>/reject', methods=['POST'])
@jwt_required()
@admin_required
def reject_demand(demand_id):
    """
    Admin rejects a submitted demand
    ---
    Request Body:
        - reason: Rejection reason (optional)
    """
    admin_id = get_jwt_identity()
    data = request.get_json() or {}
    db = get_db()

    demand = db.table('demands').select('*').eq('id', demand_id).single().execute()
    if not demand.data:
        return jsonify({'error': 'Demand not found'}), 404
    if demand.data['status'] != 'submitted':
        return jsonify({'error': 'Only submitted demands can be rejected'}), 400

    result = db.table('demands').update({
        'status': 'rejected',
        'reviewed_by': admin_id,
        'reviewed_at': 'now()',
        'rejection_reason': data.get('reason')
    }).eq('id', demand_id).execute()

    log_activity(admin_id, 'REJECT', 'demands', demand_id)
    return jsonify(serialize_response(result.data[0] if result.data else None, 'Demand rejected')), 200


# =====================================================
# STEP 4: CONTROLLER FORWARDS TO CONTRACTOR
# =====================================================

@demands_bp.route('/<demand_id>/forward', methods=['POST'])
@jwt_required()
@role_required('grain_shop_user', 'admin')
def forward_to_contractor(demand_id):
    """
    Controller forwards approved demand to contractor
    ---
    Request Body:
        - contractor_id: UUID of the contractor (required)
    """
    user = get_current_user()
    data = request.get_json()
    db = get_db()

    if not data.get('contractor_id'):
        return jsonify({'error': 'contractor_id is required'}), 400

    demand = db.table('demands').select('*').eq('id', demand_id).single().execute()
    if not demand.data:
        return jsonify({'error': 'Demand not found'}), 404
    if demand.data['status'] != 'approved':
        return jsonify({'error': 'Only approved demands can be forwarded'}), 400

    # Verify contractor exists and is active
    contractor = db.table('contractors').select('id').eq('id', data['contractor_id']).eq('is_active', True).single().execute()
    if not contractor.data:
        return jsonify({'error': 'Active contractor not found'}), 404

    result = db.table('demands').update({
        'status': 'forwarded_to_contractor',
        'contractor_id': data['contractor_id'],
        'forwarded_by': user['id'],
        'forwarded_at': 'now()'
    }).eq('id', demand_id).execute()

    log_activity(user['id'], 'FORWARD', 'demands', demand_id)
    return jsonify(serialize_response(result.data[0] if result.data else None, 'Demand forwarded to contractor')), 200


# =====================================================
# CONSOLIDATED DEMAND REPORT (CONTROLLER → ADMIN)
# =====================================================

@demands_bp.route('/consolidated', methods=['GET'])
@jwt_required()
@role_required('admin', 'grain_shop_user')
def get_consolidated_demands():
    """
    Get consolidated demand report across all messes
    Grouped by item and category
    """
    db = get_db()
    status_filter = request.args.get('status', 'submitted')
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')

    # Get all demands matching filter
    query = db.table('demands').select('id').eq('status', status_filter)
    if from_date:
        query = query.gte('demand_date', from_date)
    if to_date:
        query = query.lte('demand_date', to_date)
    
    demands_result = query.execute()
    demand_ids = [d['id'] for d in (demands_result.data or [])]

    if not demand_ids:
        return jsonify(serialize_response({'consolidated': [], 'total_demands': 0})), 200

    # Get all items from these demands
    items_result = db.table('demand_items').select(
        '*, items(name, category, unit, price), demands(mess_id, demand_date, mess(name))'
    ).in_('demand_id', demand_ids).execute()

    return jsonify(serialize_response({
        'consolidated': items_result.data or [],
        'total_demands': len(demand_ids)
    })), 200


# =====================================================
# DEMAND STATISTICS
# =====================================================

@demands_bp.route('/stats', methods=['GET'])
@jwt_required()
@role_required('admin', 'grain_shop_user')
def get_demand_stats():
    """Get demand statistics for dashboard"""
    db = get_db()

    stats = {}
    for status in ['draft', 'submitted', 'approved', 'rejected', 'forwarded_to_contractor', 'supplied_to_controller', 'distributed_to_messes']:
        result = db.table('demands').select('id', count='exact').eq('status', status).execute()
        stats[status] = result.count or 0

    stats['total'] = sum(stats.values())

    return jsonify(serialize_response(stats)), 200
