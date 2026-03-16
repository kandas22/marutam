"""
Supply Management Page
Track contractor supplies to controller (Step 5)
Record incoming supplies and view supply history
"""
import streamlit as st
import pandas as pd
from datetime import datetime


def show(api_request, user):
    """Display supply management"""
    role = user.get('role', '')

    st.subheader("🚚 Supply Management")

    if role in ('admin', 'grain_shop_user'):
        tab1, tab2, tab3, tab4 = st.tabs([
            "📥 Record Supply",
            "📋 Supply History",
            "⏳ Pending Supplies",
            "📊 Supply Summary"
        ])

        with tab1:
            record_supply_form(api_request)
        with tab2:
            show_supply_history(api_request)
        with tab3:
            show_pending_supplies(api_request)
        with tab4:
            show_supply_summary(api_request)
    else:
        st.warning("You do not have access to supply management.")


def record_supply_form(api_request):
    """Form to record items supplied by contractor"""
    st.markdown("### 📥 Record Contractor Supply")

    # Get active contractors
    contractors_resp, _ = api_request('GET', '/contractors', params={'active_only': 'true'})
    contractors = contractors_resp.get('data', {}).get('contractors', []) if contractors_resp else []

    if not contractors:
        st.warning("No active contractors. Please add a contractor first.")
        return

    contractor_options = {c['name']: c['id'] for c in contractors}

    # Get items
    items_resp, _ = api_request('GET', '/items', params={'active_only': 'true'})
    items_list = items_resp.get('data', {}).get('items', []) if items_resp else []

    if not items_list:
        st.warning("No items available.")
        return

    # Get pending demands (approved/forwarded)
    demands_resp, _ = api_request('GET', '/supplies/pending')
    pending_demands = demands_resp.get('data', []) if demands_resp else []

    with st.form("record_supply_form"):
        col1, col2 = st.columns(2)
        with col1:
            selected_contractor = st.selectbox("Contractor", options=list(contractor_options.keys()))
        with col2:
            supply_date = st.date_input("Supply Date", value=datetime.now())

        invoice_number = st.text_input("Invoice Number (Optional)")
        notes = st.text_area("Notes (Optional)")

        # If there are pending demands, show reference
        demand_id = None
        if pending_demands:
            demand_options = {"None": None}
            for d in pending_demands:
                mess_name = d.get('mess', {}).get('name', 'Unknown') if d.get('mess') else 'Unknown'
                label = f"{mess_name} — {d.get('demand_date', 'N/A')}"
                demand_options[label] = d['id']
            selected_demand = st.selectbox("Linked Demand (Optional)", options=list(demand_options.keys()))
            demand_id = demand_options[selected_demand]

        st.markdown("---")
        st.markdown("### Supply Items")

        # Group items by category
        categories = {}
        for item in items_list:
            cat = item.get('category', 'other')
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(item)

        category_labels = {
            'veg': '🥬 Vegetarian',
            'non_veg': '🍗 Non-Vegetarian',
            'grain_shop': '🌾 Grain Shop',
            'grocery': '🛒 Grocery'
        }

        supply_items = []
        for cat, cat_items in categories.items():
            st.markdown(f"**{category_labels.get(cat, cat.title())}**")
            cols = st.columns([3, 1, 1, 1])
            cols[0].markdown("**Item**")
            cols[1].markdown("**Unit**")
            cols[2].markdown("**Qty**")
            cols[3].markdown("**Price/Unit**")

            for item in cat_items:
                cols = st.columns([3, 1, 1, 1])
                cols[0].write(item['name'])
                cols[1].write(item.get('unit', '-'))
                qty = cols[2].number_input(
                    f"qty",
                    min_value=0.0,
                    value=0.0,
                    step=1.0,
                    label_visibility="collapsed",
                    key=f"supply_qty_{item['id']}"
                )
                price = cols[3].number_input(
                    f"price",
                    min_value=0.0,
                    value=float(item.get('price', 0)) if item.get('price') else 0.0,
                    step=0.5,
                    label_visibility="collapsed",
                    key=f"supply_price_{item['id']}"
                )
                if qty > 0:
                    supply_items.append({
                        'item_id': item['id'],
                        'supplied_quantity': qty,
                        'unit_price': price if price > 0 else None
                    })
            st.markdown("---")

        submitted = st.form_submit_button("📥 Record Supply", use_container_width=True)

        if submitted:
            if not supply_items:
                st.error("Please enter quantity for at least one item")
            else:
                with st.spinner("Recording supply..."):
                    data = {
                        'contractor_id': contractor_options[selected_contractor],
                        'supply_date': supply_date.strftime('%Y-%m-%d'),
                        'invoice_number': invoice_number if invoice_number else None,
                        'notes': notes if notes else None,
                        'items': supply_items
                    }
                    if demand_id:
                        data['demand_id'] = demand_id

                    response, error = api_request('POST', '/supplies', data=data)

                    if error:
                        st.error(error)
                    elif response and response.get('status') == 'success':
                        st.success(f"✅ {response.get('message', 'Supply recorded!')}")
                        st.rerun()
                    else:
                        st.error(response.get('error', 'Failed to record supply'))


