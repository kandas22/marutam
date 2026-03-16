"""
Supply Management Routes
Endpoints for tracking contractor supply to controller (Step 5)
and controller distribution to messes (Step 6)
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database import get_db
from utils import (
    admin_required, role_required, log_activity,
    serialize_response, paginate_query, get_current_user
)

supplies_bp = Blueprint('supplies', __name__)


# =====================================================
# STEP 5: CONTRACTOR SUPPLIES ITEMS TO CONTROLLER
# =====================================================

@supplies_bp.route('', methods=['POST'])
@jwt_required()
@role_required('grain_shop_user', 'admin')
def record_supply():
    """
    Record items supplied by contractor to controller
    ---
    Request Body:
        - contractor_id: UUID of the contractor (required)
        - demand_id: UUID of the demand being fulfilled (optional but recommended)
        - items: List of supplied items (required)
            - item_id: UUID of the item
            - supplied_quantity: Quantity supplied
            - unit_price: Price per unit (optional)
        - supply_date: Date of supply (optional, defaults to today)
        - invoice_number: Invoice reference (optional)
        - notes: Additional notes (optional)
    """
    user = get_current_user()
    data = request.get_json()

    if not data.get('contractor_id'):
        return jsonify({'error': 'contractor_id is required'}), 400
    if not data.get('items') or not isinstance(data['items'], list) or len(data['items']) == 0:
        return jsonify({'error': 'At least one item is required'}), 400

    db = get_db()

    # Verify contractor exists
    contractor = db.table('contractors').select('id').eq('id', data['contractor_id']).eq('is_active', True).single().execute()
    if not contractor.data:
        return jsonify({'error': 'Active contractor not found'}), 404

    # Record each supply item
    supplies_to_insert = []
    for item in data['items']:
        if not item.get('item_id') or not item.get('supplied_quantity'):
            continue
        supplies_to_insert.append({
            'contractor_id': data['contractor_id'],
            'demand_id': data.get('demand_id'),
            'item_id': item['item_id'],
            'supplied_quantity': float(item['supplied_quantity']),
            'unit_price': float(item['unit_price']) if item.get('unit_price') else None,
            'supply_date': data.get('supply_date'),
            'invoice_number': data.get('invoice_number'),
            'notes': data.get('notes'),
            'received_by': user['id']
        })

    if not supplies_to_insert:
        return jsonify({'error': 'No valid supply items provided'}), 400

    result = db.table('contractor_supplies').insert(supplies_to_insert).execute()

    # Also add items to grain_shop_inventory for stock tracking
    for item in supplies_to_insert:
        inventory_data = {
            'item_id': item['item_id'],
            'contractor_id': item['contractor_id'],
            'quantity': item['supplied_quantity'],
            'unit_price': item.get('unit_price'),
            'received_date': item.get('supply_date'),
            'recorded_by': user['id']
        }
        db.table('grain_shop_inventory').insert(inventory_data).execute()

    # Update demand status if linked to a demand
    if data.get('demand_id'):
        db.table('demands').update({
            'status': 'supplied_to_controller'
        }).eq('id', data['demand_id']).execute()

    log_activity(user['id'], 'CREATE', 'contractor_supplies', None, None, {
        'contractor_id': data['contractor_id'],
        'item_count': len(supplies_to_insert)
    })

    return jsonify(serialize_response(
        result.data if result.data else None,
        f'{len(supplies_to_insert)} supply items recorded successfully'
    )), 201


@supplies_bp.route('', methods=['GET'])
@jwt_required()
@role_required('admin', 'grain_shop_user')
def get_supplies():
    """
    Get supply records with filtering
    Query params:
        - contractor_id: Filter by contractor
        - demand_id: Filter by demand
        - from_date / to_date: Date range
        - item_id: Filter by item
    """
    db = get_db()

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    contractor_id = request.args.get('contractor_id')
    demand_id = request.args.get('demand_id')
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    item_id = request.args.get('item_id')

    query = db.table('contractor_supplies').select(
        '*, items(name, category, unit), contractors(name), users!received_by(full_name)'
    )

    if contractor_id:
        query = query.eq('contractor_id', contractor_id)
    if demand_id:
        query = query.eq('demand_id', demand_id)
    if from_date:
        query = query.gte('supply_date', from_date)
    if to_date:
        query = query.lte('supply_date', to_date)
    if item_id:
        query = query.eq('item_id', item_id)

    query = query.order('supply_date', desc=True)
    query = paginate_query(query, page, per_page)
    result = query.execute()

    return jsonify(serialize_response({
        'supplies': result.data or [],
        'page': page,
        'per_page': per_page
    })), 200


@supplies_bp.route('/<supply_id>', methods=['GET'])
@jwt_required()
@role_required('admin', 'grain_shop_user')
def get_supply(supply_id):
    """Get single supply record"""
    db = get_db()
    result = db.table('contractor_supplies').select(
        '*, items(name, category, unit), contractors(name), users!received_by(full_name)'
    ).eq('id', supply_id).single().execute()

    if not result.data:
        return jsonify({'error': 'Supply record not found'}), 404

    return jsonify(serialize_response(result.data)), 200


# =====================================================
# SUPPLY REPORTS
# =====================================================

@supplies_bp.route('/summary', methods=['GET'])
@jwt_required()
@role_required('admin', 'grain_shop_user')
def get_supply_summary():
    """
    Get supply summary (supply vs demand comparison)
    """
    db = get_db()
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')

    query = db.table('contractor_supply_summary').select('*')
    if from_date:
        query = query.gte('supply_date', from_date)
    if to_date:
        query = query.lte('supply_date', to_date)

    result = query.execute()

    return jsonify(serialize_response(result.data or [])), 200


@supplies_bp.route('/pending', methods=['GET'])
@jwt_required()
@role_required('admin', 'grain_shop_user')
def get_pending_supplies():
    """Get approved demands that haven't been supplied yet"""
    db = get_db()

    result = db.table('demands').select(
        '*, mess(name), demand_items(*, items(name, category, unit))'
    ).in_('status', ['approved', 'forwarded_to_contractor']).order('demand_date', desc=True).execute()

    return jsonify(serialize_response(result.data or [])), 200


