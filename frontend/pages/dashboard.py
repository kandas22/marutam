"""Dashboard Page"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta


def show(api_request, user):
    """Display dashboard based on user role"""
    role = user.get('role', '')

    if role == 'admin':
        show_admin_dashboard(api_request)
    elif role == 'grain_shop_user':
        show_grain_shop_dashboard(api_request)
    elif role == 'contractor':
        show_contractor_dashboard(api_request)
    else:
        show_mess_dashboard(api_request, user)


def show_admin_dashboard(api_request):
    """Admin dashboard with full statistics"""
    st.subheader("📊 Admin Dashboard")

    # Get dashboard stats
    response, error = api_request('GET', '/reports/dashboard')

    if error:
        st.error(error)
        return

    stats = response.get('data', {}) if response else {}

    # Stats cards — Row 1
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-value">{stats.get('total_users', 0)}</div>
            <div class="stat-label">👥 Total Users</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-value">{stats.get('total_contractors', 0)}</div>
            <div class="stat-label">🏢 Contractors</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-value">{stats.get('total_mess_units', 0)}</div>
            <div class="stat-label">🍽️ Mess Units</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-value">{stats.get('total_items', 0)}</div>
            <div class="stat-label">📦 Items</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Stats cards — Row 2 (Action Items)
    col5, col6, col7, col8 = st.columns(4)

    with col5:
        pending_count = stats.get('pending_approvals', 0)
        color = '#dc3545' if pending_count > 0 else '#28a745'
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-value" style="color: {color};">{pending_count}</div>
            <div class="stat-label">⏳ Pending Approvals</div>
        </div>
        """, unsafe_allow_html=True)

    with col6:
        demand_count = stats.get('pending_demands', 0)
        color = '#dc3545' if demand_count > 0 else '#28a745'
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-value" style="color: {color};">{demand_count}</div>
            <div class="stat-label">📋 Pending Demands</div>
        </div>
        """, unsafe_allow_html=True)

    with col7:
        price_count = stats.get('pending_price_changes', 0)
        color = '#dc3545' if price_count > 0 else '#28a745'
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-value" style="color: {color};">{price_count}</div>
            <div class="stat-label">💰 Price Changes</div>
        </div>
        """, unsafe_allow_html=True)

    with col8:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-value">{stats.get('today_activity_count', 0)}</div>
            <div class="stat-label">📈 Today's Activity</div>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # Activity section
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("📈 Today's Overview")
        st.metric("Distributions", stats.get('today_distributions', 0))

        # Demand stats
        demand_stats, _ = api_request('GET', '/demands/stats')
        if demand_stats and demand_stats.get('data'):
            ds = demand_stats['data']
            st.markdown("**Demand Pipeline:**")
            pipeline_cols = st.columns(4)
            pipeline_cols[0].metric("Draft", ds.get('draft', 0))
            pipeline_cols[1].metric("Submitted", ds.get('submitted', 0))
            pipeline_cols[2].metric("Approved", ds.get('approved', 0))
            pipeline_cols[3].metric("Supplied", ds.get('supplied_to_controller', 0))

    with col_b:
        st.subheader("📦 Inventory Overview")

        # Category wise
        cat_response, _ = api_request('GET', '/reports/category-wise')
        if cat_response and cat_response.get('data'):
            cat_data = cat_response['data']
            df = pd.DataFrame([
                {'Category': 'Vegetarian', 'Items': cat_data.get('veg', {}).get('item_count', 0)},
                {'Category': 'Non-Vegetarian', 'Items': cat_data.get('non_veg', {}).get('item_count', 0)},
                {'Category': 'Grain Shop', 'Items': cat_data.get('grain_shop', {}).get('item_count', 0)}
            ])

            fig = px.pie(df, values='Items', names='Category',
                        color_discrete_sequence=['#28a745', '#dc3545', '#fd7e14'])
            fig.update_layout(height=300, margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig, use_container_width=True)

    # Weekly data flow chart
    st.divider()
    st.subheader("📊 Weekly Data Flow")

    from_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    flow_response, _ = api_request('GET', '/reports/data-flow', params={'from_date': from_date})

    if flow_response and flow_response.get('data'):
        df = pd.DataFrame(flow_response['data'])
        if not df.empty:
            fig = px.bar(df, x='activity_date', y='action_count', color='action',
                        title='Daily Activity by Action Type')
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No activity data available for the selected period.")