def show_supply_history(api_request):
    """Show supply history with filters"""
    st.markdown("### 📋 Supply History")

    col1, col2 = st.columns(2)
    with col1:
        from_date = st.date_input("From", value=datetime(2024, 1, 1), key="supply_from")
    with col2:
        to_date = st.date_input("To", value=datetime.now(), key="supply_to")

    response, error = api_request('GET', '/supplies', params={
        'from_date': from_date.strftime('%Y-%m-%d'),
        'to_date': to_date.strftime('%Y-%m-%d')
    })

    if error:
        st.error(error)
        return

    supplies = response.get('data', {}).get('supplies', []) if response else []

    if not supplies:
        st.info("No supply records found for the selected period.")
        return

    df = pd.DataFrame([{
        'Date': s.get('supply_date', 'N/A'),
        'Contractor': s.get('contractors', {}).get('name', 'Unknown') if s.get('contractors') else 'Unknown',
        'Item': s.get('items', {}).get('name', 'Unknown') if s.get('items') else 'Unknown',
        'Category': (s.get('items', {}).get('category', '') if s.get('items') else '').replace('_', ' ').title(),
        'Qty': s.get('supplied_quantity', 0),
        'Unit': s.get('items', {}).get('unit', '') if s.get('items') else '',
        'Price/Unit': s.get('unit_price', '-'),
        'Invoice': s.get('invoice_number', '-'),
        'Received By': s.get('users', {}).get('full_name', '-') if s.get('users') else '-'
    } for s in supplies])

    st.dataframe(df, use_container_width=True, hide_index=True)

    # Total cost
    total_cost = sum(
        float(s.get('supplied_quantity', 0)) * float(s.get('unit_price', 0) or 0)
        for s in supplies
    )
    st.markdown(f"**Total Cost: ₹{total_cost:,.2f}**")


def show_pending_supplies(api_request):
    """Show approved demands not yet supplied"""
    st.markdown("### ⏳ Pending Supplies (Approved but not yet supplied)")

    response, error = api_request('GET', '/supplies/pending')
    if error:
        st.error(error)
        return

    pending = response.get('data', []) if response else []

    if not pending:
        st.success("✅ All approved demands have been supplied!")
        return

    for demand in pending:
        mess_name = demand.get('mess', {}).get('name', 'Unknown') if demand.get('mess') else 'Unknown'
        date = demand.get('demand_date', 'N/A')
        status = demand.get('status', '').replace('_', ' ').title()

        with st.expander(f"⏳ {mess_name} — {date} ({status})"):
            items = demand.get('demand_items', [])
            if items:
                df = pd.DataFrame([{
                    'Item': i.get('items', {}).get('name', 'Unknown') if i.get('items') else 'Unknown',
                    'Category': (i.get('items', {}).get('category', '') if i.get('items') else '').replace('_', ' ').title(),
                    'Approved Qty': i.get('approved_quantity', i.get('requested_quantity', 0)),
                    'Unit': i.get('items', {}).get('unit', '') if i.get('items') else ''
                } for i in items])
                st.dataframe(df, use_container_width=True, hide_index=True)


def show_supply_summary(api_request):
    """Show supply summary and analytics"""
    st.markdown("### 📊 Supply Summary")

    col1, col2 = st.columns(2)
    with col1:
        from_date = st.date_input("From", value=datetime(2024, 1, 1), key="summary_from")
    with col2:
        to_date = st.date_input("To", value=datetime.now(), key="summary_to")

    response, error = api_request('GET', '/supplies/summary', params={
        'from_date': from_date.strftime('%Y-%m-%d'),
        'to_date': to_date.strftime('%Y-%m-%d')
    })

    if error:
        st.error(error)
        return

    data = response.get('data', []) if response else []

    if not data:
        st.info("No supply data available for the selected period.")
        return

    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Summary metrics
    if not df.empty and 'total_cost' in df.columns:
        total = df['total_cost'].sum()
        st.metric("Total Expenditure", f"₹{total:,.2f}")
