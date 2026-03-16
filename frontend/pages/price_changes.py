"""
Price & Unit Change Management Page
Controller proposes → Admin approves/rejects
"""
import streamlit as st
import pandas as pd


def show(api_request, user):
    """Display price/unit change management"""
    role = user.get('role', '')

    st.subheader("💰 Price & Unit Change Management")

    if role == 'grain_shop_user':
        show_controller_view(api_request)
    elif role == 'admin':
        show_admin_view(api_request)
    else:
        st.warning("You do not have access to this page.")


def show_controller_view(api_request):
    """Controller can propose price/unit changes"""
    tab1, tab2 = st.tabs(["📝 Propose Change", "📋 My Proposals"])

    with tab1:
        propose_change_form(api_request)

    with tab2:
        show_proposals(api_request)


def propose_change_form(api_request):
    """Form to propose a price or unit change"""
    st.markdown("### Propose Price or Unit Change")

    # Get items
    items_resp, _ = api_request('GET', '/items', params={'active_only': 'true'})
    items_list = items_resp.get('data', {}).get('items', []) if items_resp else []

    if not items_list:
        st.warning("No items available.")
        return

    item_options = {}
    for item in items_list:
        label = f"{item['name']} ({item.get('category', '').replace('_', ' ').title()}) — Current: {item.get('price', 'N/A')}/{item.get('unit', '')}"
        item_options[label] = item

    with st.form("propose_change_form"):
        selected_label = st.selectbox("Select Item", options=list(item_options.keys()))
        selected_item = item_options[selected_label]

        change_type = st.selectbox("Change Type", ["price", "unit"])

        if change_type == "price":
            current = selected_item.get('price', 'Not Set')
            st.info(f"Current Price: **₹{current}**")
            new_value = st.number_input("New Price (₹)", min_value=0.0, step=0.5)
        else:
            current = selected_item.get('unit', 'N/A')
            st.info(f"Current Unit: **{current}**")
            new_value = st.text_input("New Unit", placeholder="e.g., kg, liters, pieces")

        submitted = st.form_submit_button("📤 Submit for Approval", use_container_width=True)

        if submitted:
            if change_type == "unit" and not new_value:
                st.error("Please enter a new unit value")
            elif change_type == "price" and new_value <= 0:
                st.error("Please enter a valid price")
            else:
                with st.spinner("Submitting proposal..."):
                    response, error = api_request('POST', '/price-changes/propose', data={
                        'item_id': selected_item['id'],
                        'change_type': change_type,
                        'new_value': str(new_value)
                    })

                    if error:
                        st.error(error)
                    elif response and response.get('status') == 'success':
                        st.success(f"✅ {response.get('message', 'Change proposed for approval!')}")
                        st.rerun()
                    else:
                        st.error(response.get('error', 'Failed to submit proposal'))


def show_proposals(api_request):
    """Show controller's submitted proposals"""
    st.markdown("### My Proposals")

    # Get all changes (pending and processed)
    for status_label, status_value in [("⏳ Pending", "pending"), ("✅ Approved", "approved"), ("❌ Rejected", "rejected")]:
        response, _ = api_request('GET', '/price-changes/history', params={'status': status_value})
        history = response.get('data', {}).get('history', []) if response else []

        if history:
            st.markdown(f"#### {status_label}")
            df = pd.DataFrame([{
                'Item': h.get('items', {}).get('name', 'Unknown') if h.get('items') else 'Unknown',
                'Type': h.get('change_type', '').title(),
                'Old Value': h.get('old_value', '-'),
                'New Value': h.get('new_value', '-'),
                'Status': h.get('approval_status', '').title(),
                'Proposed At': h.get('proposed_at', 'N/A')[:19] if h.get('proposed_at') else 'N/A',
                'Reason': h.get('rejection_reason', '-') or '-'
            } for h in history])
            st.dataframe(df, use_container_width=True, hide_index=True)


def show_admin_view(api_request):
    """Admin can approve/reject changes and view history"""
    tab1, tab2 = st.tabs(["⏳ Pending Approvals", "📋 Change History"])

    with tab1:
        show_pending_approvals(api_request)

    with tab2:
        show_change_history(api_request)


def show_pending_approvals(api_request):
    """Show pending price/unit change proposals"""
    st.markdown("### ⏳ Pending Price/Unit Change Approvals")

    response, error = api_request('GET', '/price-changes/pending')
    if error:
        st.error(error)
        return

    pending = response.get('data', {}).get('pending_changes', []) if response else []

    if not pending:
        st.success("✅ No pending price/unit change requests!")
        return

    st.warning(f"⚠️ {len(pending)} change request(s) waiting for your review")

    for change in pending:
        item_name = change.get('items', {}).get('name', 'Unknown') if change.get('items') else 'Unknown'
        change_type = change.get('change_type', '').title()
        old_val = change.get('old_value', '-')
        new_val = change.get('new_value', '-')
        proposed_by = change.get('users', {}).get('full_name', 'Unknown') if change.get('users') else 'Unknown'

        unit_text = '₹' if change.get('change_type') == 'price' else ''

        with st.expander(f"🔄 {item_name} — {change_type}: {unit_text}{old_val} → {unit_text}{new_val}"):
            st.markdown(f"- **Item:** {item_name}")
            st.markdown(f"- **Change Type:** {change_type}")
            st.markdown(f"- **Current Value:** {unit_text}{old_val}")
            st.markdown(f"- **Proposed Value:** {unit_text}{new_val}")
            st.markdown(f"- **Proposed By:** {proposed_by}")
            st.markdown(f"- **Proposed At:** {change.get('proposed_at', 'N/A')[:19] if change.get('proposed_at') else 'N/A'}")

            col1, col2, col3 = st.columns([1, 1, 2])
            with col1:
                if st.button("✅ Approve", key=f"approve_price_{change['id']}", type="primary"):
                    resp, err = api_request('POST', f"/price-changes/{change['id']}/approve")
                    if err:
                        st.error(err)
                    elif resp and resp.get('status') == 'success':
                        st.success("Change approved and applied!")
                        st.rerun()
            with col2:
                reason = st.text_input("Reason", key=f"reason_price_{change['id']}", placeholder="Optional")
                if st.button("❌ Reject", key=f"reject_price_{change['id']}"):
                    resp, err = api_request('POST', f"/price-changes/{change['id']}/reject", data={
                        'reason': reason
                    })
                    if err:
                        st.error(err)
                    elif resp and resp.get('status') == 'success':
                        st.warning("Change rejected")
                        st.rerun()


def show_change_history(api_request):
    """Show full price/unit change history"""
    st.markdown("### 📋 Price/Unit Change History")

    response, error = api_request('GET', '/price-changes/history')
    if error:
        st.error(error)
        return

    history = response.get('data', {}).get('history', []) if response else []

    if not history:
        st.info("No change history found.")
        return

    df = pd.DataFrame([{
        'Item': h.get('items', {}).get('name', 'Unknown') if h.get('items') else 'Unknown',
        'Type': h.get('change_type', '').title(),
        'Old Value': h.get('old_value', '-'),
        'New Value': h.get('new_value', '-'),
        'Status': h.get('approval_status', '').title(),
        'Proposed By': h.get('users', {}).get('full_name', '-') if h.get('users') else '-',
        'Date': h.get('proposed_at', 'N/A')[:19] if h.get('proposed_at') else 'N/A',
        'Rejection Reason': h.get('rejection_reason', '-') or '-'
    } for h in history])

    st.dataframe(df, use_container_width=True, hide_index=True)