def show_grain_shop_dashboard(api_request):
    """Grain shop user (Controller) dashboard"""
    st.subheader("📊 Controller Dashboard")

    # Get stock levels
    stock_response, error = api_request('GET', '/grain-shop/stock-levels')

    if error:
        st.error(error)
        return

    stock_data = stock_response.get('data', []) if stock_response else []

    # Low stock alerts
    low_stock = [s for s in stock_data if s.get('is_low_stock')]

    if low_stock:
        st.warning(f"⚠️ {len(low_stock)} items are below minimum stock level!")
        with st.expander("View Low Stock Items"):
            for item in low_stock:
                st.write(f"• **{item['item_name']}**: {item['current_stock']} {item['unit']} (Min: {item['minimum_stock']})")

    # Stats
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_items = len(stock_data)
        st.metric("Total Items", total_items)

    with col2:
        total_stock = sum(s.get('current_stock', 0) for s in stock_data)
        st.metric("Total Stock", f"{total_stock:.0f}")

    with col3:
        st.metric("Low Stock Items", len(low_stock))

    with col4:
        # Get pending demands
        demand_stats, _ = api_request('GET', '/demands/stats')
        submitted = demand_stats.get('data', {}).get('submitted', 0) if demand_stats else 0
        st.metric("Pending Demands", submitted)

    # Stock table
    st.divider()
    st.subheader("📦 Current Stock Levels")

    if stock_data:
        df = pd.DataFrame(stock_data)
        display_cols = [c for c in ['item_name', 'category', 'current_stock', 'minimum_stock', 'unit', 'is_low_stock'] if c in df.columns]
        if display_cols:
            df_display = df[display_cols]
            df_display.columns = [c.replace('_', ' ').title() for c in display_cols]
            st.dataframe(df_display, use_container_width=True, hide_index=True)


def show_contractor_dashboard(api_request):
    """Contractor dashboard — view assigned demands"""
    st.subheader("📊 Contractor Dashboard")

    # Get demands forwarded to this contractor
    response, error = api_request('GET', '/demands')
    if error:
        st.error(error)
        return

    demands = response.get('data', {}).get('demands', []) if response else []

    # Stats
    col1, col2, col3 = st.columns(3)
    with col1:
        forwarded = len([d for d in demands if d.get('status') == 'forwarded_to_contractor'])
        st.metric("📋 Pending Fulfillment", forwarded)
    with col2:
        supplied = len([d for d in demands if d.get('status') == 'supplied_to_controller'])
        st.metric("✅ Supplied", supplied)
    with col3:
        st.metric("📦 Total Demands", len(demands))

    st.divider()

    if demands:
        st.subheader("📋 Recent Demands")
        for demand in demands[:10]:
            status = demand.get('status', '')
            mess_name = demand.get('mess', {}).get('name', 'Unknown') if demand.get('mess') else 'Unknown'
            date = demand.get('demand_date', 'N/A')

            emoji = '📋' if status == 'forwarded_to_contractor' else '✅' if status == 'supplied_to_controller' else '📦'
            st.markdown(f"- {emoji} **{mess_name}** — {date} ({status.replace('_', ' ').title()})")
    else:
        st.info("No demands assigned to you yet.")


def show_mess_dashboard(api_request, user):
    """Mess user dashboard"""
    st.subheader("📊 Mess Dashboard")

    # Get mess info
    mess_response, error = api_request('GET', '/mess')

    if error:
        st.error(error)
        return

    mess_list = mess_response.get('data', []) if mess_response else []

    if not mess_list:
        st.info("No mess assigned. Please contact administrator.")
        return

    mess = mess_list[0]  # Get first assigned mess

    st.markdown(f"""
    <div class="info-card">
        <h4>🍽️ {mess.get('name', 'Your Mess')}</h4>
        <p>Location: {mess.get('location', 'N/A')} | Capacity: {mess.get('capacity', 'N/A')}</p>
    </div>
    """, unsafe_allow_html=True)

    # Get demands for this mess
    demands_response, _ = api_request('GET', '/demands')
    demands = demands_response.get('data', {}).get('demands', []) if demands_response else []

    # Demand stats
    col1, col2, col3 = st.columns(3)
    with col1:
        draft = len([d for d in demands if d.get('status') == 'draft'])
        st.metric("📝 Draft Demands", draft)
    with col2:
        pending = len([d for d in demands if d.get('status') == 'submitted'])
        st.metric("⏳ Pending Approval", pending)
    with col3:
        approved = len([d for d in demands if d.get('status') in ('approved', 'forwarded_to_contractor', 'supplied_to_controller', 'distributed_to_messes')])
        st.metric("✅ Approved", approved)

    st.divider()

    # Today's usage summary
    today = datetime.now().strftime('%Y-%m-%d')
    usage_response, _ = api_request('GET', f"/mess/{mess['id']}/daily-usage",
                                    params={'from_date': today, 'to_date': today})

    usage_data = usage_response.get('data', {}).get('usage', []) if usage_response else []

    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("📅 Today's Usage")
        if usage_data:
            for entry in usage_data:
                item = entry.get('items', {})
                status = entry.get('approval_status', 'pending')
                status_color = '#28a745' if status == 'approved' else '#ffc107' if status == 'pending' else '#dc3545'
                st.markdown(f"""
                • **{item.get('name', 'Unknown')}**: {entry.get('quantity_used', 0)} {item.get('unit', '')}
                <span style="background-color: {status_color}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem;">
                    {status.upper()}
                </span>
                """, unsafe_allow_html=True)
        else:
            st.info("No usage recorded for today")

    with col_b:
        st.subheader("📊 Quick Stats")
        usage_pending = len([u for u in usage_data if u.get('approval_status') == 'pending'])
        usage_approved = len([u for u in usage_data if u.get('approval_status') == 'approved'])
        st.metric("Pending Approvals", usage_pending)
        st.metric("Approved Today", usage_approved)
