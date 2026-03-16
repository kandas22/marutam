"""
Reports Page - Admin Full Access
All 7 report categories per spec:
  1. Demand Reports
  2. Supply Reports
  3. Inventory Reports
  4. User Reports
  5. Contractor Reports
  6. Daily Mess Entry Reports
  7. Financial Reports
  + Activity Log / Audit Trail
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta


def show(api_request):
    """Display reports and analytics"""
    st.subheader("📊 Reports & Analytics")

    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "📋 Demands",
        "🚚 Supply",
        "📦 Inventory",
        "👥 Users",
        "📝 Contractors",
        "🍽️ Mess Entries",
        "💰 Financial",
        "🔍 Audit Trail"
    ])

    with tab1:
        show_demand_reports(api_request)
    with tab2:
        show_supply_reports(api_request)
    with tab3:
        show_inventory_reports(api_request)
    with tab4:
        show_user_reports(api_request)
    with tab5:
        show_contractor_reports(api_request)
    with tab6:
        show_mess_entry_reports(api_request)
    with tab7:
        show_financial_reports(api_request)
    with tab8:
        show_audit_trail(api_request)


# =====================================================
# 1. DEMAND REPORTS
# =====================================================

def show_demand_reports(api_request):
    """Demand reports with filtering"""
    st.markdown("### 📋 Demand Reports")

    col1, col2, col3 = st.columns(3)
    with col1:
        status_filter = st.selectbox("Status", [
            "All", "draft", "submitted", "approved", "rejected",
            "forwarded_to_contractor", "supplied_to_controller", "distributed_to_messes"
        ], key="dr_status")
    with col2:
        from_date = st.date_input("From", value=datetime.now() - timedelta(days=30), key="dr_from")
    with col3:
        to_date = st.date_input("To", value=datetime.now(), key="dr_to")

    params = {
        'from_date': from_date.strftime('%Y-%m-%d'),
        'to_date': to_date.strftime('%Y-%m-%d')
    }
    if status_filter != "All":
        params['status'] = status_filter

    response, error = api_request('GET', '/reports/demands', params=params)
    if error:
        st.error(error)
        return

    demands = response.get('data', {}).get('demands', []) if response else []

    if not demands:
        st.info("No demands found for the selected filters.")
        return

    df = pd.DataFrame([{
        'Date': d.get('demand_date', 'N/A'),
        'Mess': d.get('mess', {}).get('name', 'Unknown') if d.get('mess') else 'Unknown',
        'Status': d.get('status', '').replace('_', ' ').title(),
        'Items': len(d.get('demand_items', [])),
        'Submitted By': d.get('users', {}).get('full_name', '-') if isinstance(d.get('users'), dict) else '-',
        'Contractor': d.get('contractors', {}).get('name', '-') if isinstance(d.get('contractors'), dict) else '-'
    } for d in demands])

    st.dataframe(df, use_container_width=True, hide_index=True)

    # Status distribution chart
    if not df.empty:
        fig = px.pie(df, names='Status', title='Demands by Status',
                     color_discrete_sequence=px.colors.qualitative.Set2)
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)


# =====================================================
# 2. SUPPLY REPORTS
# =====================================================

def show_supply_reports(api_request):
    """Supply reports"""
    st.markdown("### 🚚 Supply Reports")

    sub_tab = st.radio("Report Type", [
        "Supply History", "Supply vs Demand"
    ], horizontal=True, key="supply_sub")

    col1, col2 = st.columns(2)
    with col1:
        from_date = st.date_input("From", value=datetime.now() - timedelta(days=90), key="sr_from")
    with col2:
        to_date = st.date_input("To", value=datetime.now(), key="sr_to")

    params = {
        'from_date': from_date.strftime('%Y-%m-%d'),
        'to_date': to_date.strftime('%Y-%m-%d')
    }

    if sub_tab == "Supply History":
        response, error = api_request('GET', '/reports/supply/history', params=params)
        if error:
            st.error(error)
            return

        history = response.get('data', {}).get('history', []) if response else []
        if not history:
            st.info("No supply records found.")
            return

        df = pd.DataFrame([{
            'Date': h.get('supply_date', 'N/A'),
            'Contractor': h.get('contractors', {}).get('name', '-') if h.get('contractors') else '-',
            'Item': h.get('items', {}).get('name', '-') if h.get('items') else '-',
            'Category': (h.get('items', {}).get('category', '') if h.get('items') else '').replace('_', ' ').title(),
            'Quantity': h.get('supplied_quantity', 0),
            'Unit': h.get('items', {}).get('unit', '') if h.get('items') else '',
            'Unit Price': h.get('unit_price', '-'),
            'Received By': h.get('users', {}).get('full_name', '-') if h.get('users') else '-'
        } for h in history])

        st.dataframe(df, use_container_width=True, hide_index=True)

    elif sub_tab == "Supply vs Demand":
        response, error = api_request('GET', '/reports/supply/vs-demand', params=params)
        if error:
            st.error(error)
            return

        comparison = response.get('data', []) if response else []
        if not comparison:
            st.info("No data available for comparison.")
            return

        df = pd.DataFrame(comparison)
        st.dataframe(df, use_container_width=True, hide_index=True)

        if not df.empty:
            fig = px.bar(df, x='item_name', y=['total_demanded', 'total_supplied'],
                        barmode='group', title='Demand vs Supply by Item',
                        color_discrete_sequence=['#3498db', '#27ae60'])
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)


# =====================================================
# 3. INVENTORY REPORTS
# =====================================================

def show_inventory_reports(api_request):
    """Inventory reports"""
    st.markdown("### 📦 Inventory Reports")

    sub_tab = st.radio("Report Type", [
        "Current Inventory", "Low Stock Alerts", "Price Change History", "Category Breakdown"
    ], horizontal=True, key="inv_sub")

    if sub_tab == "Current Inventory":
        response, error = api_request('GET', '/reports/inventory/current')
        if error:
            st.error(error)
            return
        data = response.get('data', []) if response else []
        if not data:
            st.info("No inventory data.")
            return

        df = pd.DataFrame(data)
        display_cols = ['item_name', 'category', 'current_stock', 'minimum_stock', 'unit', 'price', 'is_low_stock']
        df_display = df[[c for c in display_cols if c in df.columns]]
        st.dataframe(df_display, use_container_width=True, hide_index=True)

    elif sub_tab == "Low Stock Alerts":
        response, error = api_request('GET', '/reports/inventory/low-stock')
        if error:
            st.error(error)
            return
        data = response.get('data', []) if response else []
        if not data:
            st.success("✅ All items are above minimum stock levels!")
            return

        st.warning(f"⚠️ {len(data)} item(s) below minimum stock!")
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)

    elif sub_tab == "Price Change History":
        response, error = api_request('GET', '/reports/inventory/price-history')
        if error:
            st.error(error)
            return
        history = response.get('data', {}).get('history', []) if response else []
        if not history:
            st.info("No price change history.")
            return

        df = pd.DataFrame([{
            'Item': h.get('items', {}).get('name', '-') if h.get('items') else '-',
            'Type': h.get('change_type', '').title(),
            'Old Value': h.get('old_value', '-'),
            'New Value': h.get('new_value', '-'),
            'Status': h.get('approval_status', '').title(),
            'Proposed By': h.get('users', {}).get('full_name', '-') if h.get('users') else '-',
            'Date': h.get('proposed_at', 'N/A')[:19] if h.get('proposed_at') else 'N/A'
        } for h in history])
        st.dataframe(df, use_container_width=True, hide_index=True)

    elif sub_tab == "Category Breakdown":
        response, error = api_request('GET', '/reports/category-wise')
        if error:
            st.error(error)
            return
        data = response.get('data', {}) if response else {}
        if not data:
            st.info("No category data.")
            return

        cat_labels = {'veg': 'Vegetarian', 'non_veg': 'Non-Vegetarian', 'grain_shop': 'Grain Shop'}
        df = pd.DataFrame([{
            'Category': cat_labels.get(k, k),
            'Items': v.get('item_count', 0),
            'Total Quantity': v.get('total_quantity', 0)
        } for k, v in data.items()])

        st.dataframe(df, use_container_width=True, hide_index=True)

        fig = px.pie(df, values='Items', names='Category', title='Items by Category',
                     color_discrete_sequence=['#28a745', '#dc3545', '#fd7e14'])
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)


# =====================================================
# 4. USER REPORTS
# =====================================================

def show_user_reports(api_request):
    """User reports"""
    st.markdown("### 👥 User Reports")

    role_filter = st.selectbox("Filter by Role", [
        "All", "admin", "grain_shop_user", "mess_user", "contractor"
    ], key="ur_role")

    params = {}
    if role_filter != "All":
        params['role'] = role_filter

    response, error = api_request('GET', '/reports/users', params=params)
    if error:
        st.error(error)
        return

    users = response.get('data', {}).get('users', []) if response else []
    total = response.get('data', {}).get('total', 0) if response else 0

    st.info(f"Total users: **{total}**")

    if users:
        df = pd.DataFrame([{
            'Name': u.get('full_name', '-'),
            'Username': u.get('username', '-'),
            'Email': u.get('email', '-'),
            'Role': u.get('role', '').replace('_', ' ').title(),
            'Phone': u.get('phone', '-'),
            'Active': '✅' if u.get('is_active') else '❌',
            'Created': u.get('created_at', 'N/A')[:10] if u.get('created_at') else 'N/A'
        } for u in users])
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Role distribution
        fig = px.pie(df, names='Role', title='Users by Role',
                     color_discrete_sequence=px.colors.qualitative.Set3)
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)


# =====================================================
# 5. CONTRACTOR REPORTS
# =====================================================

def show_contractor_reports(api_request):
    """Contractor reports"""
    st.markdown("### 📝 Contractor Reports")

    sub_tab = st.radio("Report Type", [
        "Current Contractor", "Contractor History", "Contractor Performance"
    ], horizontal=True, key="cr_sub")

    if sub_tab == "Current Contractor":
        response, error = api_request('GET', '/reports/contractors/current')
        if error:
            st.error(error)
            return
        contractors = response.get('data', []) if response else []
        if not contractors:
            st.info("No active contractors.")
            return

        for c in contractors:
            st.markdown(f"""
            **{c.get('name', 'Unknown')}**
            - Contact: {c.get('contact_person', '-')}
            - Phone: {c.get('phone', '-')}
            - Email: {c.get('email', '-')}
            - GST: {c.get('gst_number', '-')}
            - Tender Year: {c.get('tender_year', '-')}
            """)

    elif sub_tab == "Contractor History":
        response, error = api_request('GET', '/reports/contractors/history')
        if error:
            st.error(error)
            return
        contractors = response.get('data', []) if response else []
        if not contractors:
            st.info("No contractor history.")
            return

        df = pd.DataFrame([{
            'Name': c.get('name', '-'),
            'Contact': c.get('contact_person', '-'),
            'Phone': c.get('phone', '-'),
            'Tender Year': c.get('tender_year', '-'),
            'Start Date': c.get('tender_start_date', '-'),
            'End Date': c.get('tender_end_date', '-'),
            'Active': '✅' if c.get('is_active') else '❌'
        } for c in contractors])
        st.dataframe(df, use_container_width=True, hide_index=True)

    elif sub_tab == "Contractor Performance":
        response, error = api_request('GET', '/reports/contractors/performance')
        if error:
            st.error(error)
            return
        performance = response.get('data', []) if response else []
        if not performance:
            st.info("No performance data available.")
            return

        df = pd.DataFrame(performance)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Performance chart
        if not df.empty and 'total_cost' in df.columns:
            fig = px.bar(df, x='contractor_name', y='total_cost',
                        title='Total Cost by Contractor',
                        color_discrete_sequence=['#9b59b6'])
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)


# =====================================================
# 6. DAILY MESS ENTRY REPORTS
# =====================================================

def show_mess_entry_reports(api_request):
    """Daily mess entry reports"""
    st.markdown("### 🍽️ Daily Mess Entry Reports")

    sub_tab = st.radio("Report Type", [
        "Daily Entries", "Distributed vs Received", "Mess Consumption"
    ], horizontal=True, key="me_sub")

    col1, col2 = st.columns(2)
    with col1:
        from_date = st.date_input("From", value=datetime.now() - timedelta(days=30), key="me_from")
    with col2:
        to_date = st.date_input("To", value=datetime.now(), key="me_to")

    params = {
        'from_date': from_date.strftime('%Y-%m-%d'),
        'to_date': to_date.strftime('%Y-%m-%d')
    }

    if sub_tab == "Daily Entries":
        response, error = api_request('GET', '/reports/mess/daily-entries', params=params)
        if error:
            st.error(error)
            return

        entries = response.get('data', {}).get('entries', []) if response else []
        if not entries:
            st.info("No daily entries found.")
            return

        df = pd.DataFrame([{
            'Date': e.get('usage_date', 'N/A'),
            'Mess': e.get('mess', {}).get('name', '-') if e.get('mess') else '-',
            'Item': e.get('items', {}).get('name', '-') if e.get('items') else '-',
            'Category': (e.get('items', {}).get('category', '') if e.get('items') else '').replace('_', ' ').title(),
            'Quantity': e.get('quantity_used', 0),
            'Unit': e.get('items', {}).get('unit', '') if e.get('items') else '',
            'Meal': e.get('meal_type', '-'),
            'Status': e.get('approval_status', '').title(),
            'Recorded By': e.get('users', {}).get('full_name', '-') if e.get('users') else '-'
        } for e in entries])
        st.dataframe(df, use_container_width=True, hide_index=True)

    elif sub_tab == "Distributed vs Received":
        response, error = api_request('GET', '/reports/mess/distributed-vs-received', params=params)
        if error:
            st.error(error)
            return

        comparison = response.get('data', []) if response else []
        if not comparison:
            st.info("No comparison data available.")
            return

        df = pd.DataFrame(comparison)
        st.dataframe(df, use_container_width=True, hide_index=True)

        if not df.empty:
            fig = px.bar(df, x='mess_name', y=['distributed', 'received'],
                        barmode='group', title='Distributed vs Received by Mess',
                        color_discrete_sequence=['#3498db', '#e74c3c'])
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

    elif sub_tab == "Mess Consumption":
        response, error = api_request('GET', '/reports/mess/summary', params=params)
        if error:
            st.error(error)
            return

        data = response.get('data', []) if response else []
        if not data:
            st.info("No consumption data found.")
            return

        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)

        if not df.empty and 'mess_name' in df.columns:
            fig = px.bar(
                df.groupby('mess_name')['total_used'].sum().reset_index(),
                x='mess_name', y='total_used',
                title='Total Consumption by Mess',
                color_discrete_sequence=['#27ae60']
            )
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)


# =====================================================
# 7. FINANCIAL REPORTS
# =====================================================

def show_financial_reports(api_request):
    """Financial reports"""
    st.markdown("### 💰 Financial Reports")

    sub_tab = st.radio("Report Type", [
        "Total Expenditure", "Cost per Mess"
    ], horizontal=True, key="fin_sub")

    col1, col2 = st.columns(2)
    with col1:
        from_date = st.date_input("From", value=datetime.now() - timedelta(days=90), key="fin_from")
    with col2:
        to_date = st.date_input("To", value=datetime.now(), key="fin_to")

    params = {
        'from_date': from_date.strftime('%Y-%m-%d'),
        'to_date': to_date.strftime('%Y-%m-%d')
    }

    if sub_tab == "Total Expenditure":
        response, error = api_request('GET', '/reports/financial/expenditure', params=params)
        if error:
            st.error(error)
            return

        data = response.get('data', {}) if response else {}
        total = data.get('total_expenditure', 0)
        by_category = data.get('by_category', [])

        st.metric("Total Expenditure", f"₹{total:,.2f}")

        if by_category:
            df = pd.DataFrame(by_category)
            st.dataframe(df, use_container_width=True, hide_index=True)

            fig = px.pie(df, values='total_cost', names='category',
                        title='Expenditure by Category',
                        color_discrete_sequence=['#28a745', '#dc3545', '#fd7e14'])
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)

    elif sub_tab == "Cost per Mess":
        response, error = api_request('GET', '/reports/financial/cost-per-mess', params=params)
        if error:
            st.error(error)
            return

        data = response.get('data', []) if response else []
        if not data:
            st.info("No cost data available.")
            return

        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)

        if not df.empty:
            fig = px.bar(df, x='mess_name', y='total_cost',
                        title='Expenditure by Mess',
                        color_discrete_sequence=['#1e3a5f'])
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)


# =====================================================
# 8. AUDIT TRAIL
# =====================================================

def show_audit_trail(api_request):
    """Activity log / audit trail"""
    st.markdown("### 🔍 Audit Trail & Activity Log")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        action_filter = st.selectbox("Action", [
            "All", "CREATE", "UPDATE", "DELETE", "LOGIN", "LOGOUT",
            "APPROVE", "REJECT", "SUBMIT", "FORWARD", "PROPOSE_CHANGE",
            "UPDATE_REQUEST", "PASSWORD_RESET"
        ], key="at_action")
    with col2:
        table_filter = st.selectbox("Module", [
            "All", "users", "items", "demands", "demand_items",
            "contractors", "contractor_supplies", "distribution_log",
            "daily_ration_usage", "price_change_history", "pending_updates",
            "mess", "grain_shop_inventory"
        ], key="at_table")
    with col3:
        from_date = st.date_input("From", value=datetime.now() - timedelta(days=7), key="at_from")
    with col4:
        to_date = st.date_input("To", value=datetime.now(), key="at_to")

    params = {
        'from_date': from_date.strftime('%Y-%m-%d'),
        'to_date': to_date.strftime('%Y-%m-%d')
    }
    if action_filter != "All":
        params['action'] = action_filter
    if table_filter != "All":
        params['table_name'] = table_filter

    response, error = api_request('GET', '/reports/activity-log', params=params)
    if error:
        st.error(error)
        return

    activities = response.get('data', {}).get('activities', []) if response else []

    if not activities:
        st.info("No activity records found for the selected filters.")
        return

    df = pd.DataFrame([{
        'Time': a.get('created_at', 'N/A')[:19] if a.get('created_at') else 'N/A',
        'User': a.get('users', {}).get('full_name', 'System') if a.get('users') else 'System',
        'Role': a.get('users', {}).get('role', 'N/A').replace('_', ' ').title() if a.get('users') else 'N/A',
        'Action': a.get('action', 'N/A'),
        'Module': a.get('table_name', '-'),
        'IP': a.get('ip_address', 'N/A')
    } for a in activities])

    st.dataframe(df, use_container_width=True, hide_index=True)

    # Activity chart
    if not df.empty:
        fig = px.histogram(df, x='Action', title='Activity Distribution',
                          color_discrete_sequence=['#2d5a87'])
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)
