"""Items Management Page - Admin Only"""
import streamlit as st
import pandas as pd


def show(api_request):
    """Display items management interface"""
    st.subheader("📦 Ration Items Management")
    
    tab1, tab2 = st.tabs(["📋 All Items", "➕ Add Item"])
    
    with tab1:
        show_items_list(api_request)
    
    with tab2:
        show_create_item_form(api_request)


def show_items_list(api_request):
    """Display list of all items"""
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        search = st.text_input("🔍 Search", placeholder="Search items")
    
    with col2:
        category = st.selectbox("Category", ["All", "veg", "non_veg", "grocery"],
                               format_func=lambda x: x.replace('_', '-').title() if x != "All" else "All")
    
    with col3:
        st.write("")
        st.write("")
        st.button("🔄 Refresh")
    
    params = {}
    if search:
        params['search'] = search
    if category != "All":
        params['category'] = category
    
    response, error = api_request('GET', '/items', params=params)
    
    if error:
        st.error(error)
        return
    
    items = response.get('data', {}).get('items', []) if response else []
    
    if not items:
        st.info("No items found")
        return
    
    # Category badges
    category_colors = {
        'veg': '#28a745',
        'non_veg': '#dc3545',
        'grocery': '#fd7e14'
    }
    
    for item in items:
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
            
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
                st.write(f"📏 Unit: {item.get('unit', 'N/A')}")
            
            with col3:
                st.write(f"📊 Min Stock: {item.get('minimum_stock', 0)}")
            
            with col4:
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("✏️", key=f"edit_i_{item['id']}", help="Edit"):
                        st.session_state.edit_item = item
                with col_b:
                    if st.button("🗑️", key=f"del_i_{item['id']}", help="Deactivate"):
                        api_request('DELETE', f"/items/{item['id']}")
                        st.rerun()
            
            if item.get('description'):
                st.caption(item['description'])
            
            st.divider()
    
    # Edit dialog
    if 'edit_item' in st.session_state:
        show_edit_item_dialog(api_request, st.session_state.edit_item)


def show_create_item_form(api_request):
    """Form to create new item"""
    with st.form("create_item_form"):
        st.markdown("### Add New Ration Item")
        
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input("Item Name *", placeholder="Enter item name")
            category = st.selectbox("Category *", ["veg", "non_veg", "grocery"],
                                   format_func=lambda x: x.replace('_', '-').title())
        
        with col2:
            unit = st.selectbox("Unit *", ["kg", "liters", "pieces", "grams", "packets"])
            minimum_stock = st.number_input("Minimum Stock Level", min_value=0.0, value=0.0)
        
        description = st.text_area("Description", placeholder="Optional description")
        
        if st.form_submit_button("➕ Add Item", use_container_width=True):
            if not name:
                st.error("Item name is required")
            else:
                data = {
                    'name': name,
                    'category': category,
                    'unit': unit,
                    'minimum_stock': minimum_stock,
                    'description': description
                }
                
                response, error = api_request('POST', '/items', data=data)
                
                if error:
                    st.error(error)
                elif response and response.get('status') == 'success':
                    st.success("Item added successfully!")
                    st.balloons()
                else:
                    st.error(response.get('error', 'Failed to add item'))


@st.dialog("✏️ Edit Item", width="large")
def show_edit_item_dialog(api_request, item):
    """Dialog popup to edit item"""
    st.markdown(f"**Editing:** {item.get('name', '')} ({item.get('category', '').replace('_', '-').title()})")
    st.divider()
    
    col1, col2 = st.columns(2)
    
    with col1:
        name = st.text_input("Name", value=item.get('name', ''))
        categories = ["veg", "non_veg", "grocery"]
        cat_idx = categories.index(item.get('category', 'veg')) if item.get('category') in categories else 0
        category = st.selectbox("Category", categories, index=cat_idx,
                               format_func=lambda x: x.replace('_', '-').title())
    
    with col2:
        units = ["kg", "liters", "pieces", "grams", "packets"]
        unit_idx = units.index(item.get('unit', 'kg')) if item.get('unit') in units else 0
        unit = st.selectbox("Unit", units, index=unit_idx)
        minimum_stock = st.number_input("Minimum Stock", value=float(item.get('minimum_stock', 0)))
        is_active = st.checkbox("Active", value=item.get('is_active', True))
    
    description = st.text_area("Description", value=item.get('description', '') or '')
    
    st.divider()
    col_a, col_b = st.columns(2)
    
    with col_a:
        if st.button("💾 Save", use_container_width=True, type="primary"):
            data = {
                'name': name,
                'category': category,
                'unit': unit,
                'minimum_stock': minimum_stock,
                'description': description,
                'is_active': is_active
            }
            
            response, error = api_request('PUT', f"/items/{item['id']}", data=data)
            
            if response and response.get('status') == 'success':
                st.success("Updated!")
                if 'edit_item' in st.session_state:
                    del st.session_state.edit_item
                st.rerun()
            else:
                st.error(error or 'Failed')
    
    with col_b:
        if st.button("❌ Cancel", use_container_width=True):
            if 'edit_item' in st.session_state:
                del st.session_state.edit_item
            st.rerun()
