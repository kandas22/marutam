"""
Items Management Routes
Endpoints for managing ration items (veg/non-veg/grain_shop)
Per spec:
  - Controller (grain_shop_user) can add/edit/deactivate items
  - Controller proposes price/unit changes → Admin approves
  - Mess members see items WITHOUT price
  - Admin and Controller can see prices
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database import get_db
from utils import admin_required, role_required, log_activity, serialize_response, paginate_query, get_current_user

items_bp = Blueprint('items', __name__)


@items_bp.route('', methods=['GET'])
@jwt_required()
def get_items():
    """
    Get all ration items
    All authenticated users can view items
    - Admin & Controller: see price details
    - Mess members & Contractor: NO price details
    Query params:
        - category: Filter by category (veg, non_veg, grain_shop)
        - search: Search by name
        - active_only: Show only active items (default: true)
    """
    user = get_current_user()
    db = get_db()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    category = request.args.get('category')
    search = request.args.get('search')
    active_only = request.args.get('active_only', 'true').lower() == 'true'

    query = db.table('items').select('*')

    if active_only:
        query = query.eq('is_active', True)

    if category:
        query = query.eq('category', category)

    if search:
        query = query.ilike('name', f'%{search}%')

    query = query.order('category').order('name')
    query = paginate_query(query, page, per_page)

    result = query.execute()

    items_data = result.data or []

    # Strip price info for non-admin, non-controller users
    user_role = user.get('role', '') if user else ''
    if user_role not in ('admin', 'grain_shop_user'):
        for item in items_data:
            item.pop('price', None)

    return jsonify(serialize_response({
        'items': items_data,
        'page': page,
        'per_page': per_page
    })), 200


@items_bp.route('/categories', methods=['GET'])
@jwt_required()
def get_categories():
    """Get list of ration categories"""
    categories = [
        {'value': 'veg', 'label': 'Vegetarian'},
        {'value': 'non_veg', 'label': 'Non-Vegetarian'},
        {'value': 'grain_shop', 'label': 'Grain Shop'}
    ]
    return jsonify(serialize_response(categories)), 200


@items_bp.route('/<item_id>', methods=['GET'])
@jwt_required()
def get_item(item_id):
    """Get single item details"""
    user = get_current_user()
    db = get_db()

    result = db.table('items').select('*').eq('id', item_id).single().execute()

    if not result.data:
        return jsonify({'error': 'Item not found'}), 404

    item_data = result.data

    # Strip price for non-admin, non-controller users
    user_role = user.get('role', '') if user else ''
    if user_role not in ('admin', 'grain_shop_user'):
        item_data.pop('price', None)

    return jsonify(serialize_response(item_data)), 200


@items_bp.route('', methods=['POST'])
@jwt_required()
@role_required('admin', 'grain_shop_user')
def create_item():
    """
    Create new ration item (Controller or Admin)
    ---
    Request Body:
        - name: Item name (required)
        - category: Category - veg, non_veg, grain_shop (required)
        - unit: Unit of measurement - kg, liters, pieces (required)
        - description: Description (optional)
        - minimum_stock: Minimum stock level (optional)
        - price: Item price (optional, Admin/Controller only)
    """
    user = get_current_user()
    user_id = user['id']
    data = request.get_json()

    # Validate required fields
    required_fields = ['name', 'category', 'unit']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400

    # Validate category
    valid_categories = ['veg', 'non_veg', 'grain_shop', 'grocery']
    if data['category'] not in valid_categories:
        return jsonify({'error': f'Category must be one of: {", ".join(valid_categories)}'}), 400

    db = get_db()

    item_data = {
        'name': data['name'],
        'category': data['category'],
        'unit': data['unit'],
        'description': data.get('description'),
        'minimum_stock': data.get('minimum_stock', 0),
        'price': data.get('price'),
        'created_by': user_id,
        'is_active': True
    }

    result = db.table('items').insert(item_data).execute()

    if result.data:
        log_activity(user_id, 'CREATE', 'items', result.data[0]['id'], None, item_data)
        return jsonify(serialize_response(result.data[0], 'Item created successfully')), 201

    return jsonify({'error': 'Failed to create item'}), 500


@items_bp.route('/<item_id>', methods=['PUT'])
@jwt_required()
@role_required('admin', 'grain_shop_user')
def update_item(item_id):
    """
    Update item details (Controller or Admin)
    Note: Price and unit changes by Controller create a pending approval.
          Admin can update directly.
    """
    user = get_current_user()
    user_id = user['id']
    user_role = user.get('role', '')
    data = request.get_json()

    db = get_db()

    # Get existing item
    existing = db.table('items').select('*').eq('id', item_id).single().execute()
    if not existing.data:
        return jsonify({'error': 'Item not found'}), 404

    # Prepare update data
    update_data = {}
    pending_changes = []
    allowed_fields = ['name', 'category', 'description', 'minimum_stock', 'is_active']
    
    # Fields that require admin approval if changed by controller
    approval_fields = ['price', 'unit']

    for field in allowed_fields:
        if field in data:
            update_data[field] = data[field]

    # Handle price/unit changes
    for field in approval_fields:
        if field in data:
            if user_role == 'admin':
                # Admin can change directly
                update_data[field] = data[field]
            else:
                # Controller — create pending approval
                if str(data[field]) != str(existing.data.get(field, '')):
                    pending_changes.append({
                        'item_id': item_id,
                        'change_type': field,
                        'old_value': str(existing.data.get(field, '')),
                        'new_value': str(data[field]),
                        'proposed_by': user_id,
                        'approval_status': 'pending'
                    })

    # Validate category if provided
    if 'category' in update_data:
        valid_categories = ['veg', 'non_veg', 'grain_shop', 'grocery']
        if update_data['category'] not in valid_categories:
            return jsonify({'error': f'Category must be one of: {", ".join(valid_categories)}'}), 400

    messages = []

    # Apply direct updates
    if update_data:
        result = db.table('items').update(update_data).eq('id', item_id).execute()
        if result.data:
            log_activity(user_id, 'UPDATE', 'items', item_id, existing.data, update_data)
            messages.append('Item updated successfully')

    # Create pending changes
    if pending_changes:
        for change in pending_changes:
            db.table('price_change_history').insert(change).execute()
        log_activity(user_id, 'PROPOSE_CHANGE', 'items', item_id, None, {'pending_changes': len(pending_changes)})
        messages.append(f'{len(pending_changes)} change(s) submitted for Admin approval')

    if not update_data and not pending_changes:
        return jsonify({'error': 'No valid fields to update'}), 400

    # Get updated item
    updated = db.table('items').select('*').eq('id', item_id).single().execute()

    return jsonify(serialize_response(
        updated.data if updated.data else None,
        ' | '.join(messages) if messages else 'No changes applied'
    )), 200


@items_bp.route('/<item_id>', methods=['DELETE'])
@jwt_required()
@role_required('admin', 'grain_shop_user')
def delete_item(item_id):
    """Delete/Deactivate item (Controller or Admin)"""
    user = get_current_user()
    user_id = user['id']

    db = get_db()

    existing = db.table('items').select('*').eq('id', item_id).single().execute()
    if not existing.data:
        return jsonify({'error': 'Item not found'}), 404

    # Soft delete
    db.table('items').update({'is_active': False}).eq('id', item_id).execute()

    log_activity(user_id, 'DELETE', 'items', item_id, existing.data, None)

    return jsonify(serialize_response(None, 'Item deactivated successfully')), 200


@items_bp.route('/by-category/<category>', methods=['GET'])
@jwt_required()
def get_items_by_category(category):
    """Get items filtered by category"""
    valid_categories = ['veg', 'non_veg', 'grain_shop', 'grocery']
    if category not in valid_categories:
        return jsonify({'error': f'Invalid category. Must be one of: {", ".join(valid_categories)}'}), 400

    user = get_current_user()
    db = get_db()

    result = db.table('items').select('*').eq('category', category).eq('is_active', True).order('name').execute()

    items_data = result.data or []

    # Strip price for non-admin, non-controller users
    user_role = user.get('role', '') if user else ''
    if user_role not in ('admin', 'grain_shop_user'):
        for item in items_data:
            item.pop('price', None)

    return jsonify(serialize_response(items_data)), 200