@supplies_bp.route('/financial', methods=['GET'])
@jwt_required()
@admin_required
def get_financial_summary():
    """
    Get financial summary report (Admin only)
    Monthly expenditure by category
    """
    db = get_db()
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')

    query = db.table('financial_summary').select('*')
    if from_date:
        query = query.gte('month', from_date)
    if to_date:
        query = query.lte('month', to_date)

    result = query.execute()

    return jsonify(serialize_response(result.data or [])), 200


@supplies_bp.route('/contractor-performance', methods=['GET'])
@jwt_required()
@admin_required
def get_contractor_performance():
    """
    Get contractor performance report (Admin only)
    - Supply timeliness
    - Total quantities and costs
    """
    db = get_db()
    contractor_id = request.args.get('contractor_id')

    query = db.table('contractor_supplies').select(
        'contractor_id, contractors(name), supply_date, supplied_quantity, unit_price, items(name, category)'
    )

    if contractor_id:
        query = query.eq('contractor_id', contractor_id)

    result = query.order('supply_date', desc=True).execute()

    # Aggregate by contractor
    contractors = {}
    for supply in (result.data or []):
        c_id = supply.get('contractor_id')
        if c_id not in contractors:
            contractors[c_id] = {
                'contractor_id': c_id,
                'contractor_name': supply.get('contractors', {}).get('name', 'Unknown'),
                'total_supplies': 0,
                'total_quantity': 0,
                'total_cost': 0,
                'supply_dates': []
            }
        contractors[c_id]['total_supplies'] += 1
        contractors[c_id]['total_quantity'] += float(supply.get('supplied_quantity', 0))
        unit_price = float(supply.get('unit_price', 0)) if supply.get('unit_price') else 0
        contractors[c_id]['total_cost'] += float(supply.get('supplied_quantity', 0)) * unit_price
        if supply.get('supply_date'):
            contractors[c_id]['supply_dates'].append(supply['supply_date'])

    return jsonify(serialize_response(list(contractors.values()))), 200
