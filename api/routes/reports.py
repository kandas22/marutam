"""
Reports and Analytics Routes
Comprehensive report endpoints per spec:
  - Demand Reports
  - Supply Reports
  - Inventory Reports
  - User Reports
  - Contractor Reports
  - Daily Mess Entry Reports
  - Financial Reports
  - Activity Log / Audit Trail
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from datetime import datetime, timedelta
from database import get_db
from utils import admin_required, role_required, serialize_response, paginate_query

reports_bp = Blueprint('reports', __name__)


# =====================================================
# DASHBOARD STATS
# =====================================================

@reports_bp.route('/dashboard', methods=['GET'])
@jwt_required()
@admin_required
def get_dashboard_stats():
    """Get dashboard statistics for admin"""
    db = get_db()
    today = datetime.now().strftime('%Y-%m-%d')

    # Get counts
    users_count = db.table('users').select('id', count='exact').eq('is_active', True).execute()
    contractors_count = db.table('contractors').select('id', count='exact').eq('is_active', True).execute()
    mess_count = db.table('mess').select('id', count='exact').eq('is_active', True).execute()
    items_count = db.table('items').select('id', count='exact').eq('is_active', True).execute()
    pending_approvals = db.table('pending_updates').select('id', count='exact').eq('approval_status', 'pending').execute()
    pending_usage = db.table('daily_ration_usage').select('id', count='exact').eq('approval_status', 'pending').execute()

    # Demand stats
    pending_demands = db.table('demands').select('id', count='exact').eq('status', 'submitted').execute()

    # Price change requests
    pending_price_changes = db.table('price_change_history').select('id', count='exact').eq('approval_status', 'pending').execute()

    # Today's activity
    today_activity = db.table('activity_log').select('id', count='exact').gte('created_at', today).execute()

    # Today's distributions
    today_distributions = db.table('distribution_log').select('id', count='exact').eq('distribution_date', today).execute()

    stats = {
        'total_users': users_count.count or 0,
        'total_contractors': contractors_count.count or 0,
        'total_mess_units': mess_count.count or 0,
        'total_items': items_count.count or 0,
        'pending_approvals': (pending_approvals.count or 0) + (pending_usage.count or 0),
        'pending_demands': pending_demands.count or 0,
        'pending_price_changes': pending_price_changes.count or 0,
        'today_activity_count': today_activity.count or 0,
        'today_distributions': today_distributions.count or 0
    }

    return jsonify(serialize_response(stats)), 200


# =====================================================
# 1. DEMAND REPORTS
# =====================================================

@reports_bp.route('/demands', methods=['GET'])
@jwt_required()
@role_required('admin', 'grain_shop_user')
def get_demand_reports():
    """
    Demand reports with filtering
    Query params: status, mess_id, category, from_date, to_date
    """
    db = get_db()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    status = request.args.get('status')
    mess_id = request.args.get('mess_id')
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')

    query = db.table('demands').select(
        '*, mess(name), users!submitted_by(full_name), contractors(name), demand_items(*, items(name, category, unit))'
    )

    if status:
        query = query.eq('status', status)
    if mess_id:
        query = query.eq('mess_id', mess_id)
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


# =====================================================
# 2. SUPPLY REPORTS
# =====================================================

@reports_bp.route('/supply/history', methods=['GET'])
@jwt_required()
@admin_required
def get_supply_history():
    """Contractor supply history"""
    db = get_db()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    contractor_id = request.args.get('contractor_id')
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')

    query = db.table('contractor_supplies').select(
        '*, items(name, category, unit), contractors(name), users!received_by(full_name)'
    )

    if contractor_id:
        query = query.eq('contractor_id', contractor_id)
    if from_date:
        query = query.gte('supply_date', from_date)
    if to_date:
        query = query.lte('supply_date', to_date)

    query = query.order('supply_date', desc=True)
    query = paginate_query(query, page, per_page)
    result = query.execute()

    return jsonify(serialize_response({
        'history': result.data or [],
        'page': page,
        'per_page': per_page
    })), 200


@reports_bp.route('/supply/vs-demand', methods=['GET'])
@jwt_required()
@admin_required
def get_supply_vs_demand():
    """Compare demanded vs supplied quantities"""
    db = get_db()
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')

    # Get approved demands
    demand_query = db.table('demand_items').select(
        'item_id, items(name, category, unit), requested_quantity, approved_quantity, demands!inner(status, demand_date)'
    ).in_('demands.status', ['approved', 'forwarded_to_contractor', 'supplied_to_controller', 'distributed_to_messes'])

    if from_date:
        demand_query = demand_query.gte('demands.demand_date', from_date)
    if to_date:
        demand_query = demand_query.lte('demands.demand_date', to_date)

    demands_result = demand_query.execute()

    # Get supplies
    supply_query = db.table('contractor_supplies').select(
        'item_id, items(name, category, unit), supplied_quantity, supply_date'
    )
    if from_date:
        supply_query = supply_query.gte('supply_date', from_date)
    if to_date:
        supply_query = supply_query.lte('supply_date', to_date)

    supplies_result = supply_query.execute()

    # Aggregate by item
    item_comparison = {}

    for d in (demands_result.data or []):
        item_id = d['item_id']
        if item_id not in item_comparison:
            item_info = d.get('items', {})
            item_comparison[item_id] = {
                'item_name': item_info.get('name', 'Unknown'),
                'category': item_info.get('category', ''),
                'unit': item_info.get('unit', ''),
                'total_demanded': 0,
                'total_approved': 0,
                'total_supplied': 0
            }
        item_comparison[item_id]['total_demanded'] += float(d.get('requested_quantity', 0))
        item_comparison[item_id]['total_approved'] += float(d.get('approved_quantity', 0) or 0)

    for s in (supplies_result.data or []):
        item_id = s['item_id']
        if item_id not in item_comparison:
            item_info = s.get('items', {})
            item_comparison[item_id] = {
                'item_name': item_info.get('name', 'Unknown'),
                'category': item_info.get('category', ''),
                'unit': item_info.get('unit', ''),
                'total_demanded': 0,
                'total_approved': 0,
                'total_supplied': 0
            }
        item_comparison[item_id]['total_supplied'] += float(s.get('supplied_quantity', 0))

    return jsonify(serialize_response(list(item_comparison.values()))), 200


# =====================================================
# 3. INVENTORY REPORTS
# =====================================================

@reports_bp.route('/inventory/current', methods=['GET'])
@jwt_required()
@role_required('admin', 'grain_shop_user')
def get_current_inventory():
    """Real-time stock levels across all items"""
    db = get_db()

    items = db.table('items').select('*').eq('is_active', True).order('category').order('name').execute()

    inventory_data = []
    for item in (items.data or []):
        # Get total received
        received = db.table('grain_shop_inventory').select('quantity').eq('item_id', item['id']).execute()
        total_received = sum(float(r['quantity']) for r in (received.data or []))

        # Get total distributed
        distributed = db.table('distribution_log').select('quantity').eq('item_id', item['id']).execute()
        total_distributed = sum(float(d['quantity']) for d in (distributed.data or []))

        current_stock = total_received - total_distributed

        inventory_data.append({
            'item_id': item['id'],
            'item_name': item['name'],
            'category': item['category'],
            'unit': item['unit'],
            'price': item.get('price'),
            'minimum_stock': item.get('minimum_stock', 0),
            'total_received': total_received,
            'total_distributed': total_distributed,
            'current_stock': current_stock,
            'is_low_stock': current_stock < float(item.get('minimum_stock', 0))
        })

    return jsonify(serialize_response(inventory_data)), 200


@reports_bp.route('/inventory/price-history', methods=['GET'])
@jwt_required()
@admin_required
def get_price_history():
    """Audit trail of all price/unit changes"""
    db = get_db()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    item_id = request.args.get('item_id')

    query = db.table('price_change_history').select(
        '*, items(name, category, unit, price), users!proposed_by(full_name)'
    )

    if item_id:
        query = query.eq('item_id', item_id)

    query = query.order('proposed_at', desc=True)
    query = paginate_query(query, page, per_page)
    result = query.execute()

    return jsonify(serialize_response({
        'history': result.data or [],
        'page': page,
        'per_page': per_page
    })), 200


@reports_bp.route('/inventory/low-stock', methods=['GET'])
@jwt_required()
@role_required('admin', 'grain_shop_user')
def get_low_stock_alerts():
    """Items below minimum threshold"""
    db = get_db()

    items = db.table('items').select('*').eq('is_active', True).execute()

    low_stock = []
    for item in (items.data or []):
        received = db.table('grain_shop_inventory').select('quantity').eq('item_id', item['id']).execute()
        total_received = sum(float(r['quantity']) for r in (received.data or []))

        distributed = db.table('distribution_log').select('quantity').eq('item_id', item['id']).execute()
        total_distributed = sum(float(d['quantity']) for d in (distributed.data or []))

        current = total_received - total_distributed
        min_stock = float(item.get('minimum_stock', 0))

        if current < min_stock:
            low_stock.append({
                'item_name': item['name'],
                'category': item['category'],
                'unit': item['unit'],
                'current_stock': current,
                'minimum_stock': min_stock,
                'deficit': min_stock - current
            })

    return jsonify(serialize_response(low_stock)), 200


# =====================================================
# 4. USER REPORTS
# =====================================================

@reports_bp.route('/users', methods=['GET'])
@jwt_required()
@admin_required
def get_user_reports():
    """Complete user reports"""
    db = get_db()
    role_filter = request.args.get('role')
    active_filter = request.args.get('is_active')

    query = db.table('users').select('id, username, email, full_name, role, phone, is_active, created_at, updated_at')

    if role_filter:
        query = query.eq('role', role_filter)
    if active_filter is not None:
        query = query.eq('is_active', active_filter.lower() == 'true')

    result = query.order('role').order('full_name').execute()

    return jsonify(serialize_response({
        'users': result.data or [],
        'total': len(result.data or [])
    })), 200


@reports_bp.route('/users/activity', methods=['GET'])
@jwt_required()
@admin_required
def get_user_activity_report():
    """User activity log"""
    db = get_db()
    user_id = request.args.get('user_id')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)

    query = db.table('activity_log').select('*, users(full_name, role)')

    if user_id:
        query = query.eq('user_id', user_id)

    query = query.order('created_at', desc=True)
    query = paginate_query(query, page, per_page)
    result = query.execute()

    return jsonify(serialize_response({
        'activities': result.data or [],
        'page': page,
        'per_page': per_page
    })), 200


# =====================================================
# 5. CONTRACTOR REPORTS
# =====================================================

@reports_bp.route('/contractors/current', methods=['GET'])
@jwt_required()
@admin_required
def get_current_contractor():
    """Current active contractor details"""
    db = get_db()
    result = db.table('contractors').select('*').eq('is_active', True).execute()
    return jsonify(serialize_response(result.data or [])), 200


@reports_bp.route('/contractors/history', methods=['GET'])
@jwt_required()
@admin_required
def get_contractor_history():
    """Past contractors with tenure"""
    db = get_db()
    result = db.table('contractors').select('*').order('tender_year', desc=True).execute()
    return jsonify(serialize_response(result.data or [])), 200


@reports_bp.route('/contractors/performance', methods=['GET'])
@jwt_required()
@admin_required
def get_contractor_performance():
    """Contractor performance — supply timeliness, delivery records"""
    db = get_db()
    contractor_id = request.args.get('contractor_id')

    query = db.table('contractor_supplies').select(
        'contractor_id, contractors(name), supply_date, supplied_quantity, unit_price, items(name, category)'
    )

    if contractor_id:
        query = query.eq('contractor_id', contractor_id)

    result = query.order('supply_date', desc=True).execute()

    # Aggregate
    contractors = {}
    for s in (result.data or []):
        c_id = s.get('contractor_id')
        if c_id not in contractors:
            contractors[c_id] = {
                'contractor_id': c_id,
                'contractor_name': s.get('contractors', {}).get('name', 'Unknown'),
                'total_supplies': 0,
                'total_quantity': 0,
                'total_cost': 0,
                'last_supply_date': None
            }
        contractors[c_id]['total_supplies'] += 1
        contractors[c_id]['total_quantity'] += float(s.get('supplied_quantity', 0))
        unit_price = float(s.get('unit_price', 0)) if s.get('unit_price') else 0
        contractors[c_id]['total_cost'] += float(s.get('supplied_quantity', 0)) * unit_price
        if not contractors[c_id]['last_supply_date'] or (s.get('supply_date') and s['supply_date'] > contractors[c_id]['last_supply_date']):
            contractors[c_id]['last_supply_date'] = s.get('supply_date')

    return jsonify(serialize_response(list(contractors.values()))), 200


# =====================================================
# 6. DAILY MESS ENTRY REPORTS
# =====================================================

@reports_bp.route('/mess/daily-entries', methods=['GET'])
@jwt_required()
@admin_required
def get_daily_mess_entries():
    """Daily entries by mess, filterable by date"""
    db = get_db()
    mess_id = request.args.get('mess_id')
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)

    query = db.table('daily_ration_usage').select(
        '*, items(name, category, unit), mess(name), users!recorded_by(full_name)'
    )

    if mess_id:
        query = query.eq('mess_id', mess_id)
    if from_date:
        query = query.gte('usage_date', from_date)
    if to_date:
        query = query.lte('usage_date', to_date)

    query = query.order('usage_date', desc=True)
    query = paginate_query(query, page, per_page)
    result = query.execute()

    return jsonify(serialize_response({
        'entries': result.data or [],
        'page': page,
        'per_page': per_page
    })), 200


@reports_bp.route('/mess/distributed-vs-received', methods=['GET'])
@jwt_required()
@admin_required
def get_distributed_vs_received():
    """Compare what Controller distributed vs what mess logged"""
    db = get_db()
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')

    # Get distributions
    dist_query = db.table('distribution_log').select(
        'mess_id, item_id, quantity, distribution_date, mess(name), items(name, unit)'
    )
    if from_date:
        dist_query = dist_query.gte('distribution_date', from_date)
    if to_date:
        dist_query = dist_query.lte('distribution_date', to_date)
    distributions = dist_query.execute()

    # Get mess usage entries
    usage_query = db.table('daily_ration_usage').select(
        'mess_id, item_id, quantity_used, usage_date, mess(name), items(name, unit)'
    )
    if from_date:
        usage_query = usage_query.gte('usage_date', from_date)
    if to_date:
        usage_query = usage_query.lte('usage_date', to_date)
    usage = usage_query.execute()

    # Build comparison by mess and item
    comparison = {}
    for d in (distributions.data or []):
        key = f"{d['mess_id']}_{d['item_id']}"
        if key not in comparison:
            comparison[key] = {
                'mess_name': d.get('mess', {}).get('name', ''),
                'item_name': d.get('items', {}).get('name', ''),
                'unit': d.get('items', {}).get('unit', ''),
                'distributed': 0,
                'received': 0
            }
        comparison[key]['distributed'] += float(d.get('quantity', 0))

    for u in (usage.data or []):
        key = f"{u['mess_id']}_{u['item_id']}"
        if key not in comparison:
            comparison[key] = {
                'mess_name': u.get('mess', {}).get('name', ''),
                'item_name': u.get('items', {}).get('name', ''),
                'unit': u.get('items', {}).get('unit', ''),
                'distributed': 0,
                'received': 0
            }
        comparison[key]['received'] += float(u.get('quantity_used', 0))

    return jsonify(serialize_response(list(comparison.values()))), 200


# =====================================================
# 7. FINANCIAL REPORTS
# =====================================================

@reports_bp.route('/financial/expenditure', methods=['GET'])
@jwt_required()
@admin_required
def get_total_expenditure():
    """Total expenditure by category and time period"""
    db = get_db()
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')

    query = db.table('contractor_supplies').select(
        'supplied_quantity, unit_price, supply_date, items(name, category, unit), contractors(name)'
    )

    if from_date:
        query = query.gte('supply_date', from_date)
    if to_date:
        query = query.lte('supply_date', to_date)

    result = query.order('supply_date', desc=True).execute()

    # Calculate totals by category
    by_category = {}
    total = 0
    for s in (result.data or []):
        cat = s.get('items', {}).get('category', 'unknown')
        qty = float(s.get('supplied_quantity', 0))
        price = float(s.get('unit_price', 0)) if s.get('unit_price') else 0
        cost = qty * price

        if cat not in by_category:
            by_category[cat] = {'category': cat, 'total_cost': 0, 'total_quantity': 0, 'supply_count': 0}
        by_category[cat]['total_cost'] += cost
        by_category[cat]['total_quantity'] += qty
        by_category[cat]['supply_count'] += 1
        total += cost

    return jsonify(serialize_response({
        'by_category': list(by_category.values()),
        'total_expenditure': total
    })), 200


@reports_bp.route('/financial/cost-per-mess', methods=['GET'])
@jwt_required()
@admin_required
def get_cost_per_mess():
    """Expenditure breakdown per mess facility"""
    db = get_db()
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')

    query = db.table('distribution_log').select(
        'mess_id, item_id, quantity, mess(name), items(name, price, unit)'
    )

    if from_date:
        query = query.gte('distribution_date', from_date)
    if to_date:
        query = query.lte('distribution_date', to_date)

    result = query.execute()

    by_mess = {}
    for d in (result.data or []):
        mess_name = d.get('mess', {}).get('name', 'Unknown')
        qty = float(d.get('quantity', 0))
        price = float(d.get('items', {}).get('price', 0)) if d.get('items', {}).get('price') else 0
        cost = qty * price

        if mess_name not in by_mess:
            by_mess[mess_name] = {'mess_name': mess_name, 'total_cost': 0, 'total_items': 0}
        by_mess[mess_name]['total_cost'] += cost
        by_mess[mess_name]['total_items'] += 1

    return jsonify(serialize_response(list(by_mess.values()))), 200


# =====================================================
# EXISTING CORE REPORTS (kept from original)
# =====================================================

@reports_bp.route('/data-flow', methods=['GET'])
@jwt_required()
@admin_required
def get_data_flow():
    """Get daily data flow summary"""
    db = get_db()
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')

    if not from_date:
        from_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    if not to_date:
        to_date = datetime.now().strftime('%Y-%m-%d')

    try:
        result = db.table('daily_data_flow_summary').select('*').gte(
            'activity_date', from_date
        ).lte('activity_date', to_date).execute()
        return jsonify(serialize_response(result.data)), 200
    except Exception:
        # Fallback: query activity_log directly if view doesn't exist
        result = db.table('activity_log').select('action, table_name, created_at').gte(
            'created_at', from_date
        ).lte('created_at', to_date).order('created_at', desc=True).execute()

        # Aggregate by date and action
        summary = {}
        for a in (result.data or []):
            date = a.get('created_at', '')[:10]
            action = a.get('action', 'UNKNOWN')
            key = f"{date}_{action}"
            if key not in summary:
                summary[key] = {
                    'activity_date': date,
                    'action': action,
                    'table_name': a.get('table_name', ''),
                    'action_count': 0
                }
            summary[key]['action_count'] += 1

        return jsonify(serialize_response(list(summary.values()))), 200


@reports_bp.route('/activity-log', methods=['GET'])
@jwt_required()
@admin_required
def get_activity_log():
    """Get detailed activity log (Audit Trail)"""
    db = get_db()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    action = request.args.get('action')
    table_name = request.args.get('table_name')
    user_id = request.args.get('user_id')
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')

    query = db.table('activity_log').select('*, users(full_name, role)')

    if action:
        query = query.eq('action', action)
    if table_name:
        query = query.eq('table_name', table_name)
    if user_id:
        query = query.eq('user_id', user_id)
    if from_date:
        query = query.gte('created_at', from_date)
    if to_date:
        query = query.lte('created_at', to_date)

    offset = (page - 1) * per_page
    result = query.order('created_at', desc=True).range(offset, offset + per_page - 1).execute()

    return jsonify(serialize_response({
        'activities': result.data,
        'page': page,
        'per_page': per_page
    })), 200


@reports_bp.route('/grain-shop/summary', methods=['GET'])
@jwt_required()
@role_required('admin', 'grain_shop_user')
def get_grain_shop_summary():
    """Get grain shop daily summary"""
    db = get_db()
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')

    query = db.table('grain_shop_daily_summary').select('*')

    if from_date:
        query = query.gte('received_date', from_date)
    if to_date:
        query = query.lte('received_date', to_date)

    result = query.order('received_date', desc=True).execute()
    return jsonify(serialize_response(result.data)), 200


@reports_bp.route('/mess/summary', methods=['GET'])
@jwt_required()
@role_required('admin', 'grain_shop_user')
def get_mess_summary():
    """Get mess daily consumption summary"""
    db = get_db()
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')

    query = db.table('mess_daily_summary').select('*')

    if from_date:
        query = query.gte('usage_date', from_date)
    if to_date:
        query = query.lte('usage_date', to_date)

    result = query.order('usage_date', desc=True).execute()
    return jsonify(serialize_response(result.data)), 200


@reports_bp.route('/category-wise', methods=['GET'])
@jwt_required()
@admin_required
def get_category_wise_report():
    """Get category-wise inventory report"""
    db = get_db()

    categories = ['veg', 'non_veg', 'grain_shop']
    report = {}

    for category in categories:
        items = db.table('items').select('id').eq('category', category).eq('is_active', True).execute()
        item_ids = [i['id'] for i in items.data] if items.data else []

        if item_ids:
            inventory = db.table('grain_shop_inventory').select('quantity').in_('item_id', item_ids).execute()
            total_qty = sum(float(i['quantity']) for i in inventory.data) if inventory.data else 0
        else:
            total_qty = 0

        report[category] = {
            'item_count': len(item_ids),
            'total_quantity': total_qty
        }

    return jsonify(serialize_response(report)), 200
