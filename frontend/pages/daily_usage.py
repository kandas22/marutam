"""Daily Usage Page - Mess Users"""
import streamlit as st
import pandas as pd
from datetime import datetime


def show(api_request, user):
    """Display daily usage management for mess users"""
    st.subheader("📅 Daily Ration Usage")
    
    # Get assigned mess
    mess_response, error = api_request('GET', '/mess')
    
    if error:
        st.error(error)
        return
    
    mess_list = mess_response.get('data', []) if mess_response else []
    
    if not mess_list:
        st.warning("No mess assigned to you. Please contact administrator.")
        return
    
    mess = mess_list[0]
    mess_id = mess['id']
    
    st.markdown(f"""
    <div class="info-card">
        <h4>🍽️ {mess.get('name', 'Your Mess')}</h4>
        <p>Record daily ration consumption. Entries require admin approval.</p>
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["📋 Usage History", "➕ Record Usage"])
    
    with tab1:
        show_usage_history(api_request, mess_id)
    
    with tab2:
        show_add_usage_form(api_request, mess_id)


def show_usage_history(api_request, mess_id):
    """Display usage history"""
    col1, col2, col3 = st.columns([2, 2, 2])
    
    with col1:
        from_date = st.date_input("From Date", value=None, key="usage_from")
    
    with col2:
        to_date = st.date_input("To Date", value=None, key="usage_to")
    
    with col3:
        status = st.selectbox(
            "Status",
            ["All", "pending", "approved", "rejected"],
            format_func=lambda x: x.title() if x != "All" else "All"
        )
    
    params = {}
    if from_date:
        params['from_date'] = from_date.strftime('%Y-%m-%d')
    if to_date:
        params['to_date'] = to_date.strftime('%Y-%m-%d')
    if status != "All":
        params['status'] = status
    
    response, error = api_request('GET', f'/mess/{mess_id}/daily-usage', params=params)
    
    if error:
        st.error(error)
        return
    
    usage = response.get('data', {}).get('usage', []) if response else []
    
    if not usage:
        st.info("No usage records found")
        return
    
    # Status colors
    status_colors = {
        'pending': '#ffc107',
        'approved': '#28a745',
        'rejected': '#dc3545'
    }
    
    for entry in usage:
        item = entry.get('items', {})
        entry_status = entry.get('approval_status', 'pending')
        color = status_colors.get(entry_status, '#6c757d')
        
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
            
            with col1:
                st.write(f"**{item.get('name', 'N/A')}**")
                st.caption(f"Category: {item.get('category', '').replace('_', '-').title()}")
            
            with col2:
                st.write(f"📦 {entry.get('quantity_used', 0)} {item.get('unit', '')}")
                if entry.get('meal_type'):
                    st.caption(f"🍴 {entry['meal_type'].title()}")
            
            with col3:
                st.write(f"📅 {entry.get('usage_date', 'N/A')}")
                if entry.get('personnel_count'):
                    st.caption(f"👥 {entry['personnel_count']} personnel")
            
            with col4:
                st.markdown(f"""
                <span style="background-color: {color}; color: white; padding: 4px 12px; border-radius: 4px; font-size: 0.8rem;">
                    {entry_status.upper()}
                </span>
                """, unsafe_allow_html=True)
            
            if entry.get('notes'):
                st.caption(f"📝 {entry['notes']}")
            
            st.divider()


def show_add_usage_form(api_request, mess_id):
    """Form to record daily usage"""
    # Get items
    items_response, _ = api_request('GET', '/items')
    items = items_response.get('data', {}).get('items', []) if items_response else []
    
    with st.form("add_usage_form"):
        st.markdown("### Record Daily Ration Usage")
        st.caption("⚠️ New entries will require admin approval")
        
        col1, col2 = st.columns(2)
        
        with col1:
            item_options = {i['id']: f"{i['name']} ({i['category'].replace('_', '-')}) - {i['unit']}" for i in items}
            item_id = st.selectbox(
                "Item *",
                options=list(item_options.keys()),
                format_func=lambda x: item_options.get(x, 'Select')
            )
            
            quantity_used = st.number_input("Quantity Used *", min_value=0.01, value=1.0)
            
            meal_type = st.selectbox(
                "Meal Type",
                ["", "breakfast", "lunch", "dinner", "snacks"],
                format_func=lambda x: x.title() if x else "Select (Optional)"
            )
        
        with col2:
            usage_date = st.date_input("Usage Date", value=datetime.now())
            personnel_count = st.number_input("Personnel Count", min_value=0, value=0)
        
        notes = st.text_area("Notes", placeholder="Optional notes about the usage")
        
        if st.form_submit_button("📝 Record Usage", use_container_width=True):
            if not item_id or quantity_used <= 0:
                st.error("Please select an item and enter quantity")
            else:
                data = {
                    'item_id': item_id,
                    'quantity_used': quantity_used,
                    'usage_date': usage_date.strftime('%Y-%m-%d'),
                    'meal_type': meal_type if meal_type else None,
                    'personnel_count': personnel_count if personnel_count > 0 else None,
                    'notes': notes if notes else None
                }
                
                response, error = api_request('POST', f'/mess/{mess_id}/daily-usage', data=data)
                
                if error:
                    st.error(error)
                elif response and response.get('status') == 'success':
                    st.success("Usage recorded successfully! Awaiting admin approval.")
                    st.balloons()
                else:
                    st.error(response.get('error', 'Failed to record usage'))
