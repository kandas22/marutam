"""Distribution Management Page"""
import streamlit as st
import pandas as pd
from datetime import datetime


def show(api_request, user):
    """Display distribution management interface"""
    st.subheader("🚚 Distribution Management")
    
    role = user.get('role', '')
    
    # Admin and Grain Shop Users can create distributions
    if role in ['admin', 'grain_shop_user']:
        tab1, tab2 = st.tabs(["📋 Distribution Log", "➕ New Distribution"])
        
        with tab1:
            show_distribution_list(api_request, user)
        
        with tab2:
            show_create_distribution_form(api_request)
    else:
        show_distribution_list(api_request, user)


def show_distribution_list(api_request, user):
    """Display distribution records"""
    col1, col2, col3 = st.columns([2, 2, 2])
    
    with col1:
        # Get mess units for filter
        mess_response, _ = api_request('GET', '/mess')
        mess_list = mess_response.get('data', []) if mess_response else []
        if isinstance(mess_list, dict):
            mess_list = []
        mess_options = {'': 'All Mess Units'}
        mess_options.update({m['id']: m.get('name', 'N/A') for m in mess_list if isinstance(m, dict)})
        
        mess_filter = st.selectbox(
            "Mess Unit",
            options=list(mess_options.keys()),
            format_func=lambda x: mess_options.get(x, 'All')
        )
    
    with col2:
        from_date = st.date_input("From Date", value=None)
    
    with col3:
        to_date = st.date_input("To Date", value=None)
    
    params = {}
    if mess_filter:
        params['mess_id'] = mess_filter
    if from_date:
        params['from_date'] = from_date.strftime('%Y-%m-%d')
    if to_date:
        params['to_date'] = to_date.strftime('%Y-%m-%d')
    
    response, error = api_request('GET', '/distribution', params=params)
    
    if error:
        st.error(error)
        return
    
    data = response.get('data', {}) if response else {}
    if isinstance(data, list):
        distributions = data
    else:
        distributions = data.get('distributions', [])
    
    if not distributions:
        st.info("No distribution records found. Use '➕ New Distribution' to create one.")
        return
    
    for dist in distributions:
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
            
            with col1:
                item_data = dist.get('items')
                if item_data and isinstance(item_data, dict):
                    item_name = item_data.get('name', 'N/A')
                    item_category = item_data.get('category', '').replace('_', '-').title()
                    item_unit = item_data.get('unit', '')
                else:
                    item_name = 'N/A'
                    item_category = ''
                    item_unit = ''
                st.write(f"**{item_name}**")
                st.caption(f"Category: {item_category}")
            
            with col2:
                st.write(f"📦 {dist.get('quantity', 0)} {item_unit}")
                st.caption(f"📅 {dist.get('distribution_date', 'N/A')}")
            
            with col3:
                mess_data = dist.get('mess')
                if mess_data and isinstance(mess_data, dict):
                    mess_name = mess_data.get('name', 'N/A')
                else:
                    mess_name = 'N/A'
                st.write(f"🍽️ {mess_name}")
                
                # Show distributed by / received by info
                distributed_by = dist.get('distributed_by_user')
                received_by = dist.get('received_by_user')
                if distributed_by and isinstance(distributed_by, dict):
                    st.caption(f"📤 By: {distributed_by.get('full_name', 'Unknown')}")
                if received_by and isinstance(received_by, dict):
                    st.caption(f"✅ Received: {received_by.get('full_name', 'Unknown')}")
                elif not dist.get('received_by'):
                    st.caption("⏳ Receipt: Pending")
            
            with col4:
                if user.get('role') == 'mess_user' and not dist.get('received_by'):
                    if st.button("✅ Confirm", key=f"confirm_{dist['id']}"):
                        confirm_response, err = api_request('POST', f"/distribution/confirm-receipt/{dist['id']}")
                        if confirm_response and confirm_response.get('status') == 'success':
                            st.success("Receipt confirmed!")
                            st.rerun()
                        else:
                            st.error(err or 'Failed to confirm receipt')
            
            st.divider()


