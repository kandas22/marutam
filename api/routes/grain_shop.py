"""
Grain Shop Management Routes
Endpoints for managing grain shop inventory from contractors
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database import get_db
from utils import admin_required, role_required, log_activity, serialize_response, paginate_query, get_current_user

grain_shop_bp = Blueprint('grain_shop', __name__)


@grain_shop_bp.route('/inventory', methods=['GET'])
@jwt_required()
@role_required('admin', 'grain_shop_user')
def get_inventory():
    """
    Get grain shop inventory
    Query params:
        - contractor_id: Filter by contractor
        - item_id: Filter by item
        - category: Filter by item category
        - from_date: Start date filter
        - to_date: End date filter
    """
    db = get_db()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    contractor_id = request.args.get('contractor_id')
    item_id = request.args.get('item_id')
    category = request.args.get('category')
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    
    query = db.table('grain_shop_inventory').select(
        '*, items(name, category, unit), contractors(name, contact_person), users!recorded_by(full_name)'
    )
    
    if contractor_id:
        query = query.eq('contractor_id', contractor_id)
    if item_id:
        query = query.eq('item_id', item_id)
    if from_date:
        query = query.gte('received_date', from_date)
    if to_date:
        query = query.lte('received_date', to_date)
    
    query = query.order('received_date', desc=True)
    query = paginate_query(query, page, per_page)
    
    result = query.execute()
    
    # Filter by category if specified (post-query filter due to join)
    inventory_data = result.data
    if category and inventory_data:
        inventory_data = [inv for inv in inventory_data if inv.get('items', {}).get('category') == category]
    
    return jsonify(serialize_response({
        'inventory': inventory_data,
        'page': page,
        'per_page': per_page
    })), 200


@grain_shop_bp.route('/inventory/<inventory_id>', methods=['GET'])
@jwt_required()
@role_required('admin', 'grain_shop_user')
def get_inventory_item(inventory_id):
    """Get single inventory record details"""
    db = get_db()
    
    result = db.table('grain_shop_inventory').select(
        '*, items(name, category, unit), contractors(name, contact_person, phone, email)'
    ).eq('id', inventory_id).single().execute()
    
    if not result.data:
        return jsonify({'error': 'Inventory record not found'}), 404
    
    return jsonify(serialize_response(result.data)), 200


@grain_shop_bp.route('/inventory', methods=['POST'])
@jwt_required()
@role_required('admin', 'grain_shop_user')
def add_inventory():
    """
    Add inventory from contractor
    ---
    Request Body:
        - item_id: Item ID (required)
        - contractor_id: Contractor ID (required)
        - quantity: Quantity received (required)
        - unit_price: Unit price (optional)
        - batch_number: Batch number (optional)
        - received_date: Date received (optional, defaults to today)
        - expiry_date: Expiry date (optional)
    """
    user = get_current_user()
    data = request.get_json()
    
    required_fields = ['item_id', 'contractor_id', 'quantity']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400
    
    db = get_db()
    
    # Verify item exists
    item = db.table('items').select('id').eq('id', data['item_id']).single().execute()
    if not item.data:
        return jsonify({'error': 'Item not found'}), 404
    
    # Verify contractor exists
    contractor = db.table('contractors').select('id').eq('id', data['contractor_id']).single().execute()
    if not contractor.data:
        return jsonify({'error': 'Contractor not found'}), 404
    
    inventory_data = {
        'item_id': data['item_id'],
        'contractor_id': data['contractor_id'],
        'quantity': float(data['quantity']),
        'unit_price': float(data['unit_price']) if data.get('unit_price') else None,
        'batch_number': data.get('batch_number'),
        'received_date': data.get('received_date'),
        'expiry_date': data.get('expiry_date'),
        'recorded_by': user['id']
    }
    
    result = db.table('grain_shop_inventory').insert(inventory_data).execute()
    
    if result.data:
        log_activity(user['id'], 'CREATE', 'grain_shop_inventory', result.data[0]['id'], None, inventory_data)
        return jsonify(serialize_response(result.data[0], 'Inventory added successfully')), 201
    
    return jsonify({'error': 'Failed to add inventory'}), 500


@grain_shop_bp.route('/inventory/<inventory_id>', methods=['PUT'])
@jwt_required()
@role_required('admin', 'grain_shop_user')
def update_inventory(inventory_id):
    """Update inventory record"""
    user = get_current_user()
    data = request.get_json()
    
    db = get_db()
    
    existing = db.table('grain_shop_inventory').select('*').eq('id', inventory_id).single().execute()
    if not existing.data:
        return jsonify({'error': 'Inventory record not found'}), 404
    
    update_data = {}
    allowed_fields = ['quantity', 'unit_price', 'batch_number', 'received_date', 'expiry_date']
    
    for field in allowed_fields:
        if field in data:
            if field in ['quantity', 'unit_price'] and data[field] is not None:
                update_data[field] = float(data[field])
            else:
                update_data[field] = data[field]
    
    if not update_data:
        return jsonify({'error': 'No valid fields to update'}), 400
    
    result = db.table('grain_shop_inventory').update(update_data).eq('id', inventory_id).execute()
    
    if result.data:
        log_activity(user['id'], 'UPDATE', 'grain_shop_inventory', inventory_id, existing.data, update_data)
        return jsonify(serialize_response(result.data[0], 'Inventory updated successfully')), 200
    
    return jsonify({'error': 'Failed to update inventory'}), 500


@grain_shop_bp.route('/inventory/<inventory_id>', methods=['DELETE'])
@jwt_required()
@admin_required
def delete_inventory(inventory_id):
    """Delete inventory record (Admin only)"""
    admin_id = get_jwt_identity()
    
    db = get_db()
    
    existing = db.table('grain_shop_inventory').select('*').eq('id', inventory_id).single().execute()
    if not existing.data:
        return jsonify({'error': 'Inventory record not found'}), 404
    
    db.table('grain_shop_inventory').delete().eq('id', inventory_id).execute()
    
    log_activity(admin_id, 'DELETE', 'grain_shop_inventory', inventory_id, existing.data, None)
    
    return jsonify(serialize_response(None, 'Inventory record deleted successfully')), 200


@grain_shop_bp.route('/summary', methods=['GET'])
@jwt_required()
@role_required('admin', 'grain_shop_user')
def get_inventory_summary():
    """
    Get inventory summary grouped by item and category
    """
    db = get_db()
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    
    # Get summary view
    query = db.table('grain_shop_daily_summary').select('*')
    
    if from_date:
        query = query.gte('received_date', from_date)
    if to_date:
        query = query.lte('received_date', to_date)
    
    result = query.order('received_date', desc=True).execute()
    
    return jsonify(serialize_response(result.data)), 200


@grain_shop_bp.route('/stock-levels', methods=['GET'])
@jwt_required()
@role_required('admin', 'grain_shop_user')
def get_stock_levels():
    """
    Get current stock levels for all items
    Calculates total received vs distributed
    """
    db = get_db()
    
    # Get all items
    items = db.table('items').select('id, name, category, unit, minimum_stock').eq('is_active', True).execute()
    
    # Batch fetch ALL inventory and distribution records (instead of per-item queries)
    all_received = db.table('grain_shop_inventory').select('item_id, quantity').execute()
    all_distributed = db.table('distribution_log').select('item_id, quantity').execute()
    
    # Aggregate by item_id in Python
    received_map = {}
    for r in (all_received.data or []):
        item_id = r['item_id']
        received_map[item_id] = received_map.get(item_id, 0) + float(r['quantity'])
    
    distributed_map = {}
    for d in (all_distributed.data or []):
        item_id = d['item_id']
        distributed_map[item_id] = distributed_map.get(item_id, 0) + float(d['quantity'])
    
    stock_data = []
    
    for item in items.data:
        total_received = received_map.get(item['id'], 0)
        total_distributed = distributed_map.get(item['id'], 0)
        current_stock = total_received - total_distributed
        
        stock_data.append({
            'item_id': item['id'],
            'item_name': item['name'],
            'category': item['category'],
            'unit': item['unit'],
            'total_received': total_received,
            'total_distributed': total_distributed,
            'current_stock': current_stock,
            'minimum_stock': item['minimum_stock'],
            'is_low_stock': current_stock < item['minimum_stock']
        })
    
    return jsonify(serialize_response(stock_data)), 200
