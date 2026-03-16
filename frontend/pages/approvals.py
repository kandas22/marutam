"""Approvals Page - Admin Only"""
import streamlit as st
import pandas as pd


def show(api_request):
    """Display approvals management interface"""
    st.subheader("✅ Pending Approvals")
    
    tab1, tab2, tab3 = st.tabs(["📝 Update Requests", "📅 Daily Usage", "📜 History"])
    
    with tab1:
        show_pending_updates(api_request)
    
    with tab2:
        show_pending_daily_usage(api_request)
    
    with tab3:
        show_approval_history(api_request)


def show_pending_updates(api_request):
    """Show pending field update requests"""
    response, error = api_request('GET', '/approvals/pending')
    
    if error:
        st.error(error)
        return
    
    pending = response.get('data', {}).get('pending_updates', []) if response else []
    
    if not pending:
        st.success("✨ No pending update requests!")
        return
    
    st.warning(f"⚠️ {len(pending)} pending update requests")
    
    for item in pending:
        with st.container():
            col1, col2, col3 = st.columns([3, 3, 2])
            
            with col1:
                user_data = item.get('users')
                user_name = user_data.get('full_name', 'Unknown') if user_data and isinstance(user_data, dict) else 'Unknown'
                st.write(f"**Requested by:** {user_name}")
                st.caption(f"Table: {item.get('table_name', 'N/A')}")
            
            with col2:
                st.write(f"**Field:** {item.get('field_name', 'N/A')}")
                st.write(f"Old: `{item.get('old_value', 'N/A')}` → New: `{item.get('new_value', 'N/A')}`")
            
            with col3:
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("✅", key=f"approve_{item['id']}", help="Approve"):
                        resp, err = api_request('POST', f"/approvals/{item['id']}/approve")
                        if resp and resp.get('status') == 'success':
                            st.success("Approved!")
                            st.rerun()
                        else:
                            st.error(err or 'Failed')
                
                with col_b:
                    if st.button("❌", key=f"reject_{item['id']}", help="Reject"):
                        resp, err = api_request('POST', f"/approvals/{item['id']}/reject")
                        if resp and resp.get('status') == 'success':
                            st.info("Rejected")
                            st.rerun()
                        else:
                            st.error(err or 'Failed')
            
            st.divider()


def show_pending_daily_usage(api_request):
    """Show pending daily usage entries"""
    response, error = api_request('GET', '/approvals/daily-usage/pending')
    
    if error:
        st.error(error)
        return
    
    pending = response.get('data', {}).get('pending_usage', []) if response else []
    
    if not pending:
        st.success("✨ No pending daily usage entries!")
        return
    
    st.warning(f"⚠️ {len(pending)} pending daily usage entries")
    
    for entry in pending:
        with st.container():
            col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
            
            with col1:
                item_data = entry.get('items')
                item_name = item_data.get('name', 'N/A') if item_data and isinstance(item_data, dict) else 'N/A'
                item_category = item_data.get('category', '').replace('_', '-').title() if item_data and isinstance(item_data, dict) else ''
                item_unit = item_data.get('unit', '') if item_data and isinstance(item_data, dict) else ''
                st.write(f"**{item_name}**")
                st.caption(f"Category: {item_category}")
            
            with col2:
                st.write(f"📦 {entry.get('quantity_used', 0)} {item_unit}")
                st.caption(f"📅 {entry.get('usage_date', 'N/A')}")
            
            with col3:
                mess_data = entry.get('mess')
                mess_name = mess_data.get('name', 'N/A') if mess_data and isinstance(mess_data, dict) else 'N/A'
                st.write(f"🍽️ {mess_name}")
                user_data = entry.get('users')
                user_name = user_data.get('full_name', 'Unknown') if user_data and isinstance(user_data, dict) else 'Unknown'
                st.caption(f"By: {user_name}")            
            with col4:
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("✅", key=f"approve_u_{entry['id']}", help="Approve"):
                        resp, err = api_request('POST', f"/approvals/daily-usage/{entry['id']}/approve")
                        if resp and resp.get('status') == 'success':
                            st.success("Approved!")
                            st.rerun()
                        else:
                            st.error(err or 'Failed')
                
                with col_b:
                    if st.button("❌", key=f"reject_u_{entry['id']}", help="Reject"):
                        resp, err = api_request('POST', f"/approvals/daily-usage/{entry['id']}/reject")
                        if resp and resp.get('status') == 'success':
                            st.info("Rejected")
                            st.rerun()
                        else:
                            st.error(err or 'Failed')
            
            if entry.get('notes'):
                st.caption(f"Notes: {entry['notes']}")
            
            st.divider()


def show_approval_history(api_request):
    """Show history of approvals"""
    status_filter = st.selectbox("Filter by Status", ["All", "approved", "rejected"])
    
    params = {}
    if status_filter != "All":
        params['status'] = status_filter
    
    response, error = api_request('GET', '/approvals/history', params=params)
    
    if error:
        st.error(error)
        return
    
    history = response.get('data', {}).get('history', []) if response else []
    
    if not history:
        st.info("No approval history found")
        return
    
    df = pd.DataFrame([{
        'Table': h.get('table_name', 'N/A'),
        'Field': h.get('field_name', 'N/A'),
        'Old Value': h.get('old_value', 'N/A'),
        'New Value': h.get('new_value', 'N/A'),
        'Requested By': h.get('users', {}).get('full_name', 'Unknown') if isinstance(h.get('users'), dict) else 'Unknown',
        'Status': h.get('approval_status', 'N/A').upper(),
        'Reason': h.get('rejection_reason', '-')
    } for h in history])
    
    st.dataframe(df, use_container_width=True, hide_index=True)