def show_create_distribution_form(api_request):
    """Form to create distribution with tabular item-quantity input by category"""
    # Get all items
    items_response, _ = api_request('GET', '/items')
    items_data = items_response.get('data', {}) if items_response else {}
    if isinstance(items_data, dict):
        items = items_data.get('items', [])
    else:
        items = items_data if isinstance(items_data, list) else []
    
    # Get mess units
    mess_response, _ = api_request('GET', '/mess')
    mess_list = mess_response.get('data', []) if mess_response else []
    if isinstance(mess_list, dict):
        mess_list = []
    
    if not items:
        st.warning("No items found. Please add items first in Items Management.")
        return
    
    if not mess_list:
        st.warning("No mess units found. Please add mess units first in Mess Management.")
        return
    
    st.markdown("### Create Distribution (Grain Shop → Mess)")
    
    # ── Header controls (outside the form so category filter is dynamic) ──
    col_h1, col_h2, col_h3 = st.columns(3)
    
    with col_h1:
        mess_options = {m['id']: m.get('name', 'N/A') for m in mess_list if isinstance(m, dict)}
        if not mess_options:
            st.warning("No mess units available")
            return
        mess_id = st.selectbox(
            "Mess Unit *",
            options=list(mess_options.keys()),
            format_func=lambda x: mess_options.get(x, 'Select'),
            key="dist_mess_select"
        )
    
    with col_h2:
        category_map = {
            'veg': '🥬 Vegetarian',
            'non_veg': '🍗 Non-Vegetarian',
            'grocery': '🛒 Grocery'
        }
        selected_category = st.selectbox(
            "Category *",
            options=list(category_map.keys()),
            format_func=lambda x: category_map[x],
            key="dist_category_select"
        )
    
    with col_h3:
        distribution_date = st.date_input(
            "Distribution Date",
            value=datetime.now(),
            key="dist_date_input"
        )
    
    # ── Filter items by selected category ──
    filtered_items = [
        i for i in items
        if isinstance(i, dict) and i.get('category') == selected_category
    ]
    
    if not filtered_items:
        st.info(f"No items found in the **{category_map.get(selected_category, selected_category)}** category.")
        return
    
    # Sort items by name
    filtered_items.sort(key=lambda x: x.get('name', ''))
    
    # ── Tabular form for item quantities ──
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #e8f4fd 0%, #f0f7ff 100%); 
                padding: 1rem 1.5rem; border-radius: 10px; margin: 1rem 0;
                border-left: 4px solid #2d5a87;">
        <strong>📋 {category_map.get(selected_category, 'Items')}</strong> — 
        Enter quantities for items to distribute. Items with quantity <strong>0</strong> will be skipped.
    </div>
    """, unsafe_allow_html=True)
    
    # Table header
    st.markdown("""
    <style>
        .dist-table-header {
            display: grid;
            grid-template-columns: 0.5fr 2.5fr 1fr 1.5fr;
            gap: 0.5rem;
            padding: 0.75rem 1rem;
            background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
            color: white;
            border-radius: 8px 8px 0 0;
            font-weight: 600;
            font-size: 0.9rem;
        }
        .dist-item-row {
            display: grid;
            grid-template-columns: 0.5fr 2.5fr 1fr 1.5fr;
            gap: 0.5rem;
            padding: 0.6rem 1rem;
            border-bottom: 1px solid #e0e5ec;
            align-items: center;
            background: white;
        }
        .dist-item-row:nth-child(even) {
            background: #f8f9fa;
        }
        .dist-item-row:hover {
            background: #e8f4fd;
        }
    </style>
    <div class="dist-table-header">
        <span>#</span>
        <span>Item Name</span>
        <span>Unit</span>
        <span>Quantity</span>
    </div>
    """, unsafe_allow_html=True)
    
    with st.form("bulk_distribution_form"):
        quantities = {}
        
        for idx, item in enumerate(filtered_items, 1):
            item_id = item['id']
            item_name = item.get('name', 'N/A')
            item_unit = item.get('unit', '')
            
            col_num, col_name, col_unit, col_qty = st.columns([0.5, 2.5, 1, 1.5])
            
            with col_num:
                st.markdown(f"**{idx}**")
            with col_name:
                st.markdown(f"{item_name}")
            with col_unit:
                st.markdown(f"`{item_unit}`")
            with col_qty:
                quantities[item_id] = st.number_input(
                    f"Qty",
                    min_value=0.0,
                    value=0.0,
                    step=0.5,
                    key=f"qty_{item_id}",
                    label_visibility="collapsed"
                )
        
        st.divider()
        
        notes = st.text_area("Notes (optional)", placeholder="Any notes for this distribution batch", key="dist_notes")
        
        if st.form_submit_button("🚚 Submit Distribution", use_container_width=True, type="primary"):
            # Collect items with quantity > 0
            items_to_distribute = []
            for item in filtered_items:
                qty = quantities.get(item['id'], 0)
                if qty > 0:
                    items_to_distribute.append({
                        'item_id': item['id'],
                        'quantity': qty,
                        'item_name': item.get('name', 'N/A'),
                        'item_unit': item.get('unit', '')
                    })
            
            if not items_to_distribute:
                st.error("⚠️ Please enter quantity for at least one item.")
            elif not mess_id:
                st.error("⚠️ Please select a Mess Unit.")
            else:
                # Send bulk distribution request
                data = {
                    'mess_id': mess_id,
                    'distribution_date': distribution_date.strftime('%Y-%m-%d'),
                    'notes': notes if notes else None,
                    'items': [
                        {'item_id': d['item_id'], 'quantity': d['quantity']}
                        for d in items_to_distribute
                    ]
                }
                
                response, error = api_request('POST', '/distribution/bulk', data=data)
                
                if error:
                    st.error(error)
                elif response and response.get('status') == 'success':
                    count = response.get('data', {}).get('count', len(items_to_distribute))
                    st.success(f"✅ Successfully distributed {count} item(s) to {mess_options.get(mess_id, 'Mess')}!")
                    
                    # Show summary
                    summary_data = []
                    for d in items_to_distribute:
                        summary_data.append({
                            'Item': d['item_name'],
                            'Quantity': d['quantity'],
                            'Unit': d['item_unit']
                        })
                    st.dataframe(
                        pd.DataFrame(summary_data),
                        use_container_width=True,
                        hide_index=True
                    )
                    st.balloons()
                else:
                    error_msg = response.get('error', 'Failed to create distribution') if response else 'Failed'
                    st.error(error_msg)
