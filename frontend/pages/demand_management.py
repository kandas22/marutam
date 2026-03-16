"""
Demand Management Page
Supports the full demand workflow:
  - Mess users: Create, edit, submit demands
  - Controller (grain_shop_user): View, consolidate demands
  - Admin: Approve/reject demands
"""
import streamlit as st
import pandas as pd
from datetime import datetime


def show(api_request, user):
    """Display demand management based on user role"""
    role = user.get('role', '')

    st.subheader("📋 Demand Management")

    if role == 'mess_user':
        show_mess_demand_view(api_request, user)
    elif role == 'grain_shop_user':
        show_controller_demand_view(api_request, user)
    elif role == 'admin':
        show_admin_demand_view(api_request, user)
    elif role == 'contractor':
        show_contractor_demand_view(api_request)
    else:
        st.warning("You do not have access to demand management.")


def show_mess_demand_view(api_request, user):
    """Mess user view — create and manage demands"""
    tab1, tab2 = st.tabs(["📝 Create Demand", "📋 My Demands"])

    with tab1:
        create_demand_form(api_request, user)

    with tab2:
        show_my_demands(api_request, user)


def create_demand_form(api_request, user):
    """Form for mess user to create a demand"""
    st.markdown("### Create New Demand")

    # Get mess facilities assigned to this user
    mess_response, error = api_request('GET', '/mess')
    if error:
        st.error(error)
        return

    mess_list = mess_response.get('data', []) if mess_response else []

    if not mess_list:
        st.warning("No mess assigned. Please contact the administrator.")
        return

    mess = mess_list[0]

    st.info(f"🍽️ Creating demand for **{mess.get('name', 'Your Mess')}**")

    # Get available items
    items_response, _ = api_request('GET', '/items', params={'active_only': 'true'})
    items_list = items_response.get('data', {}).get('items', []) if items_response else []

    if not items_list:
        st.warning("No items available. Please contact the Controller.")
        return

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

    with st.form("new_demand_form"):
        demand_date = st.date_input("Demand Date", value=datetime.now())
        notes = st.text_area("Notes (Optional)", placeholder="Any special instructions...")

        st.markdown("---")
        st.markdown("### Items & Quantities")

        demand_items = []
        for cat, cat_items in categories.items():
            st.markdown(f"**{category_labels.get(cat, cat.title())}**")
            cols = st.columns([3, 1, 1])
            cols[0].markdown("**Item**")
            cols[1].markdown("**Unit**")
            cols[2].markdown("**Qty**")

            for item in cat_items:
                cols = st.columns([3, 1, 1])
                cols[0].write(item['name'])
                cols[1].write(item.get('unit', '-'))
                qty = cols[2].number_input(
                    f"qty_{item['id']}",
                    min_value=0.0,
                    value=0.0,
                    step=1.0,
                    label_visibility="collapsed",
                    key=f"demand_qty_{item['id']}"
                )
                if qty > 0:
                    demand_items.append({
                        'item_id': item['id'],
                        'requested_quantity': qty,
                        'name': item['name']
                    })
            st.markdown("---")

        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            submitted = st.form_submit_button("📝 Save as Draft", use_container_width=True)

        if submitted:
            if not demand_items:
                st.error("Please select at least one item with quantity > 0")
            else:
                with st.spinner("Creating demand..."):
                    response, error = api_request('POST', '/demands', data={
                        'mess_id': mess['id'],
                        'demand_date': demand_date.strftime('%Y-%m-%d'),
                        'notes': notes,
                        'items': [{'item_id': i['item_id'], 'requested_quantity': i['requested_quantity']} for i in demand_items]
                    })

                    if error:
                        st.error(error)
                    elif response and response.get('status') == 'success':
                        st.success(f"✅ Demand created with {len(demand_items)} items!")
                        st.rerun()
                    else:
                        st.error(response.get('error', 'Failed to create demand'))


