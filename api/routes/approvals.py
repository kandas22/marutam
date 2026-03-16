"""
Approval Management Routes
Endpoints for admin to approve/reject pending updates from mess users
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database import get_db
from utils import admin_required, log_activity, serialize_response, paginate_query

approvals_bp = Blueprint('approvals', __name__)


@approvals_bp.route('/pending', methods=['GET'])
@jwt_required()
@admin_required
def get_pending_approvals():
    """Get all pending approval requests (Admin only)"""
    db = get_db()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    table_filter = request.args.get('table_name')
    
    query = db.table('pending_updates').select(
        '*, users!requested_by(full_name, email)'
    ).eq('approval_status', 'pending')
    
    if table_filter:
        query = query.eq('table_name', table_filter)
    
    query = query.order('created_at', desc=True)
    query = paginate_query(query, page, per_page)
    result = query.execute()
    
    return jsonify(serialize_response({
        'pending_updates': result.data,
        'page': page,
        'per_page': per_page
    })), 200


@approvals_bp.route('/pending/count', methods=['GET'])
@jwt_required()
@admin_required
def get_pending_count():
    """Get count of pending approvals"""
    db = get_db()
    result = db.table('pending_updates').select('id', count='exact').eq('approval_status', 'pending').execute()
    return jsonify(serialize_response({'count': result.count if result.count else 0})), 200


@approvals_bp.route('/<approval_id>/approve', methods=['POST'])
@jwt_required()
@admin_required
def approve_update(approval_id):
    """Approve a pending update request"""
    admin_id = get_jwt_identity()
    db = get_db()
    
    pending = db.table('pending_updates').select('*').eq('id', approval_id).single().execute()
    if not pending.data:
        return jsonify({'error': 'Approval request not found'}), 404
    
    if pending.data['approval_status'] != 'pending':
        return jsonify({'error': 'Request has already been processed'}), 400
    
    pending_data = pending.data
    table_name = pending_data['table_name']
    record_id = pending_data['record_id']
    field_name = pending_data['field_name']
    new_value = pending_data['new_value']
    
    db.table(table_name).update({field_name: new_value}).eq('id', record_id).execute()
    db.table('pending_updates').update({
        'approval_status': 'approved',
        'approved_by': admin_id
    }).eq('id', approval_id).execute()
    
    log_activity(admin_id, 'APPROVE', 'pending_updates', approval_id)
    return jsonify(serialize_response(None, 'Update approved successfully')), 200


@approvals_bp.route('/<approval_id>/reject', methods=['POST'])
@jwt_required()
@admin_required
def reject_update(approval_id):
    """Reject a pending update request"""
    admin_id = get_jwt_identity()
    data = request.get_json() or {}
    db = get_db()
    
    pending = db.table('pending_updates').select('*').eq('id', approval_id).single().execute()
    if not pending.data or pending.data['approval_status'] != 'pending':
        return jsonify({'error': 'Invalid request'}), 400
    
    db.table('pending_updates').update({
        'approval_status': 'rejected',
        'approved_by': admin_id,
        'rejection_reason': data.get('reason')
    }).eq('id', approval_id).execute()
    
    log_activity(admin_id, 'REJECT', 'pending_updates', approval_id)
    return jsonify(serialize_response(None, 'Update request rejected')), 200


@approvals_bp.route('/history', methods=['GET'])
@jwt_required()
@admin_required
def get_approval_history():
    """Get history of processed (approved/rejected) approval requests"""
    db = get_db()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    status_filter = request.args.get('status')
    
    try:
        query = db.table('pending_updates').select(
            '*, users!requested_by(full_name, email)'
        ).neq('approval_status', 'pending')
        
        if status_filter and status_filter in ['approved', 'rejected']:
            query = query.eq('approval_status', status_filter)
        
        query = query.order('created_at', desc=True)
        query = paginate_query(query, page, per_page)
        result = query.execute()
        
        return jsonify(serialize_response({
            'history': result.data or [],
            'page': page,
            'per_page': per_page
        })), 200
    except Exception as e:
        print(f"Approval history error: {e}")
        return jsonify(serialize_response({
            'history': [],
            'page': page,
            'per_page': per_page
        })), 200


@approvals_bp.route('/daily-usage/pending', methods=['GET'])
@jwt_required()
@admin_required
def get_pending_daily_usage():
    """Get pending daily ration usage entries for approval"""
    db = get_db()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    query = db.table('daily_ration_usage').select(
        '*, items(name, category, unit), mess(name), users!recorded_by(full_name)'
    ).eq('approval_status', 'pending').order('created_at', desc=True)
    query = paginate_query(query, page, per_page)
    result = query.execute()
    
    return jsonify(serialize_response({
        'pending_usage': result.data,
        'page': page,
        'per_page': per_page
    })), 200


@approvals_bp.route('/daily-usage/<usage_id>/approve', methods=['POST'])
@jwt_required()
@admin_required
def approve_daily_usage(usage_id):
    """Approve a daily ration usage entry"""
    admin_id = get_jwt_identity()
    db = get_db()
    
    result = db.table('daily_ration_usage').update({
        'approval_status': 'approved',
        'approved_by': admin_id
    }).eq('id', usage_id).eq('approval_status', 'pending').execute()
    
    if result.data:
        log_activity(admin_id, 'APPROVE', 'daily_ration_usage', usage_id)
        return jsonify(serialize_response(None, 'Daily usage approved')), 200
    return jsonify({'error': 'Record not found or already processed'}), 400


@approvals_bp.route('/daily-usage/<usage_id>/reject', methods=['POST'])
@jwt_required()
@admin_required
def reject_daily_usage(usage_id):
    """Reject a daily ration usage entry"""
    admin_id = get_jwt_identity()
    db = get_db()
    
    result = db.table('daily_ration_usage').update({
        'approval_status': 'rejected',
        'approved_by': admin_id
    }).eq('id', usage_id).eq('approval_status', 'pending').execute()
    
    if result.data:
        log_activity(admin_id, 'REJECT', 'daily_ration_usage', usage_id)
        return jsonify(serialize_response(None, 'Daily usage rejected')), 200
    return jsonify({'error': 'Record not found or already processed'}), 400
