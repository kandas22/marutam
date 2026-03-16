"""
Distribution Management Routes
Endpoints for managing distribution from grain shop to mess
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database import get_db
from utils import admin_required, role_required, log_activity, serialize_response, paginate_query, get_current_user

distribution_bp = Blueprint('distribution', __name__)


@distribution_bp.route('', methods=['GET'])
@jwt_required()
@role_required('admin', 'grain_shop_user', 'mess_user')
def get_distributions():
    """
    Get distribution records
    Admin sees all, grain shop sees all distributions, mess sees only their distributions
    """
    user = get_current_user()
    db = get_db()
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    mess_id = request.args.get('mess_id')
    item_id = request.args.get('item_id')
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    
    try:
        # Simplified select to avoid ambiguous foreign key issues
        query = db.table('distribution_log').select(
            '*, items(name, category, unit), mess(name, location)'
        )
        
        # Filter by mess for mess users
        if user['role'] == 'mess_user':
            # Get mess managed by this user
            mess = db.table('mess').select('id').eq('manager_id', user['id']).execute()
            if mess.data:
                mess_ids = [m['id'] for m in mess.data]
                query = query.in_('mess_id', mess_ids)
            else:
                return jsonify(serialize_response({'distributions': [], 'page': page, 'per_page': per_page})), 200
        
        if mess_id:
            query = query.eq('mess_id', mess_id)
        if item_id:
            query = query.eq('item_id', item_id)
        if from_date:
            query = query.gte('distribution_date', from_date)
        if to_date:
            query = query.lte('distribution_date', to_date)
        
        query = query.order('distribution_date', desc=True)
        query = paginate_query(query, page, per_page)
        
        result = query.execute()
        
        # Enrich with user names for distributed_by and received_by
        distributions = result.data or []
        user_ids = set()
        for dist in distributions:
            if dist.get('distributed_by'):
                user_ids.add(dist['distributed_by'])
            if dist.get('received_by'):
                user_ids.add(dist['received_by'])
        
        # Fetch user names in one query
        user_map = {}
        if user_ids:
            users_result = db.table('users').select('id, full_name, username').in_('id', list(user_ids)).execute()
            if users_result.data:
                for u in users_result.data:
                    user_map[u['id']] = u
        
        # Attach user info to distributions
        for dist in distributions:
            dist['distributed_by_user'] = user_map.get(dist.get('distributed_by'))
            dist['received_by_user'] = user_map.get(dist.get('received_by'))
        
        return jsonify(serialize_response({
            'distributions': distributions,
            'page': page,
            'per_page': per_page
        })), 200
    except Exception as e:
        print(f"Distribution GET error: {e}")
        return jsonify({'error': f'Failed to fetch distributions: {str(e)}'}), 500


@distribution_bp.route('/<distribution_id>', methods=['GET'])
@jwt_required()
@role_required('admin', 'grain_shop_user', 'mess_user')
def get_distribution(distribution_id):
    """Get single distribution record details"""
    user = get_current_user()
    db = get_db()
    
    try:
        result = db.table('distribution_log').select(
            '*, items(name, category, unit), mess(name, location, manager_id)'
        ).eq('id', distribution_id).single().execute()
        
        if not result.data:
            return jsonify({'error': 'Distribution record not found'}), 404
        
        # Verify access for mess users
        if user['role'] == 'mess_user':
            mess_data = result.data.get('mess')
            mess_manager = mess_data.get('manager_id') if mess_data else None
            if mess_manager != user['id']:
                return jsonify({'error': 'Access denied'}), 403
        
        return jsonify(serialize_response(result.data)), 200
    except Exception as e:
        print(f"Distribution GET detail error: {e}")
        return jsonify({'error': f'Failed to fetch distribution: {str(e)}'}), 500


@distribution_bp.route('/bulk', methods=['POST'])
@jwt_required()
@role_required('admin', 'grain_shop_user')
def create_bulk_distribution():
    """
    Create multiple distribution records at once (from grain shop to mess).
    Accepts a list of items with quantities for a single mess and date.
    ---
    Request Body:
        - mess_id: Mess ID (required)
        - distribution_date: Date of distribution (optional, defaults to today)
        - notes: Additional notes (optional)
        - items: List of {item_id, quantity} (required, at least one item)
    """
    user = get_current_user()
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    mess_id = data.get('mess_id')
    items_list = data.get('items', [])
    distribution_date = data.get('distribution_date')
    notes = data.get('notes')

    if not mess_id:
        return jsonify({'error': 'mess_id is required'}), 400

    if not items_list or not isinstance(items_list, list):
        return jsonify({'error': 'items must be a non-empty list of {item_id, quantity}'}), 400

    db = get_db()

    try:
        # Verify mess exists
        mess = db.table('mess').select('id, name').eq('id', mess_id).single().execute()
        if not mess.data:
            return jsonify({'error': 'Mess not found'}), 404

        created = []
        errors = []

        for entry in items_list:
            item_id = entry.get('item_id')
            quantity = entry.get('quantity')

            if not item_id or not quantity or float(quantity) <= 0:
                errors.append(f"Skipped invalid entry: item_id={item_id}, quantity={quantity}")
                continue

            # Verify item exists
            item = db.table('items').select('id, name').eq('id', item_id).single().execute()
            if not item.data:
                errors.append(f"Item not found: {item_id}")
                continue

            distribution_data = {
                'mess_id': mess_id,
                'item_id': item_id,
                'quantity': float(quantity),
                'distribution_date': distribution_date,
                'distributed_by': user['id'],
                'notes': notes
            }

            result = db.table('distribution_log').insert(distribution_data).execute()

            if result.data:
                # Also add to mess inventory
                mess_inventory_data = {
                    'mess_id': mess_id,
                    'item_id': item_id,
                    'quantity': float(quantity),
                    'date': distribution_date,
                    'recorded_by': user['id']
                }
                db.table('mess_inventory').insert(mess_inventory_data).execute()

                created.append(result.data[0])
                log_activity(user['id'], 'CREATE', 'distribution_log', result.data[0]['id'], None, distribution_data)

        if not created:
            return jsonify({'error': 'No distributions were created. ' + '; '.join(errors)}), 400

        return jsonify(serialize_response({
            'count': len(created),
            'distributions': created,
            'errors': errors if errors else None
        }, f'{len(created)} distribution(s) recorded successfully')), 201

    except Exception as e:
        print(f"Bulk distribution POST error: {e}")
        return jsonify({'error': f'Failed to create bulk distribution: {str(e)}'}), 500


@distribution_bp.route('', methods=['POST'])
@jwt_required()
@role_required('admin', 'grain_shop_user')
def create_distribution():
    """
    Create distribution record (from grain shop to mess)
    Admin and Grain Shop Users can create distributions
    ---
    Request Body:
        - mess_id: Mess ID (required)
        - item_id: Item ID (required)
        - quantity: Quantity distributed (required)
        - distribution_date: Date of distribution (optional, defaults to today)
        - grain_shop_inventory_id: Source inventory ID (optional)
        - notes: Additional notes (optional)
    """
    user = get_current_user()
    data = request.get_json()
    
    required_fields = ['mess_id', 'item_id', 'quantity']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400
    
    db = get_db()
    
    try:
        # Verify mess exists
        mess = db.table('mess').select('id, name').eq('id', data['mess_id']).single().execute()
        if not mess.data:
            return jsonify({'error': 'Mess not found'}), 404
        
        # Verify item exists
        item = db.table('items').select('id, name').eq('id', data['item_id']).single().execute()
        if not item.data:
            return jsonify({'error': 'Item not found'}), 404
        
        distribution_data = {
            'mess_id': data['mess_id'],
            'item_id': data['item_id'],
            'quantity': float(data['quantity']),
            'distribution_date': data.get('distribution_date'),
            'grain_shop_inventory_id': data.get('grain_shop_inventory_id'),
            'distributed_by': user['id'],
            'notes': data.get('notes')
        }
        
        result = db.table('distribution_log').insert(distribution_data).execute()
        
        if result.data:
            # Also add to mess inventory
            mess_inventory_data = {
                'mess_id': data['mess_id'],
                'item_id': data['item_id'],
                'quantity': float(data['quantity']),
                'date': data.get('distribution_date'),
                'recorded_by': user['id']
            }
            db.table('mess_inventory').insert(mess_inventory_data).execute()
            
            log_activity(user['id'], 'CREATE', 'distribution_log', result.data[0]['id'], None, distribution_data)
            return jsonify(serialize_response(result.data[0], 'Distribution recorded successfully')), 201
        
        return jsonify({'error': 'Failed to create distribution'}), 500
    except Exception as e:
        print(f"Distribution POST error: {e}")
        return jsonify({'error': f'Failed to create distribution: {str(e)}'}), 500


@distribution_bp.route('/<distribution_id>', methods=['PUT'])
@jwt_required()
@role_required('admin', 'grain_shop_user')
def update_distribution(distribution_id):
    """Update distribution record (Admin and Grain Shop Users)"""
    user = get_current_user()
    data = request.get_json()
    
    db = get_db()
    
    existing = db.table('distribution_log').select('*').eq('id', distribution_id).single().execute()
    if not existing.data:
        return jsonify({'error': 'Distribution record not found'}), 404
    
    update_data = {}
    allowed_fields = ['quantity', 'distribution_date', 'notes']
    
    for field in allowed_fields:
        if field in data:
            if field == 'quantity' and data[field] is not None:
                update_data[field] = float(data[field])
            else:
                update_data[field] = data[field]
    
    if not update_data:
        return jsonify({'error': 'No valid fields to update'}), 400
    
    result = db.table('distribution_log').update(update_data).eq('id', distribution_id).execute()
    
    if result.data:
        log_activity(user['id'], 'UPDATE', 'distribution_log', distribution_id, existing.data, update_data)
        return jsonify(serialize_response(result.data[0], 'Distribution updated successfully')), 200
    
    return jsonify({'error': 'Failed to update distribution'}), 500


@distribution_bp.route('/<distribution_id>', methods=['DELETE'])
@jwt_required()
@admin_required
def delete_distribution(distribution_id):
    """Delete distribution record (Admin only)"""
    admin_id = get_jwt_identity()
    
    db = get_db()
    
    existing = db.table('distribution_log').select('*').eq('id', distribution_id).single().execute()
    if not existing.data:
        return jsonify({'error': 'Distribution record not found'}), 404
    
    db.table('distribution_log').delete().eq('id', distribution_id).execute()
    
    log_activity(admin_id, 'DELETE', 'distribution_log', distribution_id, existing.data, None)
    
    return jsonify(serialize_response(None, 'Distribution record deleted successfully')), 200


@distribution_bp.route('/confirm-receipt/<distribution_id>', methods=['POST'])
@jwt_required()
@role_required('admin', 'mess_user')
def confirm_receipt(distribution_id):
    """
    Confirm receipt of distribution at mess
    Updates the received_by field
    """
    user = get_current_user()
    db = get_db()
    
    try:
        # Get distribution with mess info
        distribution = db.table('distribution_log').select(
            '*, mess(manager_id)'
        ).eq('id', distribution_id).single().execute()
        
        if not distribution.data:
            return jsonify({'error': 'Distribution record not found'}), 404
        
        # Verify access for mess users
        if user['role'] == 'mess_user':
            mess_data = distribution.data.get('mess')
            mess_manager = mess_data.get('manager_id') if mess_data and isinstance(mess_data, dict) else None
            if mess_manager != user['id']:
                return jsonify({'error': 'Access denied'}), 403
        
        # Update received_by
        result = db.table('distribution_log').update({
            'received_by': user['id']
        }).eq('id', distribution_id).execute()
        
        if result.data:
            log_activity(user['id'], 'CONFIRM_RECEIPT', 'distribution_log', distribution_id)
            return jsonify(serialize_response(result.data[0], 'Receipt confirmed successfully')), 200
        
        return jsonify({'error': 'Failed to confirm receipt'}), 500
    except Exception as e:
        print(f"Confirm receipt error: {e}")
        return jsonify({'error': f'Failed to confirm receipt: {str(e)}'}), 500