def show_my_demands(api_request, user):
    """Show demands for the current mess user"""
    st.markdown("### My Demands")

    response, error = api_request('GET', '/demands')
    if error:
        st.error(error)
        return

    demands = response.get('data', {}).get('demands', []) if response else []

    if not demands:
        st.info("No demands found. Create your first demand above!")
        return

    status_colors = {
        'draft': '🔵',
        'submitted': '🟡',
        'approved': '🟢',
        'rejected': '🔴',
        'forwarded_to_contractor': '🟣',
        'supplied_to_controller': '📦',
        'distributed_to_messes': '✅'
    }

    for demand in demands:
        status = demand.get('status', 'draft')
        mess_name = demand.get('mess', {}).get('name', 'Unknown') if demand.get('mess') else 'Unknown'
        date = demand.get('demand_date', 'N/A')
        emoji = status_colors.get(status, '⬜')

        with st.expander(f"{emoji} {mess_name} — {date} ({status.replace('_', ' ').title()})"):
            # Show demand details
            detail_response, _ = api_request('GET', f"/demands/{demand['id']}")
            if detail_response and detail_response.get('data'):
                detail = detail_response['data']
                items = detail.get('demand_items', [])

                if items:
                    df = pd.DataFrame([{
                        'Item': i.get('items', {}).get('name', 'Unknown'),
                        'Category': i.get('items', {}).get('category', '').replace('_', ' ').title(),
                        'Requested': i.get('requested_quantity', 0),
                        'Approved': i.get('approved_quantity', '-'),
                        'Unit': i.get('items', {}).get('unit', '')
                    } for i in items])
                    st.dataframe(df, use_container_width=True, hide_index=True)

                if detail.get('notes'):
                    st.markdown(f"📝 **Notes:** {detail['notes']}")

                if detail.get('rejection_reason'):
                    st.error(f"❌ **Rejection Reason:** {detail['rejection_reason']}")

            # Actions
            if status == 'draft':
                col1, col2, col3 = st.columns([1, 1, 2])
                with col1:
                    if st.button("📤 Submit", key=f"submit_{demand['id']}"):
                        resp, err = api_request('POST', f"/demands/{demand['id']}/submit")
                        if err:
                            st.error(err)
                        elif resp and resp.get('status') == 'success':
                            st.success("Demand submitted!")
                            st.rerun()
                with col2:
                    if st.button("🗑️ Delete", key=f"delete_{demand['id']}"):
                        resp, err = api_request('DELETE', f"/demands/{demand['id']}")
                        if err:
                            st.error(err)
                        else:
                            st.success("Demand deleted")
                            st.rerun()


def show_controller_demand_view(api_request, user):
    """Controller view — consolidate and forward demands"""
    tab1, tab2, tab3 = st.tabs(["📥 Incoming Demands", "📊 Consolidated View", "📤 Forward to Contractor"])

    with tab1:
        show_incoming_demands(api_request)

    with tab2:
        show_consolidated_demands(api_request)

    with tab3:
        show_forward_demands(api_request)


def show_incoming_demands(api_request):
    """Show all incoming demands for the controller"""
    st.markdown("### Incoming Demands from Messes")

    status_filter = st.selectbox("Filter by Status", [
        "All", "submitted", "approved", "forwarded_to_contractor", "supplied_to_controller"
    ], key="ctrl_status_filter")

    params = {}
    if status_filter != "All":
        params['status'] = status_filter

    response, error = api_request('GET', '/demands', params=params)
    if error:
        st.error(error)
        return

    demands = response.get('data', {}).get('demands', []) if response else []

    if not demands:
        st.info("No demands found matching the filter.")
        return

    for demand in demands:
        status = demand.get('status', '')
        mess_name = demand.get('mess', {}).get('name', 'Unknown') if demand.get('mess') else 'Unknown'
        date = demand.get('demand_date', 'N/A')
        submitted_by = demand.get('users', {}).get('full_name', 'Unknown') if demand.get('users') else 'Unknown'

        with st.expander(f"{'🟡' if status == 'submitted' else '🟢'} {mess_name} — {date} | by {submitted_by}"):
            detail_response, _ = api_request('GET', f"/demands/{demand['id']}")
            if detail_response and detail_response.get('data'):
                detail = detail_response['data']
                items = detail.get('demand_items', [])  

                if items:
                    df = pd.DataFrame([{
                        'Item': i.get('items', {}).get('name', 'Unknown'),
                        'Category': i.get('items', {}).get('category', '').replace('_', ' ').title(),
                        'Qty Requested': i.get('requested_quantity', 0),
                        'Qty Approved': i.get('approved_quantity', '-'),
                        'Unit': i.get('items', {}).get('unit', '')
                    } for i in items])
                    st.dataframe(df, use_container_width=True, hide_index=True)


def show_consolidated_demands(api_request):
    """Show consolidated view of all submitted demands"""
    st.markdown("### 📊 Consolidated Demand Report")

    col1, col2 = st.columns(2)
    with col1:
        from_date = st.date_input("From", value=datetime.now(), key="consol_from")
    with col2:
        to_date = st.date_input("To", value=datetime.now(), key="consol_to")

    response, error = api_request('GET', '/demands/consolidated', params={
        'status': 'submitted',
        'from_date': from_date.strftime('%Y-%m-%d'),
        'to_date': to_date.strftime('%Y-%m-%d')
    })

    if error:
        st.error(error)
        return

    data = response.get('data', {}) if response else {}
    consolidated = data.get('consolidated', [])
    total = data.get('total_demands', 0)

    st.info(f"Total demands: **{total}**")

    if consolidated:
        df = pd.DataFrame([{
            'Mess': c.get('demands', {}).get('mess', {}).get('name', 'Unknown') if isinstance(c.get('demands'), dict) else 'Unknown',
            'Item': c.get('items', {}).get('name', 'Unknown'),
            'Category': c.get('items', {}).get('category', '').replace('_', ' ').title(),
            'Qty Requested': c.get('requested_quantity', 0),
            'Unit': c.get('items', {}).get('unit', '')
        } for c in consolidated])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No submitted demands found for the selected period.")


