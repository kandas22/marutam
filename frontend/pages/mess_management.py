"""Mess Management Page - Admin Only"""
import streamlit as st
import pandas as pd


def show(api_request):
    """Display mess management interface"""
    st.subheader("🍽️ Mess Unit Management")
    
    tab1, tab2 = st.tabs(["📋 All Mess Units", "➕ Add Mess"])
    
    with tab1:
        show_mess_list(api_request)
    
    with tab2:
        show_create_mess_form(api_request)


def _get_assignable_users(api_request):
    """Fetch all users except admins who can be assigned as mess managers"""
    # Fetch all users
    response, _ = api_request('GET', '/users')
    all_users = response.get('data', {}).get('users', []) if response else []
    
    # Return only active, non-admin users
    return [u for u in all_users if u.get('is_active', True) and u.get('role') != 'admin']


def show_mess_list(api_request):
    """Display list of mess units"""
    response, error = api_request('GET', '/mess')
    
    if error:
        st.error(error)
        return
    
    mess_list = response.get('data', []) if response else []
    
    if not mess_list:
        st.info("No mess units found. Click '➕ Add Mess' to create one.")
        return
    
    for mess in mess_list:
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
            
            with col1:
                st.write(f"**🍽️ {mess.get('name', 'N/A')}**")
                st.caption(f"📍 {mess.get('location', 'N/A')}")
            
            with col2:
                st.write(f"👥 Capacity: {mess.get('capacity', 'N/A')}")
                # Safely handle manager display - users join can be None
                manager_data = mess.get('users')
                if manager_data and isinstance(manager_data, dict):
                    manager_name = manager_data.get('full_name', 'Not assigned')
                else:
                    manager_name = 'Not assigned'
                st.caption(f"👔 Manager: {manager_name}")
            
            with col3:
                status = "🟢 Active" if mess.get('is_active') else "🔴 Inactive"
                st.write(status)
            
            with col4:
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("✏️", key=f"edit_m_{mess['id']}", help="Edit"):
                        st.session_state.edit_mess = mess
                with col_b:
                    if st.button("🗑️", key=f"del_m_{mess['id']}", help="Deactivate"):
                        api_request('DELETE', f"/mess/{mess['id']}")
                        st.rerun()
            
            st.divider()
    
    if 'edit_mess' in st.session_state:
        show_edit_mess_dialog(api_request, st.session_state.edit_mess)


def show_create_mess_form(api_request):
    """Form to create new mess"""
    # Get mess users and grain shop users for manager selection
    assignable_users = _get_assignable_users(api_request)
    
    with st.form("create_mess_form"):
        st.markdown("### Add New Mess Unit")
        
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input("Mess Name *", placeholder="Enter mess name")
            location = st.text_input("Location", placeholder="Enter location")
        
        with col2:
            capacity = st.number_input("Capacity", min_value=0, value=100)
            
            # Build manager options: username - Role
            manager_options = {"": "-- Select Manager --"}
            for u in assignable_users:
                role_label = u.get('role', '').replace('_', ' ').title()
                manager_options[u['id']] = f"{u.get('username', '')} - {role_label}"
            
            manager_id = st.selectbox(
                "Assign Manager",
                options=list(manager_options.keys()),
                format_func=lambda x: manager_options[x],
                help="Assign a Mess User or Grain Shop User as manager"
            )
        
        if st.form_submit_button("➕ Add Mess", use_container_width=True):
            if not name:
                st.error("Mess name is required")
            else:
                data = {
                    'name': name,
                    'location': location,
                    'capacity': capacity,
                    'manager_id': manager_id if manager_id else None
                }
                
                response, error = api_request('POST', '/mess', data=data)
                
                if error:
                    st.error(error)
                elif response and response.get('status') == 'success':
                    st.success("Mess created successfully!")
                    st.balloons()
                else:
                    st.error(response.get('error', 'Failed to create mess'))


@st.dialog("✏️ Edit Mess", width="large")
def show_edit_mess_dialog(api_request, mess):
    """Dialog popup to edit mess"""
    assignable_users = _get_assignable_users(api_request)
    
    st.markdown(f"**Editing:** {mess.get('name', '')}")
    st.divider()
    
    col1, col2 = st.columns(2)
    
    with col1:
        name = st.text_input("Name", value=mess.get('name', ''))
        location = st.text_input("Location", value=mess.get('location', '') or '')
    
    with col2:
        capacity = st.number_input("Capacity", value=int(mess.get('capacity', 0) or 0))
        
        # Build manager options: username - Role
        manager_options = {"": "-- No Manager --"}
        for u in assignable_users:
            role_label = u.get('role', '').replace('_', ' ').title()
            manager_options[u['id']] = f"{u.get('username', '')} - {role_label}"
        
        current_manager = mess.get('manager_id', '') or ''
        manager_keys = list(manager_options.keys())
        default_idx = manager_keys.index(current_manager) if current_manager in manager_keys else 0
        
        manager_id = st.selectbox(
            "Assign Manager",
            options=manager_keys,
            index=default_idx,
            format_func=lambda x: manager_options[x],
            help="Assign a Mess User or Grain Shop User as manager",
            key="edit_mess_manager_dialog"
        )
        
        is_active = st.checkbox("Active", value=mess.get('is_active', True))
    
    st.divider()
    col_a, col_b = st.columns(2)
    
    with col_a:
        if st.button("💾 Save", use_container_width=True, type="primary"):
            data = {
                'name': name,
                'location': location,
                'capacity': capacity,
                'manager_id': manager_id if manager_id else None,
                'is_active': is_active
            }
            
            response, error = api_request('PUT', f"/mess/{mess['id']}", data=data)
            
            if response and response.get('status') == 'success':
                st.success("Updated!")
                if 'edit_mess' in st.session_state:
                    del st.session_state.edit_mess
                st.rerun()
            else:
                st.error(error or 'Failed to update mess')
    
    with col_b:
        if st.button("❌ Cancel", use_container_width=True):
            if 'edit_mess' in st.session_state:
                del st.session_state.edit_mess
            st.rerun()
