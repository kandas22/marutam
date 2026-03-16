"""Grain Shop Inventory Page"""
import streamlit as st
import pandas as pd
from datetime import datetime


def show(api_request, user):
    """Display grain shop inventory interface"""
    st.subheader("🏪 Grain Shop Inventory")
    
    tab1, tab2 = st.tabs(["📦 Inventory", "➕ Add Inventory"])
    
    with tab1:
        show_inventory_list(api_request)
    
    with tab2:
        show_add_inventory_form(api_request)


def show_inventory_list(api_request):
    """Display grain shop inventory"""
    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
    
    with col1:
        # Get contractors for filter
        contractors_response, _ = api_request('GET', '/contractors')
        contractors = contractors_response.get('data', {}).get('contractors', []) if contractors_response else []
        contractor_options = {'': 'All Contractors'}
        contractor_options.update({c['id']: c['name'] for c in contractors})
        
        contractor_filter = st.selectbox(
            "Contractor",
            options=list(contractor_options.keys()),
            format_func=lambda x: contractor_options.get(x, 'All')
        )
    
    with col2:
        category = st.selectbox("Category", ["All", "veg", "non_veg", "grocery"],
                               format_func=lambda x: x.replace('_', '-').title() if x != "All" else "All")
    
    with col3:
        from_date = st.date_input("From Date", value=None)
    
    with col4:
        st.write("")
        st.write("")
        st.button("🔄 Refresh")
    
    params = {}
    if contractor_filter:
        params['contractor_id'] = contractor_filter
    if category != "All":
        params['category'] = category
    if from_date:
        params['from_date'] = from_date.strftime('%Y-%m-%d')
    
    response, error = api_request('GET', '/grain-shop/inventory', params=params)
    
    if error:
        st.error(error)
        return
    
    inventory = response.get('data', {}).get('inventory', []) if response else []
    
    if not inventory:
        st.info("No inventory records found")
        return
    
    # Display as table
    df = pd.DataFrame([{
        'Item': i.get('items', {}).get('name', 'N/A'),
        'Category': i.get('items', {}).get('category', '').replace('_', '-').title(),
        'Contractor': i.get('contractors', {}).get('name', 'N/A'),
        'Quantity': f"{i.get('quantity', 0)} {i.get('items', {}).get('unit', '')}",
        'Unit Price': f"₹{i.get('unit_price', 0)}" if i.get('unit_price') else 'N/A',
        'Received': i.get('received_date', 'N/A'),
        'Batch': i.get('batch_number', 'N/A')
    } for i in inventory])
    
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Stock levels summary
    st.divider()
    st.subheader("📊 Stock Summary")
    
    stock_response, _ = api_request('GET', '/grain-shop/stock-levels')
    stock_data = stock_response.get('data', []) if stock_response else []
    
    if stock_data:
        col1, col2, col3 = st.columns(3)
        
        veg_items = [s for s in stock_data if s.get('category') == 'veg']
        non_veg_items = [s for s in stock_data if s.get('category') == 'non_veg']
        grocery_items = [s for s in stock_data if s.get('category') == 'grocery']
        
        with col1:
            st.metric("🥬 Veg Items", len(veg_items))
        with col2:
            st.metric("🍖 Non-Veg Items", len(non_veg_items))
        with col3:
            st.metric("🛒 Grocery Items", len(grocery_items))


def show_add_inventory_form(api_request):
    """Form to add inventory from contractor"""
    # Get items
    items_response, _ = api_request('GET', '/items')
    items = items_response.get('data', {}).get('items', []) if items_response else []
    
    # Get contractors
    contractors_response, _ = api_request('GET', '/contractors')
    contractors = contractors_response.get('data', {}).get('contractors', []) if contractors_response else []
    
    with st.form("add_inventory_form"):
        st.markdown("### Add Inventory from Contractor")
        
        col1, col2 = st.columns(2)
        
        with col1:
            contractor_options = {c['id']: c['name'] for c in contractors}
            contractor_id = st.selectbox(
                "Contractor *",
                options=list(contractor_options.keys()),
                format_func=lambda x: contractor_options.get(x, 'Select')
            )
            
            item_options = {i['id']: f"{i['name']} ({i['category'].replace('_', '-')})" for i in items}
            item_id = st.selectbox(
                "Item *",
                options=list(item_options.keys()),
                format_func=lambda x: item_options.get(x, 'Select')
            )
            
            quantity = st.number_input("Quantity *", min_value=0.01, value=1.0)
        
        with col2:
            unit_price = st.number_input("Unit Price (₹)", min_value=0.0, value=0.0)
            batch_number = st.text_input("Batch Number", placeholder="Optional")
            received_date = st.date_input("Received Date", value=datetime.now())
            expiry_date = st.date_input("Expiry Date (Optional)", value=None)
        
        if st.form_submit_button("➕ Add Inventory", use_container_width=True):
            if not all([contractor_id, item_id, quantity > 0]):
                st.error("Please fill all required fields")
            else:
                data = {
                    'contractor_id': contractor_id,
                    'item_id': item_id,
                    'quantity': quantity,
                    'unit_price': unit_price if unit_price > 0 else None,
                    'batch_number': batch_number if batch_number else None,
                    'received_date': received_date.strftime('%Y-%m-%d'),
                    'expiry_date': expiry_date.strftime('%Y-%m-%d') if expiry_date else None
                }
                
                response, error = api_request('POST', '/grain-shop/inventory', data=data)
                
                if error:
                    st.error(error)
                elif response and response.get('status') == 'success':
                    st.success("Inventory added successfully!")
                    st.balloons()
                else:
                    st.error(response.get('error', 'Failed'))