def show_forward_demands(api_request):
    """Forward approved demands to contractor"""
    st.markdown("### 📤 Forward Approved Demands to Contractor")

    # Get approved demands
    response, error = api_request('GET', '/demands', params={'status': 'approved'})
    if error:
        st.error(error)
        return

    demands = response.get('data', {}).get('demands', []) if response else []

    if not demands:
        st.info("No approved demands to forward.")
        return

    # Get active contractors
    contractors_resp, _ = api_request('GET', '/contractors', params={'active_only': 'true'})
    contractors = contractors_resp.get('data', {}).get('contractors', []) if contractors_resp else []

    if not contractors:
        st.warning("No active contractors available. Please add a contractor first.")
        return

    contractor_options = {c['name']: c['id'] for c in contractors}

    for demand in demands:
        mess_name = demand.get('mess', {}).get('name', 'Unknown') if demand.get('mess') else 'Unknown'
        date = demand.get('demand_date', 'N/A')

        with st.expander(f"✅ {mess_name} — {date} (Approved)"):
            detail_response, _ = api_request('GET', f"/demands/{demand['id']}")
            if detail_response and detail_response.get('data'):
                detail = detail_response['data']
                items = detail.get('demand_items', [])

                if items:
                    df = pd.DataFrame([{
                        'Item': i.get('items', {}).get('name', 'Unknown'),
                        'Approved Qty': i.get('approved_quantity', i.get('requested_quantity', 0)),
                        'Unit': i.get('items', {}).get('unit', '')
                    } for i in items])
                    st.dataframe(df, use_container_width=True, hide_index=True)

            selected_contractor = st.selectbox(
                "Select Contractor",
                options=list(contractor_options.keys()),
                key=f"fwd_contractor_{demand['id']}"
            )

            if st.button("📤 Forward to Contractor", key=f"forward_{demand['id']}"):
                resp, err = api_request('POST', f"/demands/{demand['id']}/forward", data={
                    'contractor_id': contractor_options[selected_contractor]
                })
                if err:
                    st.error(err)
                elif resp and resp.get('status') == 'success':
                    st.success(f"Demand forwarded to {selected_contractor}!")
                    st.rerun()


def show_admin_demand_view(api_request, user):
    """Admin view — approve/reject demands"""
    tab1, tab2, tab3 = st.tabs(["⏳ Pending Approval", "📋 All Demands", "📊 Statistics"])

    with tab1:
        show_pending_demand_approvals(api_request)

    with tab2:
        show_all_demands(api_request)

    with tab3:
        show_demand_stats(api_request)


def show_pending_demand_approvals(api_request):
    """Show demands waiting for admin approval"""
    st.markdown("### ⏳ Demands Pending Approval")

    response, error = api_request('GET', '/demands', params={'status': 'submitted'})
    if error:
        st.error(error)
        return

    demands = response.get('data', {}).get('demands', []) if response else []

    if not demands:
        st.success("✅ No demands pending approval!")
        return

    st.warning(f"⚠️ {len(demands)} demand(s) waiting for your review")

    for demand in demands:
        mess_name = demand.get('mess', {}).get('name', 'Unknown') if demand.get('mess') else 'Unknown'
        date = demand.get('demand_date', 'N/A')
        submitted_by = demand.get('users', {}).get('full_name', 'Unknown') if demand.get('users') else 'Unknown'

        with st.expander(f"🟡 {mess_name} — {date} | Submitted by {submitted_by}"):
            detail_response, _ = api_request('GET', f"/demands/{demand['id']}")
            if detail_response and detail_response.get('data'):
                detail = detail_response['data']
                items = detail.get('demand_items', [])

                if items:
                    df = pd.DataFrame([{
                        'Item': i.get('items', {}).get('name', 'Unknown'),
                        'Category': i.get('items', {}).get('category', '').replace('_', ' ').title(),
                        'Requested Qty': i.get('requested_quantity', 0),
                        'Unit': i.get('items', {}).get('unit', '')
                    } for i in items])
                    st.dataframe(df, use_container_width=True, hide_index=True)

                if detail.get('notes'):
                    st.info(f"📝 {detail['notes']}")

            col1, col2, col3 = st.columns([1, 1, 2])
            with col1:
                if st.button("✅ Approve", key=f"approve_{demand['id']}", type="primary"):
                    resp, err = api_request('POST', f"/demands/{demand['id']}/approve")
                    if err:
                        st.error(err)
                    elif resp and resp.get('status') == 'success':
                        st.success("Demand approved!")
                        st.rerun()

            with col2:
                reject_reason = st.text_input("Rejection reason", key=f"reason_{demand['id']}", placeholder="Optional")
                if st.button("❌ Reject", key=f"reject_{demand['id']}"):
                    resp, err = api_request('POST', f"/demands/{demand['id']}/reject", data={
                        'reason': reject_reason
                    })
                    if err:
                        st.error(err)
                    elif resp and resp.get('status') == 'success':
                        st.warning("Demand rejected")
                        st.rerun()


