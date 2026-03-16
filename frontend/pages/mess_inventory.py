"""Mess Inventory Page - Mess Users"""
import streamlit as st
import pandas as pd


def show(api_request, user):
    """Display mess inventory for mess users"""
    st.subheader("📦 Mess Inventory")
    
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
        <p>📍 Location: {mess.get('location', 'N/A')} | 👥 Capacity: {mess.get('capacity', 'N/A')}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Filters
    col1, col2 = st.columns([2, 1])
    
    with col1:
        category = st.selectbox(
            "Category",
            ["All", "veg", "non_veg", "grocery"],
            format_func=lambda x: x.replace('_', '-').title() if x != "All" else "All"
        )
    
    with col2:
        st.write("")
        st.write("")
        st.button("🔄 Refresh")
    
    # Get inventory
    params = {}
    if category != "All":
        params['category'] = category
    
    response, error = api_request('GET', f'/mess/{mess_id}/inventory', params=params)
    
    if error:
        st.error(error)
        return
    
    inventory = response.get('data', {}).get('inventory', []) if response else []
    
    if not inventory:
        st.info("No inventory records found")
        return
    
    # Display inventory
    st.divider()
    
    category_colors = {
        'veg': '#28a745',
        'non_veg': '#dc3545',
        'grocery': '#fd7e14'
    }
    
    for inv in inventory:
        item = inv.get('items', {})
        
        with st.container():
            col1, col2, col3 = st.columns([3, 2, 2])
            
            with col1:
                cat = item.get('category', 'veg')
                color = category_colors.get(cat, '#6c757d')
                st.markdown(f"""
                **{item.get('name', 'N/A')}**
                <span style="background-color: {color}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem;">
                    {cat.replace('_', '-').upper()}
                </span>
                """, unsafe_allow_html=True)
            
            with col2:
                st.write(f"📦 {inv.get('quantity', 0)} {item.get('unit', '')}")
            
            with col3:
                st.write(f"📅 {inv.get('date', 'N/A')}")
            
            st.divider()
    
    # Summary
    st.subheader("📊 Inventory Summary by Category")
    
    veg_total = sum(float(i.get('quantity', 0)) for i in inventory if i.get('items', {}).get('category') == 'veg')
    non_veg_total = sum(float(i.get('quantity', 0)) for i in inventory if i.get('items', {}).get('category') == 'non_veg')
    grocery_total = sum(float(i.get('quantity', 0)) for i in inventory if i.get('items', {}).get('category') == 'grocery')
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("🥬 Vegetarian", f"{veg_total:.1f}")
    
    with col2:
        st.metric("🍖 Non-Vegetarian", f"{non_veg_total:.1f}")
    
    with col3:
        st.metric("🛒 Grocery", f"{grocery_total:.1f}")