def show_all_demands(api_request):
    """Show all demands with filtering"""
    st.markdown("### 📋 All Demands")

    col1, col2, col3 = st.columns(3)
    with col1:
        status_filter = st.selectbox("Status", [
            "All", "draft", "submitted", "approved", "rejected",
            "forwarded_to_contractor", "supplied_to_controller", "distributed_to_messes"
        ], key="admin_status_filter")
    with col2:
        from_date = st.date_input("From", value=datetime(2024, 1, 1), key="admin_from")
    with col3:
        to_date = st.date_input("To", value=datetime.now(), key="admin_to")

    params = {
        'from_date': from_date.strftime('%Y-%m-%d'),
        'to_date': to_date.strftime('%Y-%m-%d')
    }
    if status_filter != "All":
        params['status'] = status_filter

    response, error = api_request('GET', '/demands', params=params)
    if error:
        st.error(error)
        return

    demands = response.get('data', {}).get('demands', []) if response else []

    if not demands:
        st.info("No demands found matching the filter.")
        return

    df = pd.DataFrame([{
        'Date': d.get('demand_date', 'N/A'),
        'Mess': d.get('mess', {}).get('name', 'Unknown') if d.get('mess') else 'Unknown',
        'Status': d.get('status', '').replace('_', ' ').title(),
        'Submitted By': d.get('users', {}).get('full_name', '-') if d.get('users') else '-',
        'Contractor': d.get('contractors', {}).get('name', '-') if d.get('contractors') else '-'
    } for d in demands])

    st.dataframe(df, use_container_width=True, hide_index=True)


def show_demand_stats(api_request):
    """Show demand statistics"""
    st.markdown("### 📊 Demand Statistics")

    response, error = api_request('GET', '/demands/stats')
    if error:
        st.error(error)
        return

    stats = response.get('data', {}) if response else {}

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Demands", stats.get('total', 0))
    with col2:
        st.metric("Pending Approval", stats.get('submitted', 0))
    with col3:
        st.metric("Approved", stats.get('approved', 0))
    with col4:
        st.metric("Rejected", stats.get('rejected', 0))

    st.divider()

    col5, col6, col7 = st.columns(3)
    with col5:
        st.metric("Draft", stats.get('draft', 0))
    with col6:
        st.metric("Forwarded", stats.get('forwarded_to_contractor', 0))
    with col7:
        st.metric("Supplied", stats.get('supplied_to_controller', 0))


def show_contractor_demand_view(api_request):
    """Contractor view — see demands forwarded to them"""
    st.markdown("### 📦 Demands Assigned to You")

    response, error = api_request('GET', '/demands')
    if error:
        st.error(error)
        return

    demands = response.get('data', {}).get('demands', []) if response else []

    if not demands:
        st.info("No demands currently assigned.")
        return

    for demand in demands:
        status = demand.get('status', '')
        mess_name = demand.get('mess', {}).get('name', 'Unknown') if demand.get('mess') else 'Unknown'
        date = demand.get('demand_date', 'N/A')

        with st.expander(f"📦 {mess_name} — {date} ({status.replace('_', ' ').title()})"):
            detail_response, _ = api_request('GET', f"/demands/{demand['id']}")
            if detail_response and detail_response.get('data'):
                detail = detail_response['data']
                items = detail.get('demand_items', [])

                if items:
                    df = pd.DataFrame([{
                        'Item': i.get('items', {}).get('name', 'Unknown'),
                        'Category': i.get('items', {}).get('category', '').replace('_', ' ').title(),
                        'Approved Qty': i.get('approved_quantity', i.get('requested_quantity', 0)),
                        'Unit': i.get('items', {}).get('unit', '')
                    } for i in items])
                    st.dataframe(df, use_container_width=True, hide_index=True)
